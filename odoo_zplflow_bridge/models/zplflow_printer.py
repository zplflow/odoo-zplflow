# -*- coding: utf-8 -*-
"""Polymorphic Zebra thermal printer model supporting IPPS, raw TCP and USB."""

import socket
import struct
import logging
import base64

try:
    import requests
    import urllib3
except ImportError:
    requests = None
    urllib3 = None

try:
    from odoo import models, fields, api, _
    from odoo.exceptions import UserError
except ImportError:
    class models:
        class Model:
            pass

    class fields:
        @staticmethod
        def Char(**kwargs):
            return kwargs

        @staticmethod
        def Integer(**kwargs):
            return kwargs

        @staticmethod
        def Boolean(**kwargs):
            return kwargs

        @staticmethod
        def Selection(selection, **kwargs):
            return kwargs

    def api_onchange(*args):
        def decorator(f):
            return f
        return decorator

    api = type('api', (), {'onchange': api_onchange})

    def _(msg):
        return msg

    class UserError(Exception):
        pass


from .ipp_builder import IPPPayloadBuilder

_logger = logging.getLogger(__name__)


class ZPLFlowPrinter(models.Model):
    _name = 'zplflow.printer'
    _description = 'Zebra Thermal Printer via ZplFlow'

    name = fields.Char(string='Printer Name', required=True)
    protocol = fields.Selection([
        ('ipps', 'Zebra Link-OS IPPS (Port 631 TLS) - Firmware V89+'),
        ('raw_tcp', 'Raw Socket TCP (Port 9100 / 9001) - Legacy'),
        ('usb_direct', 'Direct USB (/dev/usb/lpX)')
    ], default='ipps', required=True)

    ip_address = fields.Char(string='IP Address / Hostname')
    port = fields.Integer(string='Port', default=631)
    tls_verify = fields.Boolean(
        string='Verify TLS Certificate',
        default=False,
        help="Disable for local printers with self-signed TLS certificates."
    )
    device_path = fields.Char(string='USB Device Path', default='/dev/usb/lp0')
    dpi = fields.Selection([('203', '203 DPI'), ('300', '300 DPI')], default='203', required=True)
    pipeline_id = fields.Char(string='Default ZplFlow Pipeline ID')
    active = fields.Boolean(string='Active', default=True)

    def action_test_print(self):
        self.ensure_one()
        proto_name = self.protocol
        if hasattr(self, '_fields') and 'protocol' in self._fields:
            proto_name = dict(self._fields['protocol'].selection).get(self.protocol, self.protocol)

        target = self.device_path if self.protocol == 'usb_direct' else f"{self.ip_address}:{self.port}"
        zpl = f"""^XA
^PW812
^LL1218
^BY2,3,100
^FO40,40^GB732,1138,4^FS
^FO80,90^A0N,45,45^FDZplFlow Test Label^FS
^FO80,150^GB652,2,2^FS
^FO80,190^A0N,28,28^FDPrinter: {self.name}^FS
^FO80,235^A0N,26,26^FDProtocol: {proto_name}^FS
^FO80,280^A0N,26,26^FDResolution: {self.dpi} DPI^FS
^FO80,325^A0N,26,26^FDTarget: {target}^FS
^FO80,380^GB652,2,2^FS
^FO80,420^A0N,28,28^FDStatus: READY TO PRINT^FS
^FO80,480^BCN,100,Y,N,N^FD{self.name[:16]}^FS
^FO80,680^GB652,2,2^FS
^FO80,720^A0N,22,22^FDUniversal Label Bridge for Odoo WMS via ZplFlow^FS
^FO80,755^A0N,20,20^FDhttps://www.zplflow.io^FS
^XZ"""

        applied_pipeline = False
        api_key = self.env['ir.config_parameter'].sudo().get_param('zplflow.api_key')
        api_url = (self.env['ir.config_parameter'].sudo().get_param('zplflow.api_url') or 'https://api.zplflow.io').rstrip('/')
        pipeline_id = self.pipeline_id or self.env['ir.config_parameter'].sudo().get_param('zplflow.default_pipeline_id')
        if api_key and pipeline_id and requests:
            try:
                _logger.info("Applying test print pipeline '%s' via %s", pipeline_id, api_url)
                zpl_b64 = base64.b64encode(zpl.encode('utf-8')).decode('ascii')
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'X-API-Key': api_key,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
                payload = {
                    'documents': [
                        {
                            'zpl_base64': zpl_b64,
                            'variables': {'name': self.name},
                        }
                    ]
                }
                res = requests.post(
                    f"{api_url}/v1/pipelines/{pipeline_id}/apply",
                    json=payload,
                    headers=headers,
                    timeout=8.0
                )
                _logger.info("zplflow API pipeline response: %s", res.status_code)
                if res.status_code == 200:
                    data = res.json()
                    docs = data.get('documents') or []
                    if docs and 'zpl_base64' in docs[0]:
                        zpl = base64.b64decode(docs[0]['zpl_base64']).decode('utf-8')
                        applied_pipeline = True
                        _logger.info("Pipeline %s successfully applied to test label", pipeline_id)
                else:
                    _logger.warning("zplflow API returned error %s: %s", res.status_code, res.text)
            except Exception as e:
                _logger.warning("Could not apply pipeline on test label: %s", str(e))

        self.print_zpl_stream(zpl)
        msg = _("Test label sent to printer '%s'") % self.name
        if applied_pipeline:
            msg += _(" (ZplFlow pipeline '%s' applied)") % pipeline_id
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Print Success"),
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }

    def print_zpl_stream(self, zpl_data):
        self.ensure_one()
        raw_bytes = zpl_data.encode('utf-8') if isinstance(zpl_data, str) else zpl_data
        _logger.info("=== ZplFlow RAW ZPL SENT TO %s (%s, %d bytes) ===\n%s\n=== END RAW ZPL ===",
                     self.name, self.protocol, len(raw_bytes), raw_bytes.decode('utf-8', errors='replace'))
        if self.protocol == 'ipps':
            return self._print_via_ipps(raw_bytes)
        elif self.protocol == 'raw_tcp':
            return self._print_via_raw_tcp(raw_bytes)
        elif self.protocol == 'usb_direct':
            return self._print_via_usb(raw_bytes)
        raise UserError(_("Unsupported protocol: %s") % self.protocol)

    def _print_via_ipps(self, raw_bytes):
        target_url = f"https://{self.ip_address}:{self.port}/ipp/print"
        printer_uri = f"ipps://{self.ip_address}:{self.port}/ipp/print"
        payload = IPPPayloadBuilder.build_print_job(
            printer_uri=printer_uri,
            zpl_data=raw_bytes,
            job_name="odoo-print-job"
        )
        if not self.tls_verify and urllib3:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        try:
            res = requests.post(
                target_url,
                data=payload,
                headers={'Content-Type': 'application/ipp'},
                verify=self.tls_verify,
                timeout=8.0
            )
            res.raise_for_status()
            if len(res.content) >= 4:
                status_code = struct.unpack('>H', res.content[2:4])[0]
                if status_code != 0x0000:
                    raise UserError(_("Zebra IPP error code: 0x%04X") % status_code)
            return True
        except Exception as e:
            raise UserError(_("Failed IPPS print to %s: %s") % (self.name, str(e)))

    def _print_via_raw_tcp(self, raw_bytes):
        try:
            with socket.create_connection((self.ip_address, self.port), timeout=5.0) as sock:
                sock.sendall(raw_bytes)
            return True
        except Exception as e:
            raise UserError(_("Failed TCP print to %s: %s") % (self.name, str(e)))

    def _print_via_usb(self, raw_bytes):
        try:
            with open(self.device_path, 'wb') as printer:
                printer.write(raw_bytes)
            return True
        except Exception as e:
            raise UserError(_("Failed USB print to %s: %s") % (self.name, str(e)))

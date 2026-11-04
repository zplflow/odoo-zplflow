# -*- coding: utf-8 -*-
"""Polymorphic Zebra thermal printer model supporting IPPS, raw TCP and USB."""

import socket
import struct
import logging

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
    _description = 'Zebra Thermal Printer via zplflow'

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
    pipeline_id = fields.Char(string='Default zplflow Pipeline ID')
    active = fields.Boolean(string='Active', default=True)

    def print_zpl_stream(self, zpl_data):
        self.ensure_one()
        raw_bytes = zpl_data.encode('utf-8') if isinstance(zpl_data, str) else zpl_data
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

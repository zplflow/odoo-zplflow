# -*- coding: utf-8 -*-
"""Stock transfer extension exposing a zplflow thermal printer and label action."""

import logging
import base64

try:
    import requests
except ImportError:
    requests = None

try:
    from odoo import models, fields, _
    from odoo.exceptions import UserError
except ImportError:
    class models:
        class Model:
            """Minimal stand-in for ``odoo.models.Model`` used outside Odoo."""

            def ensure_one(self):
                return self

    class fields:
        @staticmethod
        def Many2one(*args, **kwargs):
            return kwargs

    def _(msg):
        return msg

    class UserError(Exception):
        pass

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    zplflow_printer_id = fields.Many2one(
        'zplflow.printer',
        string='ZplFlow Thermal Printer',
        help='Printer used for automatic thermal shipping label dispatch via ZplFlow'
    )

    def _generate_default_zpl_label(self):
        self.ensure_one()
        partner = self.partner_id
        partner_name = (partner.name or 'N/A').replace('^', '')
        street = (partner.street or '').replace('^', '')
        city_zip = f"{partner.zip or ''} {partner.city or ''}".strip().replace('^', '')
        country = (partner.country_id.name if partner.country_id else '').replace('^', '')

        origin = (self.origin or 'Direct Transfer').replace('^', '')
        carrier = getattr(self, 'carrier_id', None)
        carrier_name = (carrier.name if carrier else 'Standard Delivery').replace('^', '')
        
        move_lines = getattr(self, 'move_ids_without_package', None) or getattr(self, 'move_ids', [])
        items_count = len(move_lines)

        zpl = f"""^XA
^PW812
^LL1218
^BY2,3,100
^FO40,40^GB732,1138,4^FS
^FO70,70^A0N,40,40^FDSHIPPING LABEL^FS
^FO70,120^A0N,26,26^FDCarrier: {carrier_name}^FS
^FO70,160^GB672,2,2^FS
^FO70,190^A0N,24,24^FDShip To:^FS
^FO70,225^A0N,32,32^FD{partner_name[:35]}^FS
^FO70,270^A0N,26,26^FD{street[:40]}^FS
^FO70,305^A0N,26,26^FD{city_zip[:40]}^FS
^FO70,340^A0N,26,26^FD{country[:40]}^FS
^FO70,385^GB672,2,2^FS
^FO70,410^A0N,24,24^FDTransfer: {self.name}^FS
^FO70,445^A0N,24,24^FDOrigin: {origin}^FS
^FO70,500^BCN,110,Y,N,N^FD{self.name}^FS
^FO70,680^GB672,2,2^FS
^FO70,710^A0N,22,22^FDItems: {items_count} line(s)^FS
^FO70,745^A0N,20,20^FDOdoo WMS - Printed via ZplFlow Bridge^FS
^XZ"""
        return zpl

    def action_print_zplflow_label(self):
        self.ensure_one()
        printer = self.zplflow_printer_id
        if not printer:
            # Auto-assign if exactly one active printer exists
            active_printers = self.env['zplflow.printer'].search([('active', '=', True)])
            if len(active_printers) == 1:
                printer = active_printers[0]
                self.zplflow_printer_id = printer
            else:
                raise UserError(_("Please configure or select a ZplFlow Thermal Printer for this transfer."))

        # Generate base ZPL shipping label
        zpl_data = self._generate_default_zpl_label()

        # Check if cloud pipeline is configured to transform the label
        applied_pipeline = False
        api_key = self.env['ir.config_parameter'].sudo().get_param('zplflow.api_key')
        api_url = (self.env['ir.config_parameter'].sudo().get_param('zplflow.api_url') or 'https://api.zplflow.io').rstrip('/')
        pipeline_id = printer.pipeline_id or self.env['ir.config_parameter'].sudo().get_param('zplflow.default_pipeline_id')

        if api_key and pipeline_id and requests:
            try:
                _logger.info("Calling zplflow cloud pipeline '%s' at %s", pipeline_id, api_url)
                zpl_b64 = base64.b64encode(zpl_data.encode('utf-8')).decode('ascii')
                headers = {
                    'Authorization': f"Bearer {api_key}",
                    'X-API-Key': api_key,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
                payload = {
                    'documents': [
                        {
                            'zpl_base64': zpl_b64,
                            'variables': {
                                'transfer_name': self.name or '',
                                'customer': (self.partner_id.name or '').replace('^', ''),
                                'origin': (self.origin or '').replace('^', ''),
                            },
                        }
                    ]
                }
                res = requests.post(
                    f"{api_url}/v1/pipelines/{pipeline_id}/apply",
                    headers=headers,
                    json=payload,
                    timeout=8.0
                )
                _logger.info("zplflow API response status: %s", res.status_code)
                if res.status_code == 200:
                    data = res.json()
                    docs = data.get('documents') or []
                    if docs and 'zpl_base64' in docs[0]:
                        zpl_data = base64.b64decode(docs[0]['zpl_base64']).decode('utf-8')
                        applied_pipeline = True
                        _logger.info(
                            "Pipeline '%s' successfully transformed label for %s (tokens charged: %s)",
                            pipeline_id, self.name, data.get('tokens_charged', 0)
                        )
                else:
                    _logger.warning("zplflow API returned error status %s: %s", res.status_code, res.text)
            except Exception as e:
                _logger.error("Failed to apply zplflow pipeline: %s", str(e))

        printer.print_zpl_stream(zpl_data)

        msg = _("Thermal shipping label for %s sent to printer '%s'") % (self.name, printer.name)
        if applied_pipeline:
            msg += _(" (ZplFlow pipeline '%s' applied)") % pipeline_id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Label Sent"),
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }

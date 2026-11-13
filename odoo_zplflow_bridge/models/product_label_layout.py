# -*- coding: utf-8 -*-
"""Product label layout extension to send labels directly to ZplFlow thermal printers."""

import base64
import logging
import uuid

try:
    import requests
except ImportError:
    requests = None

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    zplflow_printer_id = fields.Many2one(
        'zplflow.printer',
        string='ZplFlow Thermal Printer',
        default=lambda self: self._default_zplflow_printer_id(),
        help='Select a thermal printer to send labels directly without saving a file to disk.'
    )

    @api.model
    def _default_zplflow_printer_id(self):
        active_printers = self.env['zplflow.printer'].search([('active', '=', True)])
        if len(active_printers) == 1:
            return active_printers[0]
        return False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # If an active ZplFlow printer exists, default to ZPL format
        active_printers = self.env['zplflow.printer'].search([('active', '=', True)], limit=1)
        if active_printers and 'print_format' in fields_list:
            res['print_format'] = 'zpl'
            res['zplflow_printer_id'] = active_printers.id
        return res

    @api.onchange('zplflow_printer_id')
    def _onchange_zplflow_printer_id(self):
        if self.zplflow_printer_id and self.print_format not in ('zpl', 'zplxprice'):
            self.print_format = 'zpl'

    def process(self):
        self.ensure_one()
        # If no ZplFlow printer is selected, fall back to standard Odoo download action
        if not self.zplflow_printer_id:
            return super().process()

        printer = self.zplflow_printer_id
        xml_id, data = self._prepare_report_data()
        if not xml_id:
            raise UserError(_("Unable to find report template for %s format") % self.print_format)

        report = self.env.ref(xml_id)
        docids = self.product_tmpl_ids.ids if self.product_tmpl_ids else self.product_ids.ids

        # 1. Native ZPL format selected
        if 'zpl' in self.print_format:
            zpl_bytes, _report_ext = report._render(xml_id, docids, data=data)
            zpl_content = zpl_bytes.decode('utf-8')

            # Ensure barcode width module is calibrated with ^BY2 to fit thermal labels
            if '^BY' not in zpl_content and '^XA' in zpl_content:
                zpl_content = zpl_content.replace('^XA', '^XA\n^BY2,3,100')

            # Apply ZplFlow cloud pipeline if configured
            applied_pipeline = False
            api_key = self.env['ir.config_parameter'].sudo().get_param('zplflow.api_key')
            api_url = (self.env['ir.config_parameter'].sudo().get_param('zplflow.api_url') or 'https://api.zplflow.io').rstrip('/')
            pipeline_id = printer.pipeline_id or self.env['ir.config_parameter'].sudo().get_param('zplflow.default_pipeline_id')

            if api_key and pipeline_id and requests:
                try:
                    _logger.info("Applying ZplFlow pipeline '%s' to product label", pipeline_id)
                    zpl_b64 = base64.b64encode(zpl_content.encode('utf-8')).decode('ascii')
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
                                'variables': {
                                    'quantity': str(self.custom_quantity),
                                    'format': self.print_format,
                                },
                            }
                        ]
                    }
                    res = requests.post(
                        f"{api_url}/v1/pipelines/{pipeline_id}/apply",
                        json=payload,
                        headers=headers,
                        timeout=8.0
                    )
                    if res.status_code == 200:
                        data_res = res.json()
                        docs = data_res.get('documents') or []
                        if docs and 'zpl_base64' in docs[0]:
                            zpl_content = base64.b64decode(docs[0]['zpl_base64']).decode('utf-8')
                            applied_pipeline = True
                            _logger.info("ZplFlow pipeline successfully transformed product label")
                except Exception as e:
                    _logger.warning("Could not apply pipeline to product label: %s", str(e))

            printer.print_zpl_stream(zpl_content)

            product_name = self.product_tmpl_ids[:1].name if self.product_tmpl_ids else (self.product_ids[:1].display_name if self.product_ids else '')
            msg = _("Sent %d product label(s) for '%s' to printer '%s'") % (
                self.custom_quantity, product_name, printer.name
            )
            if applied_pipeline:
                msg += _(" (ZplFlow pipeline '%s' applied)") % pipeline_id

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Labels Printed"),
                    'message': msg,
                    'type': 'success',
                    'sticky': False,
                }
            }

        # 2. PDF layout selected (e.g. Dymo, 2x7, 4x7) -> convert via ZplFlow API
        api_key = self.env['ir.config_parameter'].sudo().get_param('zplflow.api_key')
        api_url = (self.env['ir.config_parameter'].sudo().get_param('zplflow.api_url') or 'https://api.zplflow.io').rstrip('/')
        if api_key and requests:
            try:
                pdf_bytes, _report_ext = report._render(xml_id, docids, data=data)
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'X-API-Key': api_key,
                    'Idempotency-Key': str(uuid.uuid4()),
                    'Content-Type': 'application/pdf',
                }
                dpi = int(printer.dpi or 203)
                res = requests.post(
                    f"{api_url}/v1/convert/pdf-to-zpl?dpi={dpi}",
                    data=pdf_bytes,
                    headers=headers,
                    timeout=15.0
                )
                if res.status_code == 200:
                    data_json = res.json()
                    pages = data_json.get('pages') or []
                    for page in pages:
                        b64 = page.get('zpl_base64')
                        if b64:
                            zpl_page = base64.b64decode(b64).decode('utf-8')
                            printer.print_zpl_stream(zpl_page)

                    product_name = self.product_tmpl_ids[:1].name if self.product_tmpl_ids else (self.product_ids[:1].display_name if self.product_ids else '')
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _("Labels Printed"),
                            'message': _("Converted PDF and sent %d label(s) for '%s' to printer '%s'") % (
                                self.custom_quantity, product_name, printer.name
                            ),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    _logger.warning("ZplFlow PDF-to-ZPL conversion returned error %s: %s", res.status_code, res.text)
            except Exception as e:
                _logger.error("ZplFlow PDF-to-ZPL conversion failed: %s", str(e))

        # Fallback guidance if PDF conversion couldn't proceed
        raise UserError(_(
            "To print directly to your Zebra printer without downloading a file, "
            "please select 'ZPL Labels' or 'ZPL Labels with price' as the Format."
        ))

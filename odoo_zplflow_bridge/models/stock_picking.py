# -*- coding: utf-8 -*-
"""Stock transfer extension exposing a zplflow thermal printer and label action."""

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


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    zplflow_printer_id = fields.Many2one(
        'zplflow.printer',
        string='zplflow Thermal Printer',
        help='Printer used for automatic thermal shipping label dispatch'
    )

    def action_print_zplflow_label(self):
        self.ensure_one()
        if not self.zplflow_printer_id:
            raise UserError(_("No zplflow printer configured for this transfer."))
        return True

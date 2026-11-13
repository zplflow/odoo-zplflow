# -*- coding: utf-8 -*-
"""Settings exposed in Odoo's General Settings for the zplflow bridge."""

try:
    from odoo import models, fields
except ImportError:
    class models:
        class TransientModel:
            pass

    class fields:
        @staticmethod
        def Char(**kwargs):
            return kwargs


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    zplflow_api_url = fields.Char(
        string='ZplFlow API URL',
        default='https://api.zplflow.io',
        config_parameter='zplflow.api_url'
    )
    zplflow_api_key = fields.Char(
        string='ZplFlow API Key',
        config_parameter='zplflow.api_key'
    )
    zplflow_default_pipeline_id = fields.Char(
        string='ZplFlow Default Pipeline ID',
        config_parameter='zplflow.default_pipeline_id'
    )

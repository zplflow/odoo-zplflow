import unittest
import os
import ast


class TestOdoo16Compatibility(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    def test_manifest_version(self):
        manifest_path = os.path.join(self.base_dir, '__manifest__.py')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = ast.literal_eval(f.read())
        self.assertTrue(manifest['version'].startswith('16.0.'), "Version must start with 16.0.")

    def test_printer_views_attrs(self):
        view_path = os.path.join(self.base_dir, 'views', 'zplflow_printer_views.xml')
        with open(view_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("attrs=\"{'invisible':", content, "Odoo 16 printer view must use attrs")
        self.assertIn('<tree string=', content, "Odoo 16 printer view must use <tree> tag")

    def test_settings_view_app_settings_block(self):
        view_path = os.path.join(self.base_dir, 'views', 'res_config_settings_views.xml')
        with open(view_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('class="app_settings_block"', content, "Odoo 16 settings view must use app_settings_block")


if __name__ == '__main__':
    unittest.main()

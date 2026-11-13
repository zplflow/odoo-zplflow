import unittest
import os
import ast


class TestOdoo17Compatibility(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    def test_manifest_version(self):
        manifest_path = os.path.join(self.base_dir, '__manifest__.py')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = ast.literal_eval(f.read())
        self.assertTrue(manifest['version'].startswith('17.0.'), "Version must start with 17.0.")

    def test_printer_views_tree_tag(self):
        view_path = os.path.join(self.base_dir, 'views', 'zplflow_printer_views.xml')
        with open(view_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('<tree string=', content, "Odoo 17 printer view must use <tree> tag")
        self.assertIn('tree,form', content, "Odoo 17 view_mode must use tree,form")


if __name__ == '__main__':
    unittest.main()

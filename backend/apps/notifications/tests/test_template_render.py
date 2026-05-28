from django.test import SimpleTestCase

from apps.notifications.services.template_render import render_template, strip_html_to_plain


class TemplateRenderTests(SimpleTestCase):
    def test_replaces_variables(self):
        out = render_template('Hello {{name}}, ref {{ref}}', {'name': 'Ada', 'ref': 'X1'})
        self.assertEqual(out, 'Hello Ada, ref X1')

    def test_escapes_html_in_body(self):
        out = render_template('<p>{{msg}}</p>', {'msg': '<script>'}, escape_html=True)
        self.assertIn('&lt;script&gt;', out)
        self.assertNotIn('<script>', out)

    def test_missing_var_becomes_empty(self):
        out = render_template('Hi {{missing}}', {})
        self.assertEqual(out, 'Hi ')

    def test_strip_html_to_plain(self):
        plain = strip_html_to_plain('<p>Line one</p><p>Line two</p>')
        self.assertIn('Line one', plain)
        self.assertIn('Line two', plain)

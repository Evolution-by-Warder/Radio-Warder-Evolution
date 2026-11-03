import ast
import json
from pathlib import Path
import string
import unittest
from unittest.mock import patch
from WarderRadio import ROOT
from WarderRadio import i18n


class TranslationTests(unittest.TestCase):
    def test_entire_warder_language_union_and_all_keys_are_translated(self):
        expected = {'al', 'cs', 'de', 'el', 'en', 'es', 'et', 'fa', 'fr', 'hu', 'it',
                    'lt', 'nl', 'pl', 'pt', 'ro', 'ru', 'sk', 'tr', 'uk', 'zh'}
        self.assertEqual(set(i18n.SUPPORTED), expected)
        english = i18n.translations('en')
        self.assertEqual(len(english), 75)
        for code in expected:
            with self.subTest(code=code):
                translated = i18n.translations(code)
                self.assertEqual(set(translated), set(english))
                self.assertTrue(all(isinstance(s, str) and s.strip() for s in translated.values()))
                self.assertEqual(translated['Install update {version}?'].count('{version}'), 1)
                self.assertIn('0.2.0', translated['Install update {version}?'].format(version='0.2.0'))
                if code != 'en':
                    self.assertNotEqual(translated['Settings'], 'Settings')
                    self.assertNotEqual(translated['Update failed'], 'Update failed')

    def test_language_aliases_and_regional_codes(self):
        for code, expected in [('sq_AL', 'al'), ('al_AL', 'al'), ('cs-CZ', 'cs'),
                               ('cz_CZ', 'cs'), ('zh_CN', 'zh'), ('pt_BR', 'pt'),
                               ('fa_IR', 'fa'), ('zz_ZZ', 'en')]:
            self.assertEqual(i18n.language_code(code), expected)

    def test_all_static_ui_translation_keys_exist(self):
        english = i18n.translations('en')
        for path in Path(ROOT).glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 't' and node.args:
                    value = node.args[0]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        self.assertIn(value.value, english, (path.name, value.value))

    def test_language_changes_are_used_without_reimporting_plugin(self):
        with patch.object(i18n, 'language_code', return_value='de'):
            self.assertEqual(i18n.t('Settings'), 'Einstellungen')
        with patch.object(i18n, 'language_code', return_value='sk'):
            self.assertEqual(i18n.t('Settings'), 'Nastavenia')

"""Optional main-menu shortcut regression tests with no Enigma2 runtime."""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from WarderRadio import ROOT
from WarderRadio.model import Store
from WarderRadio import i18n


class Descriptor:
    WHERE_PLUGINMENU = 3
    WHERE_EXTENSIONSMENU = 1
    WHERE_MENU = 5

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class MainMenuTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        parent = types.ModuleType("Plugins")
        parent.__path__ = []
        child = types.ModuleType("Plugins.Plugin")
        child.PluginDescriptor = Descriptor
        with patch.dict(sys.modules, {"Plugins": parent, "Plugins.Plugin": child}):
            spec = importlib.util.spec_from_file_location(
                "WarderRadio._test_main_menu", os.path.join(ROOT, "plugin.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.plugin = module

    def test_disabled_by_default_and_existing_plugins_unchanged(self):
        store = Store(self.dir.name)
        self.assertFalse(store.show_main_menu)
        descriptors = self.plugin.Plugins()
        self.assertEqual([p.where for p in descriptors],
                         [Descriptor.WHERE_PLUGINMENU, Descriptor.WHERE_EXTENSIONSMENU, Descriptor.WHERE_MENU])
        self.assertEqual(descriptors[0].name, "Radio Warder Evolution")
        self.assertEqual(descriptors[1].name, "Radio Warder Evolution")
        with patch("WarderRadio.model.read_json", return_value={}):
            self.assertEqual(self.plugin.main_menu("mainmenu"), [])
            self.assertEqual(self.plugin.main_menu("system"), [])

    def test_menu_entry_requires_explicit_true_and_correct_menu(self):
        with patch("WarderRadio.model.read_json", return_value={"show_main_menu": "yes"}):
            self.assertEqual(self.plugin.main_menu("mainmenu"), [])
        with patch("WarderRadio.model.read_json", return_value={"show_main_menu": True}):
            self.assertEqual(self.plugin.main_menu("system"), [])
            entries = self.plugin.main_menu("mainmenu")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], "Radio by Warder")
        self.assertIs(entries[0][1], self.plugin.main)
        self.assertEqual(entries[0][2], "warder_radio_mainmenu")
        self.assertEqual(len(entries[0]), 4)

    def test_store_flag_preserves_existing_data(self):
        state = Store(self.dir.name)
        state.show_main_menu = True
        state.save()
        fresh = Store(self.dir.name)
        self.assertTrue(fresh.show_main_menu)
        fresh.show_main_menu = False
        fresh.save()
        self.assertFalse(Store(self.dir.name).show_main_menu)
        with open(state.path, encoding="utf-8") as stream:
            saved = json.load(stream)
        self.assertEqual(saved["schema"], 1)
        self.assertIn("favourites", saved)
        self.assertIn("history", saved)
        self.assertIn("custom", saved)

    def test_all_21_languages_have_full_toggle_translation(self):
        for lang in i18n.SUPPORTED:
            with self.subTest(lang=lang):
                with patch.object(i18n, "language_code", return_value=lang):
                    for key in ("Show in Enigma2 main menu", "Main menu setting saved", "Could not save setting"):
                        self.assertTrue(i18n.t(key).strip())


if __name__ == "__main__":
    unittest.main()

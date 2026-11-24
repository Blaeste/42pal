"""Settings in the first menu: the language, in the text and the full-screen interfaces.

A catalog put in a folder of the test is a language of the menu: no code
changes to add one (docs/plans/languages.md).
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from random import Random
from unittest import mock

import pal42.cli  # noqa: F401  (puts vendor/ in Python's path)
from pal42 import i18n
from pal42.cli.shell import SETTINGS, Shell
from pal42.cli.tui import MenuScreen, Pal42App, ScreenShell, capture_console
from pal42.cli.workspace import Workspace
from rich.console import Console
from textual.widgets import OptionList
from tests.test_cli import ECHO_CATALOG, ECHO_THEMES, FakeClock, Script
from tests.test_tui import FullScreenTest, quiet, screen_test

class SettingsTestCase(unittest.TestCase):
	"""A folder of catalogs with a made-up language, and a settings file of the test."""

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)
		(self.folder / "fr.json").write_text(json.dumps({"_name": "Français"}), encoding="utf-8")
		patcher = mock.patch("pal42.i18n.LOCALES_DIR", self.folder)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.addCleanup(i18n.set_language, "en")
		self.settings_file = self.folder / "settings.json"

	def saved(self):
		return json.loads(self.settings_file.read_text())

class TestTextSettings(SettingsTestCase):

	def run_shell(self, *answers):
		self.console = Console(file=io.StringIO(), width=100, color_system=None)
		script = Script(*answers)
		shell = Shell(self.console, script.ask, script.ask_password, Workspace(self.folder / "exam"),
			rng=Random(1), clock=FakeClock(), sleep=lambda seconds: None,
			catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		shell.settings_file = self.settings_file
		shell.run()
		return self.console.file.getvalue()

	def test_settings_is_the_last_choice_of_the_first_menu(self):
		# The login, then 4 (Settings: after the students, practice and testers), 2 (Français), then 5: quit.
		text = self.run_shell("", "pw", "4", "2", "5")
		self.assertIn("4. Settings", text)
		self.assertIn("5. Quit", text)
		self.assertIn("1. English", text)
		self.assertIn("2. Français", text)
		self.assertEqual(i18n.language(), "fr")
		self.assertEqual(self.saved(), {"language": "fr"})
		# Back to the first menu after the choice.
		self.assertEqual(text.count("What do you want to do?"), 2)

	def test_back_in_the_language_menu_changes_nothing(self):
		self.run_shell("", "pw", "4", "3", "5")
		self.assertEqual(i18n.language(), "en")
		self.assertFalse(self.settings_file.exists())

class TestScreenSettings(FullScreenTest, SettingsTestCase):

	def setUp(self):
		FullScreenTest.setUp(self)
		SettingsTestCase.setUp(self)

	def app(self):
		shell = ScreenShell(capture_console(), None, None, Workspace(self.root), rng=Random(1), clock=self.clock,
			sleep=lambda seconds: None, store=self.store, catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		app = quiet(Pal42App(shell, user="student"))
		app.settings_file = self.settings_file
		return app

	async def choose(self, pilot, value):
		screen = pilot.app.screen
		screen.query_one(OptionList).highlighted = [item[0] for item in screen.items].index(value)
		await pilot.press("enter")
		await pilot.pause()

	@screen_test
	async def test_settings_then_a_language_then_the_first_menu_again(self):
		app = self.app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			self.assertEqual(pilot.app.screen.items[-1][0], SETTINGS)
			await self.choose(pilot, SETTINGS)
			screen = pilot.app.screen
			self.assertIsInstance(screen, MenuScreen)
			self.assertEqual(screen.title, "Language")
			self.assertEqual([item[1] for item in screen.items], ["English", "Français"])
			await self.choose(pilot, "fr")
			self.assertEqual(i18n.language(), "fr")
			self.assertEqual(self.saved(), {"language": "fr"})
			self.assertEqual(pilot.app.screen.title, "What do you want to do?")

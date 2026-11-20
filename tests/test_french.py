"""42pal in French: the menus and the messages, with the real catalog pal42/locales/fr.json."""

import io
import tempfile
import unittest
from random import Random

import pal42.cli  # noqa: F401  (puts vendor/ in Python's path)
from pal42 import i18n
from pal42.cli import display
from pal42.cli.shell import COMMANDS, Shell
from pal42.cli.tui import Pal42App, ScreenShell, capture_console
from pal42.cli.workspace import Workspace
from rich.console import Console
from tests.test_cli import ECHO_CATALOG, ECHO_THEMES, FakeClock, Script
from tests.test_tui import FullScreenTest, quiet, screen_test

class FrenchTestCase(unittest.TestCase):

	def setUp(self):
		self.assertEqual(i18n.set_language("fr"), "fr")
		self.addCleanup(i18n.set_language, "en")

class TestFrenchText(FrenchTestCase):

	def test_the_first_menu_and_the_login_in_french(self):
		console = Console(file=io.StringIO(), width=100, color_system=None)
		script = Script("", "pw", "4")
		with tempfile.TemporaryDirectory() as root:
			shell = Shell(console, script.ask, script.ask_password, Workspace(root), rng=Random(1), clock=FakeClock(),
				sleep=lambda seconds: None, catalog=ECHO_CATALOG, themes=ECHO_THEMES)
			shell.run()
		text = console.file.getvalue()
		self.assertIn("Bienvenue", text)
		self.assertIn("Que veux-tu faire ?", text)
		self.assertIn("2. Entraînement", text)
		self.assertIn("3. Réglages", text)
		self.assertIn("langue : Français", text)
		self.assertIn("4. Quitter", text)
		self.assertIn("Au revoir !", text)
		self.assertIn("login :", script.prompts)

	def test_the_menus_stay_aligned_in_french(self):
		"""The choices are padded: their grey lines start in the same column."""
		lines = display.audience_menu({}, practice=True, progress=True, settings=True, language="Français")
		self.assertEqual(lines[1].index("un thème"), lines[2].index("tes exams"))
		self.assertEqual(lines[2].index("tes exams"), lines[3].index("langue"))

	def test_the_help_of_the_commands_in_french(self):
		console = Console(file=io.StringIO(), width=100, color_system=None)
		console.print(display.help_table(COMMANDS))
		text = console.file.getvalue()
		self.assertIn("Commandes", text)
		self.assertIn("corrige ton travail", text)
		# The names of the commands stay, like in the real examshell.
		self.assertIn("grademe", text)

class TestFrenchScreen(FullScreenTest, FrenchTestCase):

	def setUp(self):
		FullScreenTest.setUp(self)
		FrenchTestCase.setUp(self)

	@screen_test
	async def test_the_first_menu_of_the_full_screen_in_french(self):
		shell = ScreenShell(capture_console(), None, None, Workspace(self.root), rng=Random(1), clock=self.clock,
			sleep=lambda seconds: None, store=self.store, catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		app = quiet(Pal42App(shell, user="student"))
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			screen = pilot.app.screen
			self.assertEqual(screen.title, "Que veux-tu faire ?")
			self.assertEqual([item[1] for item in screen.items][-2:], ["Entraînement", "Réglages"])
			self.assertEqual(screen.last_label, "Quit")

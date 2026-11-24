"""Going back to the menus from an exam or a practice, and pasting in the command line.

A wrong click in the menus starts an exam the student did not want: Back
(Escape on the screen, back or b in the text interface) asks first, then
goes back to the first menu. An exam with no grademe yet is forgotten; one
with grademe is kept in the history as abandoned.
"""

import io
import unittest
from pathlib import Path
from random import Random
import tempfile

import pal42.cli  # noqa: F401  (puts vendor/ in Python's path)
from pal42.cli.shell import Shell
from pal42.cli.tui import MenuScreen, SessionScreen
from pal42.cli.workspace import Workspace
from pal42.session import SessionStore
from rich.console import Console
from tests.helpers import ECHO_OK
from tests.test_cli import ECHO_CATALOG, ECHO_THEMES, FakeClock, Script
from tests.test_tui import FullScreenTest, log_text, screen_test

class TestPasteInTheCommandLine(FullScreenTest):

	@screen_test
	async def test_ctrl_v_pastes_the_first_line_only(self):
		"""After a report, the clipboard holds the whole report: one line of it is pasted."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login_to_exams(pilot)
			await pilot.press("enter", "enter")
			await pilot.pause()
			command = app.screen.query_one("#command")
			app._clipboard = "grademe\n# 42pal report\n" + "a line of the report\n" * 500
			await pilot.press("ctrl+v")
			await pilot.pause()
			self.assertEqual(command.value, "grademe")

class TestBackOnTheScreen(FullScreenTest):

	async def to_session(self, pilot):
		"""Revision, level 1: the session screen."""
		await self.login_to_exams(pilot)
		await pilot.press("enter", "enter")
		await pilot.pause()
		self.assertIsInstance(pilot.app.screen, SessionScreen)

	@screen_test
	async def test_escape_then_back_forgets_an_exam_with_no_grademe(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_session(pilot)
			await pilot.press("escape")
			await pilot.pause()
			self.assertIsInstance(app.screen, MenuScreen)
			self.assertEqual(app.screen.title, "Back to the menus?")
			self.assertIn("no grademe", app.screen.items[0][3])
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "What do you want to do?")
			self.assertIsNone(self.store.load())
			self.assertEqual(self.store.history(), [])

	@screen_test
	async def test_back_after_a_grademe_keeps_the_exam_as_abandoned(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_session(pilot)
			await self.type(pilot, "grademe")
			await self.wait_grading(pilot, app.screen)
			await self.type(pilot, "back")
			self.assertIn("abandoned", app.screen.items[0][3])
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "What do you want to do?")
			self.assertEqual([entry["end"] for entry in self.store.history()], ["abandoned"])

	@screen_test
	async def test_escape_twice_stays_in_the_exam(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_session(pilot)
			await pilot.press("escape")
			await pilot.pause()
			await pilot.press("escape")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			self.assertIsNotNone(self.store.load())

	@screen_test
	async def test_back_from_a_practice_goes_to_the_first_menu(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			# The first menu: the students, then Practice.
			await pilot.press("down", "enter")
			await pilot.pause()
			await pilot.press("enter")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			self.assertTrue(app.practice)
			await pilot.press("escape")
			await pilot.pause()
			self.assertIn("nothing is lost", app.screen.items[0][3])
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "What do you want to do?")
			self.assertFalse(app.practice)
			# And an exam can start from there.
			await pilot.press("enter")
			await pilot.pause()
			await pilot.press("enter", "enter")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			self.assertFalse(app.practice)

class TestBackInText(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.root = Path(folder.name)
		self.store = SessionStore(self.root / ".42pal")

	def run_shell(self, *answers):
		self.console = Console(file=io.StringIO(), width=100, color_system=None)
		self.script = Script(*answers)
		shell = Shell(self.console, self.script.ask, self.script.ask_password, Workspace(self.root / "exam"),
			rng=Random(1), clock=FakeClock(), sleep=lambda seconds: None, store=self.store, catalog=ECHO_CATALOG,
			themes=ECHO_THEMES)
		shell.run()
		return shell, self.console.file.getvalue()

	def asked(self, words):
		"""True if a question asked holds `words`."""
		return any(words in prompt for prompt in self.script.prompts)

	def test_back_and_yes_goes_to_the_first_menu_and_forgets_the_exam(self):
		# Login, students, revision, level 1, then back, y, and 4: quit.
		shell, text = self.run_shell("", "pw", "1", "2", "", "back", "y", "4")
		self.assertTrue(self.asked("Back to the menus? Nothing is kept: no grademe was made yet."))
		self.assertEqual(text.count("What do you want to do?"), 2)
		self.assertIsNone(shell.exam)
		self.assertIsNone(self.store.load())
		self.assertEqual(self.store.history(), [])

	def test_back_and_no_stays_in_the_exam(self):
		shell, text = self.run_shell("", "pw", "1", "2", "", "b", "n", "status")
		self.assertEqual(text.count("What do you want to do?"), 1)
		self.assertIn("Time spent", text)

	def test_back_from_a_practice_goes_to_the_first_menu(self):
		# Login, Practice (2), a theme (1), then back, y, then 4: quit.
		shell, text = self.run_shell("", "pw", "2", "1", "back", "y", "4")
		self.assertEqual(text.count("What do you want to do?"), 2)
		self.assertIn("Goodbye!", text)

	def test_back_after_a_grademe_keeps_the_exam_as_abandoned(self):
		(self.root / "exam" / "rendu" / "echo_first").mkdir(parents=True)
		# Quit is 5 then: the first menu offers Progress after a grademe.
		shell, text = self.run_shell("", "pw", "1", "2", "", "grademe", "back", "y", "5")
		self.assertTrue(self.asked("abandoned"))
		self.assertEqual([entry["end"] for entry in self.store.history()], ["abandoned"])

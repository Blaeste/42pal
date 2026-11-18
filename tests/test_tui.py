"""Tests of the full-screen interface (pal42.cli.tui), driven by textual's pilot.

The pilot runs the app in a virtual terminal and presses keys in it; the
shells behind are the same as in the text interface.

Run all the tests from the project root with: python3 -m unittest -v
"""

import asyncio
import functools
import tempfile
import unittest
from pathlib import Path
from random import Random

import pal42.cli  # noqa: F401  (puts vendor/ in Python's path, for textual)
from pal42.cli.tui import (
	LoginScreen, MenuScreen, Pal42App, ScreenPracticeShell, ScreenShell, SessionScreen,
	capture_console,
)
from pal42.cli.workspace import Workspace
from pal42.session import Session, SessionStore
from tests.helpers import ECHO_OK
from tests.test_cli import ECHO_CATALOG, ECHO_THEMES, FakeClock

def log_text(screen):
	"""Everything the session screen wrote in its log."""
	return "\n".join(line.text for line in screen.query_one("#log").lines)

def screen_test(method):
	"""Run an async test with asyncio.run.

	unittest's IsolatedAsyncioTestCase runs its loop in debug mode, which
	makes textual several times slower.
	"""
	@functools.wraps(method)
	def run(self):
		asyncio.run(method(self))
	return run

def quiet(app):
	"""The app without its animations: the pilot would wait for each one."""
	app.animation_level = "none"
	return app

class FullScreenTest(unittest.TestCase):
	"""A temporary workspace and store for each test."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name) / "42pal_exam"
		self.store = SessionStore(Path(self.tmp.name) / ".42pal")
		self.clock = FakeClock()

	def tearDown(self):
		self.tmp.cleanup()

	def exam_app(self, catalog=ECHO_CATALOG, themes=ECHO_THEMES):
		shell = ScreenShell(capture_console(), None, None, Workspace(self.root), rng=Random(1),
			clock=self.clock, sleep=lambda seconds: None, store=self.store,
			catalog=catalog, themes=themes)
		return quiet(Pal42App(shell, user="student"))

	async def type(self, pilot, text):
		"""Type `text` in the command line, then Enter."""
		await pilot.press(*text, "enter")
		await pilot.pause()

	async def wait_grading(self, pilot, screen):
		"""Wait until the grading thread is done (10 seconds at most)."""
		for _ in range(200):
			await pilot.pause(0.05)
			if not screen.busy:
				return
		self.fail("the grading never ended")

	async def login(self, pilot):
		"""Enter twice: the login given, then any password."""
		await pilot.pause()
		await pilot.press("enter", "enter")
		await pilot.pause()

class TestExamScreens(FullScreenTest):
	"""Login, menus, then the session screen."""

	@screen_test
	async def test_login_then_mode_and_level_then_the_subject(self):
		"""One exam only: the mode menu comes first; revision asks the level."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await pilot.pause()
			self.assertIsInstance(app.screen, LoginScreen)
			await self.login(pilot)
			self.assertIsInstance(app.screen, MenuScreen)
			self.assertEqual(app.screen.title, "Exam Rank 02 · mode")
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Exam Rank 02 · starting level")
			await pilot.press("enter")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			self.assertEqual((app.shell.mode, app.shell.level), ("revision", 1))
			self.assertEqual(app.shell.user, "student")

	@screen_test
	async def test_commands_go_to_the_shell_and_their_output_to_the_log(self):
		"""status shows the level; a grademe of a right rendu passes, in a thread."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			await pilot.press("enter", "enter")
			await pilot.pause()
			await self.type(pilot, "s")
			self.assertRegex(log_text(app.screen), r"Level\s+1 of 4")
			rendu = self.root / "rendu" / app.shell.variant.name
			(rendu / "echo_first.c").write_text(ECHO_OK, encoding="utf-8")
			await self.type(pilot, "grademe")
			await self.wait_grading(pilot, app.screen)
			self.assertIn("OK", log_text(app.screen))
			self.assertEqual(app.shell.level, 2)

	@screen_test
	async def test_up_and_down_go_through_the_commands_typed(self):
		"""Up brings back status, then grademe... ; down goes back to what was being typed."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			await pilot.press("enter", "enter")
			await pilot.pause()
			command = app.screen.query_one("#command")
			await self.type(pilot, "help")
			await self.type(pilot, "status")
			await self.type(pilot, "status")
			await pilot.press("h", "e")
			await pilot.press("up")
			self.assertEqual(command.value, "status")
			await pilot.press("up")
			self.assertEqual(command.value, "help")
			await pilot.press("up")
			self.assertEqual(command.value, "help")
			await pilot.press("down", "down")
			self.assertEqual(command.value, "he")
			await pilot.press("backspace", "backspace", "up", "enter")
			await pilot.pause()
			self.assertEqual(log_text(app.screen).count("examshell> status"), 3)

	@screen_test
	async def test_exam_mode_skips_the_level_menu_and_finish_ends(self):
		"""Exam mode starts at level 1; finish, then Enter leaves with the summary."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			await pilot.press("up", "enter")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			self.assertEqual(app.shell.mode, "exam")
			await self.type(pilot, "finish")
			self.assertIn("End of the exam", log_text(app.screen))
			await pilot.press("enter")
			await pilot.pause()
		self.assertIn("End of the exam", app.return_value)
		self.assertEqual(self.store.history()[0]["end"], "finish")

	@screen_test
	async def test_the_menu_does_not_move_when_the_details_change(self):
		"""Exam, Revision and Back have details of different lengths: the card stays."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			card = app.screen.query_one(".card")
			places = set()
			for key in ["up", "down", "down", "up"]:
				await pilot.press(key)
				await pilot.pause()
				places.add((card.region.y, app.screen.query_one(".details").region.height))
			self.assertEqual(len(places), 1, places)

	@screen_test
	async def test_the_password_field_says_nothing(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await pilot.pause()
			self.assertEqual(app.screen.query_one("#password").placeholder, "")

	@screen_test
	async def test_escape_in_the_first_menu_quits(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			await pilot.press("escape")
			await pilot.pause()
		self.assertIsNone(app.return_value)
		self.assertIsNone(app.shell.exam)

	@screen_test
	async def test_back_goes_to_the_menu_before(self):
		"""The real exams: piscine, then Back from the exams: who are you again."""
		app = self.exam_app(catalog=None, themes=None)
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			self.assertEqual(app.screen.title, "Who are you?")
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Choose your exam")
			await pilot.press("escape")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Who are you?")

	@screen_test
	async def test_a_saved_exam_can_be_resumed(self):
		"""Resume: the same level and subject as when the terminal was closed."""
		self.store.save(Session(
			exam="rank02", level=2, variant="echo_first#5", started_at=self.clock.now - 600,
			mode="exam", attempts=2, oks=1, failures=0, passed_levels=[1],
		))
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			self.assertEqual(app.screen.title, "Resume your exam?")
			await pilot.press("enter")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			self.assertEqual((app.shell.level, app.shell.variant.id), (2, "echo_first#5"))

class TestUpdateScreen(FullScreenTest):
	"""The update found at launch, offered after the login."""

	@screen_test
	async def test_update_now_pulls_then_restarts(self):
		from pal42.cli.tui import RESTART
		from pal42.update import Update
		from tests.test_cli import FakeCheck
		app = self.exam_app()
		app.update_check = FakeCheck(Update(3, ("feat: add a",)))
		pulls = []
		app.updater = lambda: pulls.append(1) or (True, "")
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			self.assertEqual(app.screen.title, "A new version of 42pal")
			await pilot.press("enter")
			for _ in range(100):
				await pilot.pause(0.05)
				if pulls and app.return_value is RESTART:
					break
		self.assertEqual(pulls, [1])
		self.assertIs(app.return_value, RESTART)

	@screen_test
	async def test_not_now_goes_to_the_menus(self):
		from pal42.update import Update
		from tests.test_cli import FakeCheck
		app = self.exam_app()
		app.update_check = FakeCheck(Update(1, ("fix: b",)))
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			await pilot.press("down", "enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Exam Rank 02 · mode")

class TestPracticeScreens(FullScreenTest):
	"""./42pal practice in full screen."""

	@screen_test
	async def test_theme_menu_then_next_subject(self):
		shell = ScreenPracticeShell(capture_console(), None, Workspace(self.root), rng=Random(1),
			catalog=ECHO_CATALOG, themes=ECHO_THEMES, sleep=lambda seconds: None)
		app = quiet(Pal42App(shell, practice=True))
		async with app.run_test(size=(100, 40)) as pilot:
			await pilot.pause()
			self.assertEqual(app.screen.title, "Choose a theme to practise")
			await pilot.press("enter")
			await pilot.pause()
			self.assertIsInstance(app.screen, SessionScreen)
			first = shell.variant.id
			await self.type(pilot, "n")
			self.assertNotEqual(shell.variant.id, first)
			await self.type(pilot, "f")
			self.assertIn("Practice summary", log_text(app.screen))

class TestLinks(FullScreenTest):
	"""Paths and web addresses open with a click."""

	def test_rich_links_and_web_addresses_become_clickable(self):
		"""A file link of the shell, and an https address, get a click action."""
		from rich.text import Text
		from pal42.cli.tui import clickable
		text = clickable(Text.from_markup(
			"Trace: [link=file:///tmp/x/01_a.trace]~/x/01_a.trace[/link] see https://42.fr/en now"))
		actions = {span.style.meta.get("@click") for span in text.spans
			if not isinstance(span.style, str) and span.style.meta}
		self.assertIn("app.open_link('/tmp/x/01_a.trace')", actions)
		self.assertIn("app.open_link('https://42.fr/en')", actions)

	@screen_test
	async def test_open_link_runs_the_opener_of_the_system(self):
		"""xdg-open (open on macOS) gets the path; a notification says it."""
		app = self.exam_app()
		launched = []
		app.launch = launched.append
		async with app.run_test(size=(100, 40)) as pilot:
			app.action_open_link("/tmp/somewhere")
			await pilot.pause()
		self.assertEqual(launched[0][-1], "/tmp/somewhere")
		self.assertIn(launched[0][0], ("xdg-open", "open"))

	@screen_test
	async def test_the_paths_of_the_subject_are_clickable(self):
		"""Read it and Hand in open the subject file and the rendu folder."""
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			await pilot.press("enter", "enter")
			await pilot.pause()
			where = app.screen.query_one("#subject").content.renderables[0]
			actions = [span.style.meta["@click"] for span in where.spans
				if not isinstance(span.style, str) and "@click" in span.style.meta]
			name = app.shell.variant.name
			self.assertTrue(any(f"subjects/{name}/subject.en.txt" in action for action in actions))
			self.assertTrue(any(f"rendu/{name}" in action for action in actions))
			# A real click on the path, after "Read it  ", opens the subject.
			launched = []
			app.launch = launched.append
			await pilot.click("#subject", offset=(12, 0))
			await pilot.pause()
			self.assertTrue(launched and launched[0][-1].endswith(f"{name}/subject.en.txt"), launched)

class TestPlainLinks(unittest.TestCase):
	"""The text interface: the paths of the subject panel are terminal links."""

	def test_subject_panel_links_its_paths(self):
		from rich.console import Console
		from pal42.cli import display
		from pal42.exam import load_exam
		from pal42.variant import draw
		exam = load_exam("rank02", catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		variant = draw(ECHO_CATALOG.exercises["echo_first"], 1)
		panel = display.subject_panel(exam, 1, variant, Path("/tmp/s/subject.en.txt"), Path("/tmp/r"))
		console = Console(file=__import__("io").StringIO(), force_terminal=True, width=100)
		console.print(panel)
		output = console.file.getvalue()
		self.assertIn("file:///tmp/s/subject.en.txt", output)
		self.assertIn("file:///tmp/r", output)

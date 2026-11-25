"""Testers in the first menu: a tester downloaded when the student agrees, the folder asked, the results shown.

The tester is the fake one of tests/test_testers.py, cloned from a git
repository in a temporary folder: no network.
"""

import io
import json
import os
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from random import Random
from unittest import mock

import pal42.cli  # noqa: F401  (puts vendor/ in Python's path)
from pal42 import i18n, testers
from pal42.cli.shell import TESTERS as TESTERS_CHOICE, Shell, suggest_folder
from pal42.cli.tui import FolderScreen, MenuScreen, TesterScreen
from pal42.cli.workspace import Workspace
from rich.console import Console
from tests.test_cli import ECHO_CATALOG, ECHO_THEMES, FakeClock, Script
from tests.test_testers import fake_tester, new_tag, results
from tests.test_tui import FullScreenTest, log_text, screen_test

# The first menu with the catalog of the tests: 1 the students, 2 Practice,
# 3 Testers, 4 Settings, 5 Quit. The menu of the testers: 1 libfterator, 2 Back.
TESTERS, QUIT = "3", "5"
LIBFTERATOR, BACK = "1", "2"
# The menu after the results: 1 Run again, 2 Another folder, 3 Back.
AGAIN, ANOTHER, DONE = "1", "2", "3"

class TestersTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)
		self.tester, self.repo = fake_tester(self.folder)
		self.testers_root = self.folder / "testers"
		self.settings = self.folder / "settings.json"
		self.project = self.folder / "libft"
		self.project.mkdir()
		(self.project / "libft.h").write_text("")
		(self.project / "result.json").write_text(json.dumps(results()))

	def configure(self, shell, tester=None):
		"""The testers of the test, kept in its folder; the settings too; the projects looked for in it."""
		shell.settings_file = self.settings
		shell.testers_root = self.testers_root
		shell.tester_list = (tester or self.tester,)
		shell.testers_environ = {"PATH": os.environ["PATH"]}
		shell.projects_root = self.folder

class TestTheTextMenus(TestersTestCase):

	def run_shell(self, *answers, tester=None):
		console = Console(file=io.StringIO(), width=100, color_system=None)
		self.script = Script(*answers)
		shell = Shell(console, self.script.ask, self.script.ask_password, Workspace(self.folder / "exam"),
			rng=Random(1), clock=FakeClock(), sleep=lambda seconds: None, catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		self.configure(shell, tester)
		shell.run()
		return console.file.getvalue()

	def asked(self, words):
		return any(words in prompt for prompt in self.script.prompts)

	def test_testers_in_the_first_menu_then_back(self):
		text = self.run_shell("", "pw", TESTERS, BACK, QUIT)
		self.assertIn("3. Testers", text)
		self.assertIn("test your projects", text)
		self.assertIn("1. libfterator", text)
		self.assertEqual(text.count("What do you want to do?"), 2)
		self.assertIn("Goodbye!", text)

	def test_a_tester_this_system_cannot_run_is_offered_but_says_so(self):
		"""The menus stay the same on every system: macOS has no ld --wrap for libfterator."""
		with mock.patch.object(testers, "available", lambda tester: False):
			text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, BACK, QUIT)
		self.assertIn("3. Testers", text)
		self.assertIn("(Linux only)", text)
		self.assertIn("libfterator runs on Linux only.", text)
		self.assertFalse(self.testers_root.exists())

	def test_the_download_refused(self):
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "n", BACK, QUIT)
		self.assertTrue(self.asked("Download it now? (y/n)"))
		self.assertIn(self.tester.tag, text)
		self.assertEqual(testers.state(self.tester, self.testers_root), testers.MISSING)

	def test_downloaded_then_run_on_the_folder_given(self):
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "y", str(self.project), DONE, BACK, QUIT)
		self.assertEqual(testers.state(self.tester, self.testers_root), testers.READY)
		self.assertIn("Where is your libft?", text)
		self.assertIn("The subject 1/2", text)
		self.assertIn("No useless relink", text)
		self.assertIn("a second make rebuilds files", text)
		self.assertIn("The functions 3/4", text)
		self.assertIn("ft_strlcat", text)
		self.assertIn("dst_not_terminated", text)
		self.assertIn("read 1 byte(s) past the end", text)
		self.assertIn("Undefined cases, not counted", text)
		self.assertIn("✗ KO  subject 1/2 · tests 3/4", text)
		self.assertIn("Full log:", text)
		self.assertEqual(testers.last_project(self.tester, self.settings), str(self.project))

	def test_the_folder_of_the_last_time_is_offered(self):
		testers.install(self.tester, self.testers_root, environ={})
		testers.remember_project(self.tester, str(self.project), self.settings)
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "", DONE, BACK, QUIT)
		self.assertIn("✗ KO", text)

	def test_a_folder_that_does_not_exist_is_asked_again(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, str(self.folder / "nothing"), str(self.project), DONE,
			BACK, QUIT)
		self.assertIn("No folder here", text)
		self.assertIn("✗ KO", text)

	def test_back_goes_back_to_the_testers(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "back", BACK, QUIT)
		self.assertEqual(text.count("1. libfterator"), 2)
		self.assertNotIn("✗ KO", text)

	def test_the_projects_found_by_their_number(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "1", DONE, BACK, QUIT)
		self.assertIn("Where is your libft?", text)
		self.assertIn("1. " + str(self.project), text)
		self.assertIn("✗ KO", text)

	def test_cd_ls_then_test(self):
		testers.install(self.tester, self.testers_root, environ={})
		(self.folder / "plain").mkdir()
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, f"cd {self.folder}", "ls", "cd libft", "ls", "test",
			DONE, BACK, QUIT)
		self.assertIn("★ libft/", text)
		self.assertIn("plain/", text)
		self.assertIn("✓ a libft here", text)
		self.assertTrue(self.asked(f"{self.project} $"))
		self.assertIn("✗ KO", text)

	def test_cd_up_and_test_a_folder_named(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, f"cd {self.project}", "cd ..", "test libft",
			DONE, BACK, QUIT)
		self.assertTrue(self.asked(f"{self.folder} $"))
		self.assertIn("✗ KO", text)

	def test_enter_alone_tests_the_folder_of_the_project_you_are_in(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, f"cd {self.project}", "", DONE, BACK, QUIT)
		self.assertIn("✗ KO", text)

	def test_it_starts_in_the_home_folder_with_no_folder_tested_yet(self):
		testers.install(self.tester, self.testers_root, environ={})
		with mock.patch("pal42.cli.shell.Path.home", return_value=self.folder):
			text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "ls", "back", BACK, QUIT)
		self.assertTrue(self.asked("~ $"))
		self.assertIn("★ libft/", text)

	def test_a_number_not_in_the_list(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "7", "back", BACK, QUIT)
		self.assertIn("No folder number 7", text)

	def test_mistakes_are_said(self):
		testers.install(self.tester, self.testers_root, environ={})
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "cd nowhere", "dance", "help", "back", BACK, QUIT)
		self.assertIn("No folder here", text)
		self.assertIn("Unknown command: dance", text)
		self.assertIn("ls", text)
		self.assertNotIn("✗ KO", text)

	def test_run_again_then_another_folder(self):
		other = self.folder / "other"
		other.mkdir()
		(other / "result.json").write_text(json.dumps(results(conformity=[], tests=results()["tests"][:3])))
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "y", str(self.project), AGAIN, ANOTHER, str(other),
			DONE, BACK, QUIT)
		self.assertEqual(text.count("✗ KO"), 2)
		self.assertIn("✓ OK  tests 3/3", text)
		self.assertEqual(testers.last_project(self.tester, self.settings), str(other))

	def test_a_download_that_fails(self):
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "y", BACK, QUIT,
			tester=replace(self.tester, tag="v0.0.0"))
		self.assertIn("The download failed", text)
		self.assertEqual(text.count("1. libfterator"), 2)

	def test_a_new_version_offered_and_refused_runs_the_one_installed(self):
		testers.install(self.tester, self.testers_root, environ={})
		newer = replace(self.tester, tag="v9.9.10", commit=new_tag(self.repo, "v9.9.10"))
		text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "n", str(self.project), DONE, BACK, QUIT, tester=newer)
		self.assertTrue(self.asked("Update it now? (y/n)"))
		self.assertEqual(testers.state(newer, self.testers_root), testers.OUTDATED)
		self.assertIn("✗ KO", text)

	def test_a_new_version_accepted(self):
		testers.install(self.tester, self.testers_root, environ={})
		newer = replace(self.tester, tag="v9.9.10", commit=new_tag(self.repo, "v9.9.10"))
		self.run_shell("", "pw", TESTERS, LIBFTERATOR, "y", str(self.project), DONE, BACK, QUIT, tester=newer)
		self.assertEqual(testers.state(newer, self.testers_root), testers.READY)

	def test_the_tester_speaks_the_language_of_42pal(self):
		testers.install(self.tester, self.testers_root, environ={})
		languages = []
		real_run = testers.run

		def run(tester, project, lang, root, on_progress=None):
			languages.append(lang)
			return real_run(tester, project, lang, root, on_progress=on_progress)

		self.addCleanup(i18n.set_language, "en")
		i18n.set_language("fr")
		with mock.patch.object(testers, "run", run):
			text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, str(self.project), DONE, BACK, QUIT)
		self.assertEqual(languages, ["fr"])
		self.assertIn("Testeurs", text)

class TestTheScreens(FullScreenTest, TestersTestCase):

	def setUp(self):
		FullScreenTest.setUp(self)
		TestersTestCase.setUp(self)

	def app(self, tester=None):
		app = self.exam_app()
		self.configure(app.shell, tester)
		app.settings_file = self.settings
		return app

	async def to_testers(self, pilot):
		"""Log in, then Testers in the first menu."""
		await self.login(pilot)
		values = [item[0] for item in pilot.app.screen.items]
		await pilot.press(*["down"] * values.index(TESTERS_CHOICE), "enter")
		await pilot.pause()
		self.assertEqual(pilot.app.screen.title, "Testers")

	async def wait_for(self, pilot, kind):
		"""Wait until the screen is a `kind` (10 seconds at most)."""
		for _ in range(200):
			await pilot.pause(0.05)
			if isinstance(pilot.app.screen, kind):
				return pilot.app.screen
		self.fail(f"no {kind.__name__}: {pilot.app.screen!r}")

	async def wait_report(self, pilot, screen):
		for _ in range(200):
			await pilot.pause(0.05)
			if not screen.busy:
				return log_text(screen)
		self.fail("the tester never ended")

	async def give_folder(self, pilot, path):
		screen = await self.wait_for(pilot, FolderScreen)
		screen.query_one("#folder").value = str(path)
		await pilot.press("enter")
		await pilot.pause()

	@screen_test
	async def test_testers_comes_before_settings_in_the_first_menu(self):
		async with self.app().run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			titles = [item[1] for item in pilot.app.screen.items]
			self.assertEqual(titles[-3:], ["Practice", "Testers", "Settings"])

	@screen_test
	async def test_downloaded_then_the_folder_then_the_results(self):
		app = self.app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_testers(pilot)
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Download libfterator?")
			await pilot.press("enter")
			await self.give_folder(pilot, self.project)
			screen = await self.wait_for(pilot, TesterScreen)
			text = await self.wait_report(pilot, screen)
			self.assertIn("No useless relink", text)
			self.assertIn("ft_strlcat", text)
			self.assertIn("read 1 byte(s) past the end", text)
			self.assertIn("✗ KO  subject 1/2 · tests 3/4", text)
			# The verdict in the header too: the log opens at its top.
			self.assertIn("✗ KO  subject 1/2 · tests 3/4", str(screen.query_one("#header").render()))
			self.assertEqual(testers.state(self.tester, self.testers_root), testers.READY)
			self.assertEqual(testers.last_project(self.tester, self.settings), str(self.project))
			# Another folder: the one of the last time comes first in the list.
			await pilot.press("f")
			folder = await self.wait_for(pilot, FolderScreen)
			self.assertEqual(folder.entry_labels()[0][1], self.project)
			await pilot.press("escape")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Testers")
			await pilot.press("escape")
			await pilot.pause()
			self.assertEqual(app.screen.title, "What do you want to do?")

	@screen_test
	async def test_run_again(self):
		testers.install(self.tester, self.testers_root, environ={})
		app = self.app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_testers(pilot)
			await pilot.press("enter")
			await self.give_folder(pilot, self.project)
			screen = await self.wait_for(pilot, TesterScreen)
			await self.wait_report(pilot, screen)
			(self.project / "result.json").write_text(json.dumps(results(conformity=[], tests=results()["tests"][:3])))
			await pilot.press("r")
			text = await self.wait_report(pilot, screen)
			self.assertIn("✓ OK  tests 3/3", text)
			self.assertNotIn("✗ KO", text)

	@screen_test
	async def test_a_folder_that_does_not_exist_stays_on_the_folder(self):
		testers.install(self.tester, self.testers_root, environ={})
		app = self.app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_testers(pilot)
			await pilot.press("enter")
			await self.give_folder(pilot, self.folder / "nothing")
			self.assertIsInstance(app.screen, FolderScreen)
			self.assertIn("No folder here", str(app.screen.query_one("#folder-status").render()))

	@screen_test
	async def test_the_download_refused(self):
		app = self.app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_testers(pilot)
			await pilot.press("enter")
			await pilot.pause()
			await pilot.press("escape")
			await pilot.pause()
			self.assertEqual(app.screen.title, "Testers")
			self.assertEqual(testers.state(self.tester, self.testers_root), testers.MISSING)

	@screen_test
	async def test_a_download_that_fails_comes_back_to_the_testers(self):
		app = self.app(tester=replace(self.tester, tag="v0.0.0"))
		async with app.run_test(size=(100, 40)) as pilot:
			await self.to_testers(pilot)
			await pilot.press("enter")
			await pilot.pause()
			await pilot.press("enter")
			screen = await self.wait_for(pilot, MenuScreen)
			for _ in range(100):
				await pilot.pause(0.05)
				if app.screen.title == "Testers":
					break
			self.assertEqual(app.screen.title, "Testers")

	@screen_test
	async def test_a_tester_this_system_cannot_run(self):
		app = self.app()
		with mock.patch.object(testers, "available", lambda tester: False):
			async with app.run_test(size=(100, 40)) as pilot:
				await self.to_testers(pilot)
				self.assertEqual(app.screen.items[0][2], "Linux only")
				await pilot.press("enter")
				await pilot.pause()
				self.assertEqual(app.screen.title, "Testers")
		self.assertFalse(self.testers_root.exists())

class TestTheFolderScreen(FullScreenTest, TestersTestCase):
	"""The folder: those found first, as they are found; then typed, with the folders below it, live."""

	def setUp(self):
		FullScreenTest.setUp(self)
		TestersTestCase.setUp(self)
		(self.project / "libft.h").write_text("")
		(self.folder / "plain").mkdir()

	async def open_screen(self, pilot, default=None):
		await self.login(pilot)
		screen = FolderScreen(self.tester, default, root=self.folder)
		self.chosen = []
		pilot.app.push_screen(screen, self.chosen.append)
		await pilot.pause()
		return screen

	def entries(self, screen):
		return [label for label, _ in screen.entry_labels()]

	async def wait_entries(self, pilot, screen, label):
		for _ in range(100):
			await pilot.pause(0.05)
			if any(label in entry for entry in self.entries(screen)):
				return
		self.fail(f"{label} never shown: {self.entries(screen)}")

	@screen_test
	async def test_the_projects_found_come_first_and_one_is_chosen(self):
		async with self.exam_app().run_test(size=(100, 40)) as pilot:
			screen = await self.open_screen(pilot)
			await self.wait_entries(pilot, screen, "libft")
			await pilot.press("down", "enter")
			await pilot.pause()
			self.assertEqual(self.chosen, [self.project])

	@screen_test
	async def test_typing_a_folder_shows_its_folders_live(self):
		async with self.exam_app().run_test(size=(100, 40)) as pilot:
			screen = await self.open_screen(pilot)
			screen.query_one("#folder").value = f"{self.folder}/"
			await pilot.pause()
			entries = self.entries(screen)
			self.assertEqual(entries[0], "..")
			self.assertIn("★ libft/", entries)
			self.assertIn("plain/", entries)
			screen.query_one("#folder").value = f"{self.folder}/pl"
			await pilot.pause()
			self.assertEqual(self.entries(screen), ["plain/"])

	@screen_test
	async def test_enter_on_a_folder_opens_it_and_on_a_project_tests_it(self):
		async with self.exam_app().run_test(size=(100, 40)) as pilot:
			screen = await self.open_screen(pilot)
			folder = screen.query_one("#folder")
			folder.value = f"{self.folder}/"
			await pilot.pause()
			plain = self.entries(screen).index("plain/")
			await pilot.press(*["down"] * (plain + 1), "enter")
			await pilot.pause()
			self.assertEqual(folder.value.rstrip("/"), str(self.folder / "plain"))
			self.assertEqual(self.chosen, [])
			# .. goes up, then the project is tested.
			await pilot.press("down", "enter")
			await pilot.pause()
			self.assertEqual(folder.value.rstrip("/"), str(self.folder))
			project = self.entries(screen).index("★ libft/")
			await pilot.press(*["down"] * (project + 1), "enter")
			await pilot.pause()
			self.assertEqual(self.chosen, [self.project])

	@screen_test
	async def test_the_folder_typed_says_when_it_is_the_project(self):
		async with self.exam_app().run_test(size=(100, 40)) as pilot:
			screen = await self.open_screen(pilot)
			screen.query_one("#folder").value = str(self.project)
			await pilot.pause()
			self.assertIn("a libft here", str(screen.query_one("#folder-status").render()))
			await pilot.press("enter")
			await pilot.pause()
			self.assertEqual(self.chosen, [self.project])

	@screen_test
	async def test_tab_opens_the_folder_highlighted(self):
		async with self.exam_app().run_test(size=(100, 40)) as pilot:
			screen = await self.open_screen(pilot)
			folder = screen.query_one("#folder")
			folder.value = f"{self.folder}/pl"
			await pilot.pause()
			await pilot.press("tab")
			await pilot.pause()
			self.assertEqual(folder.value, f"{self.folder}/plain/")

	@screen_test
	async def test_escape_goes_back(self):
		async with self.exam_app().run_test(size=(100, 40)) as pilot:
			await self.open_screen(pilot)
			await pilot.press("escape")
			await pilot.pause()
			self.assertEqual(self.chosen, [None])

class TestLive(FullScreenTest, TestersTestCase):
	"""The results of the tester as they come: a counter, the checks and the failed tests, then the report."""

	def setUp(self):
		FullScreenTest.setUp(self)
		TestersTestCase.setUp(self)

	@screen_test
	async def test_the_results_come_as_they_are_found(self):
		release = threading.Event()
		self.addCleanup(release.set)

		def run(tester, project, on_progress):
			progress = testers.Progress()
			for event in ({"event": "step", "step": "subject"},
					{"event": "check", "key": "make.relink", "group": "Makefile", "label": "No useless relink",
						"status": "KO", "detail": "a second make rebuilds"},
					{"event": "plan", "tests": 4}, {"event": "step", "step": "tests"},
					{"event": "test", "name": "strlcat/dst", "status": "OOB", "detail": "read 1 byte past", "ms": 1}):
				on_progress(progress, progress.update(event))
			release.wait(10)
			return testers.parse(results(), tester)

		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await self.login(pilot)
			screen = TesterScreen(self.tester, self.project, run)
			app.push_screen(screen)
			for _ in range(100):
				await pilot.pause(0.05)
				if "1/4" in str(screen.query_one("#activity").render()):
					break
			activity = str(screen.query_one("#activity").render())
			self.assertIn("1/4", activity)
			self.assertIn("1 KO", activity)
			text = log_text(screen)
			self.assertIn("No useless relink", text)
			self.assertIn("ft_strlcat", text)
			self.assertIn("read 1 byte past", text)
			self.assertTrue(screen.busy)
			release.set()
			for _ in range(100):
				await pilot.pause(0.05)
				if not screen.busy:
					break
			self.assertIn("✗ KO  subject 1/2 · tests 3/4", log_text(screen))

# The suites as a tester like Linerator names and draws them.
GNL_SUITES = [
	{"key": "buffer_1", "name": "BUFFER_SIZE=1", "group": "BUFFER_SIZE", "label": "1", "tests": 3},
	{"key": "read_errors", "name": "read() fails", "group": "The other tests", "label": "read() fails", "tests": 2},
]
GNL_TESTS = [
	{"name": "buffer_1/one_line", "status": "PASS", "detail": "1 line", "ms": 1},
	{"name": "buffer_1/empty", "status": "PASS", "detail": "0 lines", "ms": 1},
	{"name": "buffer_1/long_line", "status": "LEAK", "detail": "1 block(s) not freed", "ms": 1},
	{"name": "read_errors/first_read", "status": "PASS", "detail": "NULL", "ms": 1},
	{"name": "read_errors/reopen", "status": "PASS", "detail": "NULL", "ms": 1},
]

# The suites as Pushterator gives them: a row of benchmarks has its levels.
BENCH_ROW = {"key": "bench_100", "name": "100 numbers", "group": "Benchmarks", "label": "100 numbers", "tests": 3,
	"levels": [{"key": "excellent", "name": "excellent", "under": 700}, {"key": "good", "name": "good", "under": 1500},
		{"key": "pass", "name": "pass", "under": 2000}], "unit": "operations", "short": "100"}
SWAP_SUITES = [{"key": "size_3", "name": "3 numbers", "group": "Suites", "label": "3 numbers", "tests": 2}, BENCH_ROW]
SWAP_TESTS = [
	{"name": "size_3/1_2_3", "status": "PASS", "detail": "no operation", "ms": 1, "ops": 0},
	{"name": "size_3/3_2_1", "status": "PASS", "detail": "2 operations", "ms": 1, "ops": 2},
	{"name": "bench_100/run_1", "status": "PASS", "detail": "650 operations: excellent", "ms": 1, "ops": 650},
	{"name": "bench_100/run_2", "status": "PASS", "detail": "1100 operations: good", "ms": 1, "ops": 1100},
	{"name": "bench_100/run_3", "status": "CRASH", "detail": "SIGSEGV", "ms": 1},
]

class TestTheBenchmarksOfATester(unittest.TestCase):
	"""A tester whose suites have levels (the benchmarks of Pushterator): bars, their own section, the verdict."""

	def report(self):
		return testers.parse(results(conformity=[], tests=SWAP_TESTS, suites=SWAP_SUITES), testers.find("pushterator"))

	def text(self, lines):
		console = Console(file=io.StringIO(), width=100, color_system=None)
		for line in lines:
			console.print(line)
		return console.file.getvalue()

	def test_the_levels_and_the_operations_read(self):
		report = self.report()
		self.assertEqual(report.suites[1]["short"], "100")
		self.assertEqual([test.ops for test in report.tests], [0, 2, 650, 1100, None])

	def test_their_section_in_the_report_and_their_level_in_the_verdict(self):
		from pal42.cli import display
		text = self.text(display.tester_report(self.report(), testers.find("pushterator"), Path("/tmp/push_swap")))
		self.assertIn("Benchmarks", text)
		self.assertIn("best 650 · average 875 · worst 1100", text)
		self.assertIn("excellent under 700 operations", text)
		# A run without operations: its failure under the benchmarks; the suite not listed with the tests.
		self.assertIn("run_3", text)
		self.assertNotIn("100 numbers ....", text)
		verdict = next(line for line in text.splitlines() if line.startswith("✗ KO"))
		self.assertEqual(verdict, "✗ KO  tests 4/5 · 100: good")

	def test_their_bars_in_the_panel(self):
		from pal42.cli import display
		report = self.report()
		done = {}
		for test in report.tests:
			done.setdefault(test.function, []).append((not test.bad, test.ops))
		panel = display.tester_panel(report.suites, done)
		lines = panel.plain.splitlines()
		self.assertEqual(lines[:2], ["Suites", " 3 numbers ■■ 2/2"])
		self.assertIn(" 100 numbers   good", lines)
		self.assertIn(" excellent <700 · good <1500 · pass <2000", lines)
		self.assertIn("waiting…", display.tester_panel([BENCH_ROW], {}).plain)

class TestTheSuitesOfATester(FullScreenTest, TestersTestCase):
	"""A tester that names and draws its suites: 42pal shows the same names and the same panel as the tester."""

	def setUp(self):
		FullScreenTest.setUp(self)
		TestersTestCase.setUp(self)

	@screen_test
	async def test_the_panel_and_the_names_live_then_in_the_report(self):
		release = threading.Event()
		self.addCleanup(release.set)

		def run(tester, project, on_progress):
			progress = testers.Progress()
			for event in ({"event": "plan", "tests": 5, "suites": GNL_SUITES}, {"event": "step", "step": "tests"},
					*({"event": "test", **test} for test in GNL_TESTS[:3])):
				on_progress(progress, progress.update(event))
			release.wait(10)
			return testers.parse(results(conformity=[], tests=GNL_TESTS, suites=GNL_SUITES), tester)

		app = self.exam_app()
		async with app.run_test(size=(120, 40)) as pilot:
			await self.login(pilot)
			screen = TesterScreen(self.tester, self.project, run)
			app.push_screen(screen)
			for _ in range(100):
				await pilot.pause(0.05)
				panel = getattr(screen, "suites_panel", None)
				if panel is not None and "2/3" in str(panel.render()):
					break
			self.assertTrue(panel.has_class("-shown"))
			self.assertIn("BUFFER_SIZE", str(panel.render()))
			self.assertIn("BUFFER_SIZE=1 · long_line", log_text(screen))
			release.set()
			for _ in range(100):
				await pilot.pause(0.05)
				if not screen.busy:
					break
			text = log_text(screen)
			self.assertIn("BUFFER_SIZE=1", text)
			self.assertIn("read() fails", text)
			self.assertNotIn("buffer_1 ", text)
			self.assertIn("2/2", str(panel.render()))
			# The report takes the place of what came live.
			self.assertEqual(text.count("long_line"), 1)

	@screen_test
	async def test_no_panel_for_a_tester_that_gives_no_suites(self):
		def run(tester, project, on_progress):
			return testers.parse(results(), tester)

		app = self.exam_app()
		async with app.run_test(size=(120, 40)) as pilot:
			await self.login(pilot)
			screen = TesterScreen(self.tester, self.project, run)
			app.push_screen(screen)
			for _ in range(100):
				await pilot.pause(0.05)
				if not screen.busy:
					break
			self.assertFalse(screen.suites_panel.has_class("-shown"))

	@screen_test
	async def test_no_title_of_failures_while_everything_passes(self):
		release = threading.Event()
		self.addCleanup(release.set)

		def run(tester, project, on_progress):
			progress = testers.Progress()
			for event in ({"event": "plan", "tests": 5}, {"event": "step", "step": "tests"},
					*({"event": "test", **test} for test in GNL_TESTS[:2])):
				on_progress(progress, progress.update(event))
			release.wait(10)
			return testers.parse(results(), tester)

		app = self.exam_app()
		async with app.run_test(size=(120, 40)) as pilot:
			await self.login(pilot)
			screen = TesterScreen(self.tester, self.project, run)
			screen.PROGRESS_EVERY = 0
			app.push_screen(screen)
			for _ in range(100):
				await pilot.pause(0.05)
				if "2/5" in str(screen.query_one("#activity").render()):
					break
			self.assertIn("2/5", str(screen.query_one("#activity").render()))
			self.assertNotIn("Failed so far", log_text(screen))
			release.set()

class TestNoHorizontalScroll(FullScreenTest, TestersTestCase):
	"""The long lines of the results wrap: no horizontal scroll bar, even in a narrow terminal."""

	def setUp(self):
		FullScreenTest.setUp(self)
		TestersTestCase.setUp(self)

	@screen_test
	async def test_a_long_detail_wraps(self):
		long = "word " * 60
		data = results(tests=[{"name": "strlcat/long", "status": "FAIL", "detail": long, "ms": 1}])

		def run(tester, project, on_progress):
			return testers.parse(data, tester)

		app = self.exam_app()
		async with app.run_test(size=(70, 30)) as pilot:
			await self.login(pilot)
			screen = TesterScreen(self.tester, self.project, run)
			app.push_screen(screen)
			for _ in range(100):
				await pilot.pause(0.05)
				if not screen.busy:
					break
			log = screen.query_one("#log")
			self.assertLessEqual(log.virtual_size.width, log.scrollable_content_region.width)
			self.assertIn("word word", log_text(screen))

class TestNoHorizontalScrollInTheExam(FullScreenTest):

	@screen_test
	async def test_a_long_command_wraps_in_the_log_of_the_exam(self):
		app = self.exam_app()
		async with app.run_test(size=(70, 30)) as pilot:
			await self.login_to_exams(pilot)
			await pilot.press("enter", "enter")
			await pilot.pause()
			await self.type(pilot, "x" * 150)
			log = app.screen.query_one("#log")
			self.assertLessEqual(log.virtual_size.width, log.scrollable_content_region.width)

class TestTheFramesOfTheExam(FullScreenTest):
	"""The frames the shell prints (a trace) keep their lines in the log: none is cut in two."""

	@screen_test
	async def test_a_trace_in_the_log_of_the_exam(self):
		from pal42.cli import display
		app = self.exam_app()
		async with app.run_test(size=(176, 42)) as pilot:
			await self.login_to_exams(pilot)
			await pilot.press("enter", "enter")
			await pilot.pause()
			screen = app.screen
			screen.fit_console()
			trace = "= Test 4 " + "=" * 71 + "\n$> ./x \"Hello World\" | cat -e\n--- student\n+++ moulinette\nDiff KO\n"
			console = screen.shell.console
			console.begin_capture()
			console.print(display.trace_panel(trace))
			screen.finish_command(False, console.end_capture())
			await pilot.pause()
			lines = [line.text.rstrip() for line in screen.query_one("#log").lines if line.text.strip()]
			frame = [line for line in lines if line.startswith(("│", "╭", "╰"))]
			self.assertTrue(frame[0].startswith("╭") and frame[-1].startswith("╰"), frame)
			self.assertTrue(all(line.endswith(("│", "╮", "╯")) for line in frame), frame)
			self.assertIn("Diff KO", "\n".join(frame))

class TestTheProgressText(unittest.TestCase):

	def test_what_the_tester_is_doing(self):
		from pal42.cli import display
		tester = testers.find("libfterator")
		progress = testers.Progress()
		self.assertIn("starting", display.tester_progress(tester, progress))
		progress.update({"event": "step", "step": "subject"})
		progress.update({"event": "check", "key": "a", "group": "g", "label": "l", "status": "OK", "detail": ""})
		self.assertIn("the subject: 1 check", display.tester_progress(tester, progress))
		progress.update({"event": "step", "step": "build"})
		self.assertIn("building", display.tester_progress(tester, progress))
		progress.update({"event": "plan", "tests": 4})
		progress.update({"event": "step", "step": "tests"})
		progress.update({"event": "test", "name": "a/b", "status": "PASS", "detail": "", "ms": 1})
		text = display.tester_progress(tester, progress)
		self.assertIn("tests 1/4", text)
		self.assertIn("0 KO", text)
		self.assertIn("━", text)

class TestTheCompletionOfAFolder(unittest.TestCase):

	def test_the_folders_that_start_with_what_is_typed(self):
		with tempfile.TemporaryDirectory() as folder:
			root = Path(folder)
			(root / "libft").mkdir()
			(root / "libft_old").mkdir()
			(root / "libft.txt").write_text("")
			(root / ".hidden").mkdir()
			self.assertEqual(suggest_folder(f"{folder}/lib"), f"{folder}/libft/")
			self.assertEqual(suggest_folder(f"{folder}/libft_"), f"{folder}/libft_old/")
			self.assertIsNone(suggest_folder(f"{folder}/nothing"))
			# Hidden folders only when a dot is typed.
			self.assertEqual(suggest_folder(f"{folder}/."), f"{folder}/.hidden/")
			self.assertIsNone(suggest_folder(""))

if __name__ == "__main__":
	unittest.main()

class TestTheVisualizerOfATester(FullScreenTest, TestersTestCase):
	"""v in the results: 42pal pauses and opens the visualizer of the tester in the terminal, then comes back."""

	def setUp(self):
		FullScreenTest.setUp(self)
		TestersTestCase.setUp(self)
		self.tester = replace(self.tester, visualizer=("--visualize",))
		testers.install(self.tester, self.testers_root, environ={})

	async def results(self, pilot, app):
		await self.login(pilot)
		app.push_screen(TesterScreen(self.tester, self.project, app.run_tester))
		for _ in range(200):
			await pilot.pause(0.05)
			if isinstance(app.screen, TesterScreen) and not app.screen.busy and app.screen.report is not None:
				return app.screen
		self.fail("no results")

	@screen_test
	async def test_v_opens_the_visualizer_in_the_terminal(self):
		app = self.exam_app()
		self.configure(app.shell, self.tester)
		app.settings_file = self.settings
		commands = []
		app.run_in_terminal = commands.append
		async with app.run_test(size=(100, 40)) as pilot:
			screen = await self.results(pilot, app)
			self.assertIn("visualize", str(screen.query_one("#session-hints").render()))
			await pilot.press("v")
			await pilot.pause()
			self.assertEqual(len(commands), 1)
			self.assertIn("--visualize", commands[0])
			self.assertIn(str(self.project), commands[0])
			self.assertIs(app.screen, screen)

	@screen_test
	async def test_no_visualizer_no_v(self):
		self.tester = replace(self.tester, visualizer=())
		app = self.exam_app()
		self.configure(app.shell, self.tester)
		commands = []
		app.run_in_terminal = commands.append
		async with app.run_test(size=(100, 40)) as pilot:
			screen = await self.results(pilot, app)
			self.assertNotIn("visualize", str(screen.query_one("#session-hints").render()))
			await pilot.press("v")
			await pilot.pause()
			self.assertEqual(commands, [])

class TestTheVisualizerInText(TestersTestCase):

	def test_visualize_in_the_menu_after_the_results(self):
		tester = replace(self.tester, visualizer=("--visualize",))
		testers.install(tester, self.testers_root, environ={})
		console = Console(file=io.StringIO(), width=100, color_system=None)
		script = Script("", "pw", TESTERS, LIBFTERATOR, str(self.project), "3", "4", BACK, QUIT)
		shell = Shell(console, script.ask, script.ask_password, Workspace(self.folder / "exam"), rng=Random(1),
			clock=FakeClock(), sleep=lambda seconds: None, catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		self.configure(shell, tester)
		commands = []
		shell.run_command = commands.append
		shell.run()
		text = console.file.getvalue()
		# What now? 1 Run again, 2 Another folder, 3 Visualize, 4 Back.
		self.assertIn("3. Visualize", text)
		self.assertEqual(len(commands), 1)
		self.assertIn("--visualize", commands[0])

class TestTheReportOfATester(unittest.TestCase):
	"""What 42pal shows of the results of a tester: its own title, and the same failure once."""

	def report(self, tests):
		data = results(conformity=[], tests=tests)
		return testers.parse(data, testers.find("pushterator"))

	def text(self, report, tester):
		from pal42.cli import display
		console = Console(file=io.StringIO(), width=100, color_system=None)
		for line in display.tester_report(report, tester, Path("/tmp/push_swap")):
			console.print(line)
		return console.file.getvalue()

	def test_the_title_of_the_tests_of_each_tester(self):
		tests = results()["tests"][:3]
		self.assertIn("The functions", self.text(self.report(tests), testers.find("libfterator")))
		self.assertIn("The tests", self.text(self.report(tests), testers.find("pushterator")))

	def test_the_same_failure_of_a_whole_suite_once(self):
		tests = [{"name": f"strategy_simple/case_{n}", "status": "FAIL", "detail": "Error with --simple", "ms": 0}
			for n in range(8)]
		text = self.text(self.report(tests), testers.find("pushterator"))
		self.assertIn("all 8", text)
		self.assertEqual(text.count("Error with --simple"), 1)

	def test_the_names_the_tester_gives_its_suites(self):
		data = results(conformity=[], tests=GNL_TESTS, suites=GNL_SUITES)
		report = testers.parse(data, testers.find("linerator"))
		text = self.text(report, testers.find("linerator"))
		self.assertIn("BUFFER_SIZE=1", text)
		self.assertIn("read() fails", text)
		self.assertNotIn("buffer_1", text.replace("buffer_1/", ""))

	def test_an_undefined_case_in_a_suite_is_not_counted(self):
		tests = [{"name": "malloc_failures/malloc_1", "status": "PASS", "detail": "", "ms": 0},
			{"name": "malloc_failures/malloc_9", "status": "INFO", "detail": "only 8 calls to malloc", "ms": 0}]
		report = self.report(tests)
		self.assertEqual(report.test_score, (1, 1))
		self.assertEqual((report.functions[0].passed, report.functions[0].total), (1, 1))

	def test_the_suites_checked(self):
		data = {"suites": [{"key": "a", "tests": 3}, {"name": "no key"}, "nonsense", {"key": "b", "tests": -1}]}
		self.assertEqual(testers.suites_of(data), [
			{"key": "a", "name": "a", "group": "", "label": "a", "tests": 3},
			{"key": "b", "name": "b", "group": "", "label": "b", "tests": 0}])
		self.assertEqual(testers.suites_of({"suites": "nonsense"}), [])
		self.assertEqual(testers.suites_of({}), [])

	def test_different_failures_each_shown(self):
		tests = [{"name": f"size_5/case_{n}", "status": "FAIL", "detail": f"not sorted {n}", "ms": 0} for n in range(3)]
		text = self.text(self.report(tests), testers.find("pushterator"))
		self.assertNotIn("all 3", text)
		self.assertIn("not sorted 2", text)

class TestTheDisclaimer(FullScreenTest):
	"""Each launcher says it is a helper tool: it does not cover every test of the evaluation."""

	@screen_test
	async def test_at_the_bottom_of_the_login(self):
		app = self.exam_app()
		async with app.run_test(size=(100, 40)) as pilot:
			await pilot.pause()
			self.assertIn("not an oracle", str(app.screen.query_one(".disclaimer").render()))

	def test_in_the_text_interface(self):
		console = Console(file=io.StringIO(), width=120, color_system=None)
		script = Script("", "pw", "5")
		with tempfile.TemporaryDirectory() as root:
			shell = Shell(console, script.ask, script.ask_password, Workspace(root), rng=Random(1), clock=FakeClock(),
				sleep=lambda seconds: None, catalog=ECHO_CATALOG, themes=ECHO_THEMES)
			shell.run()
		self.assertIn("not an oracle", console.file.getvalue())

	def test_at_the_end_of_the_results_of_a_tester(self):
		from pal42.cli import display
		report = testers.parse(results(), testers.find("libfterator"))
		console = Console(file=io.StringIO(), width=120, color_system=None)
		for line in display.tester_report(report, testers.find("libfterator"), Path("/tmp/libft")):
			console.print(line)
		self.assertIn("not an oracle", console.file.getvalue().splitlines()[-1])

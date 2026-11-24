"""Testers in the first menu: a tester downloaded when the student agrees, the folder asked, the results shown.

The tester is the fake one of tests/test_testers.py, cloned from a git
repository in a temporary folder: no network.
"""

import io
import json
import os
import tempfile
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
		(self.project / "result.json").write_text(json.dumps(results()))

	def configure(self, shell, tester=None):
		"""The testers of the test, kept in its folder; the settings too."""
		shell.settings_file = self.settings
		shell.testers_root = self.testers_root
		shell.tester_list = (tester or self.tester,)
		shell.testers_environ = {"PATH": os.environ["PATH"]}

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
		self.assertTrue(self.asked("Folder of your libft"))
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

	def test_no_folder_goes_back_to_the_testers(self):
		testers.install(self.tester, self.testers_root, environ={})
		with mock.patch("pal42.cli.shell.Path.cwd", return_value=self.folder):
			text = self.run_shell("", "pw", TESTERS, LIBFTERATOR, "", BACK, QUIT)
		self.assertEqual(text.count("1. libfterator"), 2)
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

		def run(tester, project, lang, root):
			languages.append(lang)
			return real_run(tester, project, lang, root)

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
			self.assertEqual(testers.state(self.tester, self.testers_root), testers.READY)
			self.assertEqual(testers.last_project(self.tester, self.settings), str(self.project))
			# Another folder: the one of the last time is offered.
			await pilot.press("f")
			folder = await self.wait_for(pilot, FolderScreen)
			self.assertTrue(folder.query_one("#folder").value)
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
			self.assertIn("No folder here", str(app.screen.query_one("#folder-error").render()))

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

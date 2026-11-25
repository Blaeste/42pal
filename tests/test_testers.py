"""The testers of projects: downloaded at a tag and checked, run, and their JSON read.

No network: the tester cloned is a fake one, in a git repository made in a
temporary folder (docs/plans/testers.md).
"""

import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pal42 import testers

# The fake tester: it gives back the results written in the project
# (result.json), with the language it was asked for, and prints a line.
LAUNCHER = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
args = sys.argv[1:]
project = Path(args[0])
print("terminal output of the fake tester")
result = project / "result.json"
if not result.is_file():
	print("no results: boom")
	sys.exit(2)
data = json.loads(result.read_text())
data["lang"] = args[args.index("--lang") + 1]
data["args"] = args
if "--stream" in args:
	def emit(event, **fields):
		print(json.dumps(dict(event=event, **fields)), flush=True)
	emit("start", tester="libfterator", version=data.get("version"), lang=data["lang"])
	if data["conformity"]:
		emit("step", step="subject")
		for check in data["conformity"]:
			emit("check", **check)
	if data.get("error"):
		emit("error", **data["error"])
	else:
		emit("step", step="build")
		emit("plan", tests=len(data["tests"]))
		emit("step", step="tests")
		for test in data["tests"]:
			emit("test", **test)
Path(args[args.index("--json") + 1]).write_text(json.dumps(data))
sys.exit(1)
"""

def git(folder, *args):
	return subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t", *args],
		capture_output=True, text=True, check=True).stdout.strip()

def results(**fields):
	"""A JSON of format 1, as libfterator writes it; fields replace its values."""
	data = {
		"format": 1, "tester": "libfterator", "version": "2.0.0", "lang": "en", "seed": 42,
		"log": "/tmp/out/libfterator_1.log", "error": None, "notes": [],
		"conformity": [
			{"key": "files.layout", "group": "Files", "label": "Makefile at the root", "status": "OK", "detail": ""},
			{"key": "make.relink", "group": "Makefile", "label": "No useless relink", "status": "KO",
				"detail": "a second make rebuilds files"},
			{"key": "readme.ai", "group": "README", "label": "Use of AI", "status": "WARN", "detail": "say it"},
			{"key": "norm", "group": "Norm", "label": "Norminette", "status": "SKIP", "detail": "not found"},
		],
		"tests": [
			{"name": "isalpha/basic", "status": "PASS", "detail": "", "ms": 1},
			{"name": "isalpha/edges", "status": "PASS", "detail": "", "ms": 1},
			{"name": "strlcat/basic", "status": "PASS", "detail": "", "ms": 1},
			{"name": "strlcat/dst_not_terminated", "status": "OOB", "detail": "read 1 byte(s) past the end", "ms": 2},
			{"name": "info/strlen_null", "status": "INFO", "detail": "SIGSEGV", "ms": 1},
		],
	}
	data.update(fields)
	return data

def fake_tester(folder, shell=False):
	"""The fake tester in a git repository in `folder`, tagged v9.9.9; return (tester, repository).

	shell: its launcher is a shell script (like the one of pushterator), not a Python one.
	"""
	repo = Path(folder) / "repo"
	repo.mkdir()
	launcher = repo / "libfterator"
	if shell:
		(repo / "fake.py").write_text(LAUNCHER)
		launcher.write_text('#!/bin/sh\nexec python3 "$(dirname "$0")/fake.py" "$@"\n')
	else:
		launcher.write_text(LAUNCHER)
	launcher.chmod(0o755)
	git(repo, "init", "-q")
	git(repo, "add", ".")
	git(repo, "commit", "-q", "-m", "first")
	git(repo, "tag", "v9.9.9")
	return replace(testers.TESTERS[0], url=repo.as_uri(), tag="v9.9.9", commit=git(repo, "rev-parse", "HEAD"),
		python=not shell), repo

def new_tag(repo, tag):
	"""A new commit in the repository of the fake tester, tagged `tag`; return its commit."""
	(repo / tag).write_text("new\n")
	git(repo, "add", ".")
	git(repo, "commit", "-q", "-m", tag)
	git(repo, "tag", tag)
	return git(repo, "rev-parse", "HEAD")

class TesterTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.tmp = Path(folder.name)
		self.root = self.tmp / "testers"
		self.tester, self.repo = fake_tester(self.tmp)
		self.project = self.tmp / "libft"
		self.project.mkdir()

	def install(self):
		ok, why = testers.install(self.tester, self.root, environ={})
		self.assertTrue(ok, why)

class TestTheRegistry(unittest.TestCase):

	def test_libfterator_at_a_tag_and_a_commit_of_its_repository(self):
		tester = testers.find("libfterator")
		self.assertEqual(tester.url, "https://github.com/Blaeste/Libfterator.git")
		self.assertTrue(tester.tag.startswith("v2."))
		self.assertRegex(tester.commit, r"^[0-9a-f]{40}$")
		self.assertEqual(tester.launcher, "libfterator")

	def test_pushterator_for_push_swap(self):
		tester = testers.find("pushterator")
		self.assertEqual(tester.url, "https://github.com/Blaeste/Pushterator.git")
		self.assertTrue(tester.tag.startswith("v1."))
		self.assertRegex(tester.commit, r"^[0-9a-f]{40}$")
		self.assertEqual((tester.launcher, tester.project), ("pushterator", "push_swap"))
		# Its launcher is a shell script; it runs on macOS too; it has a visualizer.
		self.assertFalse(tester.python)
		self.assertEqual(tester.visualizer, ("--visualize",))
		self.assertTrue(testers.available(tester, "darwin"))
		self.assertTrue(tester.streams)

	def test_only_on_linux(self):
		tester = testers.find("libfterator")
		self.assertTrue(testers.available(tester, "linux"))
		self.assertFalse(testers.available(tester, "darwin"))

	def test_the_repository_can_be_replaced_to_try_a_local_one(self):
		tester = testers.find("libfterator")
		self.assertEqual(testers.source(tester, {}), tester.url)
		self.assertEqual(testers.source(tester, {"PAL42_TESTER_LIBFTERATOR": "/home/me/lft"}), "/home/me/lft")

class TestInstall(TesterTestCase):

	def test_missing_then_ready_once_cloned_at_its_tag(self):
		self.assertEqual(testers.state(self.tester, self.root), testers.MISSING)
		self.install()
		self.assertEqual(testers.state(self.tester, self.root), testers.READY)
		self.assertTrue((self.root / "libfterator" / "libfterator").is_file())

	def test_a_tag_that_is_not_the_commit_expected_is_refused_and_removed(self):
		tester = replace(self.tester, commit="0" * 40)
		ok, why = testers.install(tester, self.root, environ={})
		self.assertFalse(ok)
		self.assertIn("not the one expected", why)
		self.assertFalse((self.root / "libfterator").exists())
		self.assertEqual(list(self.root.iterdir()), [])

	def test_a_tag_that_does_not_exist(self):
		ok, why = testers.install(replace(self.tester, tag="v0.0.0"), self.root, environ={})
		self.assertFalse(ok)
		# Where it was looked for, and the version: a tag not pushed yet is seen at once.
		self.assertIn("v0.0.0", why)
		self.assertIn(self.repo.as_uri(), why)
		self.assertIn("not found", why)
		self.assertEqual(testers.state(self.tester, self.root), testers.MISSING)

	def test_without_git(self):
		ok, why = testers.install(self.tester, self.root, environ={"PATH": str(self.tmp / "nothing")})
		self.assertFalse(ok)
		self.assertIn("git", why)

	def test_a_new_tag_in_42pal_makes_it_outdated_then_installed_again(self):
		self.install()
		newer = replace(self.tester, tag="v9.9.10", commit=new_tag(self.repo, "v9.9.10"))
		self.assertEqual(testers.state(newer, self.root), testers.OUTDATED)
		ok, why = testers.install(newer, self.root, environ={})
		self.assertTrue(ok, why)
		self.assertEqual(testers.state(newer, self.root), testers.READY)
		self.assertTrue((self.root / "libfterator" / "v9.9.10").is_file())

	def test_a_failed_update_keeps_the_tester_installed(self):
		self.install()
		ok, _ = testers.install(replace(self.tester, tag="v0.0.0"), self.root, environ={})
		self.assertFalse(ok)
		self.assertEqual(testers.state(self.tester, self.root), testers.READY)

	def test_the_local_repository_given_instead(self):
		tester = replace(self.tester, url="https://example.invalid/nothing.git")
		ok, why = testers.install(tester, self.root, environ={"PAL42_TESTER_LIBFTERATOR": str(self.repo),
			"PATH": os.environ["PATH"]})
		self.assertTrue(ok, why)

class TestRun(TesterTestCase):

	def run_tester(self, data=None, lang="en"):
		if data is not None:
			(self.project / "result.json").write_text(json.dumps(data))
		self.install()
		return testers.run(self.tester, self.project, lang, self.root)

	def test_the_tester_gets_the_project_the_language_and_a_json_file(self):
		report = self.run_tester(results(), lang="fr")
		self.assertEqual(report.lang, "fr")
		self.assertEqual(report.data["args"][0], str(self.project))
		self.assertIn("--no-color", report.data["args"])

	def test_the_checks_and_their_counts(self):
		report = self.run_tester(results())
		self.assertEqual([check.status for check in report.checks], ["OK", "KO", "WARN", "SKIP"])
		self.assertEqual(report.checks[1].label, "No useless relink")
		# WARN and SKIP are not counted.
		self.assertEqual(report.conformity_score, (1, 2))

	def test_the_tests_by_function_and_their_counts(self):
		report = self.run_tester(results())
		self.assertEqual([(f.name, f.passed, f.total) for f in report.functions], [("isalpha", 2, 2), ("strlcat", 1, 2)])
		self.assertEqual([test.name for test in report.functions[1].bad], ["strlcat/dst_not_terminated"])
		# The undefined cases are apart, never counted.
		self.assertEqual([test.name for test in report.info], ["info/strlen_null"])
		self.assertEqual(report.test_score, (3, 4))
		self.assertFalse(report.passed)

	def test_everything_passes(self):
		data = results(conformity=[results()["conformity"][0]], tests=results()["tests"][:3])
		self.assertTrue(self.run_tester(data).passed)

	def test_the_error_of_the_tester(self):
		report = self.run_tester(results(error={"title": "Cannot build libft.a", "detail": "ft_atoi.c:3: error"},
			conformity=[], tests=[]))
		self.assertEqual(report.error, ("Cannot build libft.a", "ft_atoi.c:3: error"))
		self.assertFalse(report.passed)

	def test_no_results_gives_an_error_with_what_it_printed(self):
		report = self.run_tester()
		title, detail = report.error
		self.assertIn("no results", title)
		self.assertIn("boom", detail)

	def test_a_format_42pal_does_not_know(self):
		report = self.run_tester(results(format=99))
		self.assertIn("format 99", report.error[0])

	def test_the_log_and_the_notes(self):
		report = self.run_tester(results(notes=["taken with make bonus"]))
		self.assertEqual(report.log, "/tmp/out/libfterator_1.log")
		self.assertEqual(report.notes, ["taken with make bonus"])

	def test_in_real_time_with_stream(self):
		(self.project / "result.json").write_text(json.dumps(results()))
		self.install()
		seen = []
		report = testers.run(self.tester, self.project, "en", self.root,
			on_progress=lambda progress, item: seen.append((progress.step, progress.tests_done, item)))
		self.assertIn("--stream", report.data["args"])
		steps = []
		for step, _, _ in seen:
			if not steps or steps[-1] != step:
				steps.append(step)
		self.assertEqual(steps, ["", "subject", "build", "tests"])
		items = [item for _, _, item in seen if item is not None]
		self.assertEqual([item.status for item in items], ["OK", "KO", "WARN", "SKIP", "PASS", "PASS", "PASS", "OOB", "INFO"])
		self.assertEqual(seen[-1][1], 5)
		# The report at the end is the one of the JSON file.
		self.assertEqual(report.test_score, (3, 4))

	def test_the_progress(self):
		progress = testers.Progress()
		progress.update({"event": "plan", "tests": 3})
		progress.update({"event": "step", "step": "tests"})
		progress.update({"event": "test", "name": "strlen/basic", "status": "FAIL", "detail": "got 1", "ms": 1})
		progress.update({"event": "test", "name": "info/strlen_null", "status": "INFO", "detail": "SIGSEGV", "ms": 1})
		self.assertEqual((progress.step, progress.tests_done, progress.tests_total), ("tests", 2, 3))
		self.assertEqual([test.name for test in progress.bad], ["strlen/basic"])
		self.assertIsNone(progress.update({"event": "nothing we know"}))

	def test_an_older_version_kept_gets_no_stream(self):
		"""Not updated: the version installed may not know --stream; its results come at the end."""
		(self.project / "result.json").write_text(json.dumps(results()))
		self.install()
		newer = replace(self.tester, tag="v9.9.10", commit=new_tag(self.repo, "v9.9.10"))
		report = testers.run(newer, self.project, "en", self.root, on_progress=lambda progress, item: None)
		self.assertNotIn("--stream", report.data["args"])
		self.assertEqual(report.test_score, (3, 4))

	def test_without_progress_no_stream(self):
		report = self.run_tester(results())
		self.assertNotIn("--stream", report.data["args"])

	def test_a_launcher_that_is_a_shell_script(self):
		(self.tmp / "shell").mkdir()
		tester, _ = fake_tester(self.tmp / "shell", shell=True)
		(self.project / "result.json").write_text(json.dumps(results()))
		ok, why = testers.install(tester, self.root, environ={})
		self.assertTrue(ok, why)
		report = testers.run(tester, self.project, "en", self.root)
		self.assertIsNone(report.error)
		self.assertEqual(report.test_score, (3, 4))

	def test_a_warning_is_not_a_failure(self):
		data = results(conformity=results()["conformity"][:1], tests=results()["tests"][:3] + [
			{"name": "complexity/medium", "status": "WARN", "detail": "more than O(n√n)", "ms": 0}])
		report = self.run_tester(data)
		self.assertTrue(report.passed)
		medium = report.functions[-1]
		self.assertEqual((medium.name, medium.bad, [test.name for test in medium.warnings]),
			("complexity", [], ["complexity/medium"]))

	def test_the_command_of_the_visualizer(self):
		self.install()
		self.assertIsNone(testers.visualizer_command(self.tester, self.project, "en", self.root))
		tester = replace(self.tester, visualizer=("--visualize",))
		command = testers.visualizer_command(tester, self.project, "fr", self.root)
		self.assertEqual(command[-5:], [str(self.root / "libfterator" / "libfterator"), str(self.project), "--visualize",
			"--lang", "fr"])

	def test_not_installed(self):
		report = testers.run(self.tester, self.project, "en", self.root)
		self.assertIn("not installed", report.error[0])

class TestTheMarker(unittest.TestCase):
	"""A folder is a project of the tester when it has its marker file (with its text, when there is one)."""

	def test_a_file_or_a_file_that_speaks_of_the_project(self):
		with tempfile.TemporaryDirectory() as folder:
			folder = Path(folder)
			libfterator, pushterator = testers.find("libfterator"), testers.find("pushterator")
			(folder / "libft.h").write_text("")
			self.assertTrue(testers.has_marker(libfterator, folder))
			self.assertFalse(testers.has_marker(pushterator, folder))
			(folder / "Makefile").write_text("NAME = libft.a\n")
			self.assertFalse(testers.has_marker(pushterator, folder))
			(folder / "Makefile").write_text("NAME = push_swap\n")
			self.assertTrue(testers.has_marker(pushterator, folder))

class TestFindTheProjects(unittest.TestCase):
	"""The folders that look like the project (libft.h for libfterator), found in the home folder."""

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.home = Path(folder.name)
		self.tester = testers.find("libfterator")

	def project(self, relative):
		path = self.home / relative
		path.mkdir(parents=True)
		(path / "libft.h").write_text("")
		return path

	def test_the_nearest_first(self):
		deep = self.project("42/common_core/rank0/libft")
		near = self.project("libft")
		printf = self.project("42/ft_printf/libft")
		self.assertEqual(testers.find_projects(self.tester, self.home), [near, printf, deep])

	def test_not_in_hidden_folders_nor_too_deep(self):
		self.project(".cache/libft")
		self.project("a/b/c/d/e/libft")
		self.project("node_modules/libft")
		self.assertEqual(testers.find_projects(self.tester, self.home), [])

	def test_a_folder_that_cannot_be_read_is_skipped(self):
		locked = self.home / "locked"
		locked.mkdir()
		locked.chmod(0)
		self.addCleanup(locked.chmod, 0o755)
		near = self.project("libft")
		self.assertEqual(testers.find_projects(self.tester, self.home), [near])

	def test_the_last_one_tested_first(self):
		near = self.project("libft")
		other = self.project("work/libft")
		settings_file = self.home / "settings.json"
		testers.remember_project(self.tester, other, settings_file)
		self.assertEqual(testers.project_choices(self.tester, settings_file, self.home), [other, near])

	def test_the_last_one_tested_even_without_the_marker(self):
		elsewhere = self.home / "elsewhere"
		elsewhere.mkdir()
		settings_file = self.home / "settings.json"
		testers.remember_project(self.tester, elsewhere, settings_file)
		self.assertEqual(testers.project_choices(self.tester, settings_file, self.home), [elsewhere])

class TestTheProjectRemembered(unittest.TestCase):

	def test_the_last_project_of_each_tester(self):
		with tempfile.TemporaryDirectory() as folder:
			path = Path(folder) / "settings.json"
			tester = testers.find("libfterator")
			self.assertIsNone(testers.last_project(tester, path))
			testers.remember_project(tester, "/home/me/libft", path)
			self.assertEqual(testers.last_project(tester, path), "/home/me/libft")
			# The other settings stay.
			data = json.loads(path.read_text())
			data["language"] = "fr"
			path.write_text(json.dumps(data))
			testers.remember_project(tester, "/home/me/other", path)
			self.assertEqual(json.loads(path.read_text())["language"], "fr")
			self.assertEqual(testers.last_project(tester, path), "/home/me/other")

	def test_the_language_given_to_the_tester(self):
		tester = testers.find("libfterator")
		self.assertEqual(testers.tester_language(tester, "fr"), "fr")
		self.assertEqual(testers.tester_language(tester, "en"), "en")
		# libfterator speaks French and English: English for the other languages.
		self.assertEqual(testers.tester_language(tester, "de"), "en")

if __name__ == "__main__":
	unittest.main()

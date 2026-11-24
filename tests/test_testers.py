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

class TesterTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.tmp = Path(folder.name)
		self.root = self.tmp / "testers"
		repo = self.tmp / "repo"
		repo.mkdir()
		launcher = repo / "libfterator"
		launcher.write_text(LAUNCHER)
		launcher.chmod(0o755)
		git(repo, "init", "-q")
		git(repo, "add", ".")
		git(repo, "commit", "-q", "-m", "first")
		git(repo, "tag", "v9.9.9")
		self.repo = repo
		self.tester = replace(testers.TESTERS[0], url=repo.as_uri(), tag="v9.9.9", commit=git(repo, "rev-parse", "HEAD"))
		self.project = self.tmp / "libft"
		self.project.mkdir()

	def install(self):
		ok, why = testers.install(self.tester, self.root, environ={})
		self.assertTrue(ok, why)

class TestTheRegistry(unittest.TestCase):

	def test_libfterator_at_a_tag_and_a_commit_of_its_repository(self):
		tester = testers.find("libfterator")
		self.assertEqual(tester.url, "https://github.com/Blaeste/libfterator.git")
		self.assertTrue(tester.tag.startswith("v2."))
		self.assertRegex(tester.commit, r"^[0-9a-f]{40}$")
		self.assertEqual(tester.launcher, "libfterator")

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
		self.assertTrue(why)
		self.assertEqual(testers.state(self.tester, self.root), testers.MISSING)

	def test_without_git(self):
		ok, why = testers.install(self.tester, self.root, environ={"PATH": str(self.tmp / "nothing")})
		self.assertFalse(ok)
		self.assertIn("git", why)

	def test_a_new_tag_in_42pal_makes_it_outdated_then_installed_again(self):
		self.install()
		(self.repo / "NEW").write_text("new\n")
		git(self.repo, "add", ".")
		git(self.repo, "commit", "-q", "-m", "second")
		git(self.repo, "tag", "v9.9.10")
		newer = replace(self.tester, tag="v9.9.10", commit=git(self.repo, "rev-parse", "HEAD"))
		self.assertEqual(testers.state(newer, self.root), testers.OUTDATED)
		ok, why = testers.install(newer, self.root, environ={})
		self.assertTrue(ok, why)
		self.assertEqual(testers.state(newer, self.root), testers.READY)
		self.assertTrue((self.root / "libfterator" / "NEW").is_file())

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

	def test_not_installed(self):
		report = testers.run(self.tester, self.project, "en", self.root)
		self.assertIn("not installed", report.error[0])

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

"""The testers of projects: downloaded when the student agrees, run, and read.

A tester is an entry of TESTERS: its repository, a tag and the commit of
that tag. install clones the tag into ~/.42pal/testers/<name>/ and checks
the commit: a push on the branch of the tester changes nothing for 42pal,
and a new tag comes with an update of 42pal. run starts the tester on a
project and reads its JSON (never what it prints). The network is only
used by install. Like the rest of the core, this module never prints
(docs/plans/testers.md).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pal42 import settings
from pal42.i18n import N_, t
from pal42.session import STATE_DIR

TESTERS_DIR = STATE_DIR / "testers"

@dataclass(frozen=True)
class Tester:
	"""A tester: what it tests, where it comes from, how it is started."""
	name: str
	# What it tests, and a short line on it, for the menus.
	project: str
	summary: str
	url: str
	tag: str
	commit: str
	# The program at the root of its repository.
	launcher: str
	# Written before the name of each function of its results: ft_strlen.
	prefix: str = ""
	# A file at the root of the project: the folder of 42pal is offered when it has one.
	marker: str = ""
	# The values of sys.platform it runs on (libfterator needs ld --wrap: Linux).
	platforms: tuple = ("linux",)
	# The formats of JSON 42pal can read from it.
	formats: tuple = (1,)
	# The languages it speaks; the others get English.
	languages: tuple = ("en", "fr")

TESTERS = (
	Tester(
		name="libfterator",
		project="libft",
		summary=N_("libft, subject v19.3: the 43 functions, leaks and overflows"),
		url="https://github.com/Blaeste/libfterator.git",
		tag="v2.0.0",
		commit="d0bd761a03c429de19ba9acb749544e03cbc81d8",
		launcher="libfterator",
		prefix="ft_",
		marker="libft.h",
	),
)

# What state() says.
MISSING = "missing"
OUTDATED = "outdated"
READY = "ready"

# Seconds a clone may take, and a run of a tester.
CLONE_TIMEOUT = 120
RUN_TIMEOUT = 600

def find(name):
	"""The tester called `name`, or None."""
	return next((tester for tester in TESTERS if tester.name == name), None)

def available(tester, platform=sys.platform):
	"""True when the tester runs on this system."""
	return any(platform.startswith(name) for name in tester.platforms)

def source(tester, environ=None):
	"""Where the tester is cloned from: its repository, or PAL42_TESTER_<NAME> (a local one, to try it)."""
	environ = os.environ if environ is None else environ
	return environ.get(f"PAL42_TESTER_{tester.name.upper()}") or tester.url

def folder(tester, root=None):
	return Path(root or TESTERS_DIR) / tester.name

def _git(args, environ=None, timeout=CLONE_TIMEOUT):
	"""Run git; return (ok, output). git never asks a question: no password, no passphrase."""
	env = dict(os.environ if environ is None else environ)
	env["GIT_TERMINAL_PROMPT"] = "0"
	env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
	program = shutil.which("git", path=env.get("PATH"))
	if program is None:
		return False, t("git is missing: install it to download the testers.")
	try:
		result = subprocess.run([program, *args], capture_output=True, text=True, timeout=timeout, env=env,
			stdin=subprocess.DEVNULL)
	except subprocess.TimeoutExpired:
		return False, t("git took more than {seconds} s.", seconds=timeout)
	except OSError as error:
		return False, str(error)
	output = (result.stdout + result.stderr).strip()
	return result.returncode == 0, output

def _commit(path):
	ok, output = _git(["-C", str(path), "rev-parse", "HEAD"], timeout=10)
	return output if ok else None

def state(tester, root=None):
	"""MISSING (never downloaded), OUTDATED (another commit than the one of 42pal) or READY."""
	path = folder(tester, root)
	if not (path / tester.launcher).is_file():
		return MISSING
	return READY if _commit(path) == tester.commit else OUTDATED

def install(tester, root=None, environ=None):
	"""Clone the tag of the tester and check its commit; return (ok, why).

	The new copy takes the place of the old one only once checked: a failed
	update keeps the tester as it was.
	"""
	path = folder(tester, root)
	path.parent.mkdir(parents=True, exist_ok=True)
	new = Path(tempfile.mkdtemp(prefix=f".{tester.name}-", dir=path.parent))
	try:
		url = source(tester, environ)
		ok, output = _git(["clone", "--quiet", "--depth", "1", "--branch", tester.tag, url, str(new)], environ)
		if not ok:
			return False, t("{tester} {tag} not found at {url}: {why}", tester=tester.name, tag=tester.tag, url=url,
				why=output.splitlines()[-1] if output else t("git clone failed."))
		commit = _commit(new)
		if commit != tester.commit:
			return False, t("The tag {tag} is at the commit {commit}, not the one expected: nothing was installed.",
				tag=tester.tag, commit=(commit or "?")[:12])
		if path.exists():
			shutil.rmtree(path)
		new.rename(path)
		return True, ""
	finally:
		shutil.rmtree(new, ignore_errors=True)

@dataclass
class Check:
	"""A check of the subject: OK and KO are counted, WARN and SKIP are not."""
	key: str
	group: str
	label: str
	status: str
	detail: str

@dataclass
class TestCase:
	"""A test of the tester: PASS, INFO (an undefined case, not counted), or a failure."""
	name: str
	status: str
	detail: str

	@property
	def function(self):
		return self.name.split("/", 1)[0]

	@property
	def short_name(self):
		return self.name.split("/", 1)[-1]

	@property
	def bad(self):
		return self.status not in ("PASS", "INFO")

@dataclass
class Function:
	"""The tests of a function, in the order of the tester."""
	name: str
	tests: list

	@property
	def bad(self):
		return [test for test in self.tests if test.bad]

	@property
	def total(self):
		return len(self.tests)

	@property
	def passed(self):
		return self.total - len(self.bad)

@dataclass
class Report:
	"""What a tester found; error is (title, detail) when it could not run."""
	checks: list
	tests: list
	error: tuple = None
	notes: list = None
	log: str = None
	lang: str = "en"
	# What the tester printed, and its JSON as it is.
	output: str = ""
	data: dict = None

	@property
	def functions(self):
		functions = []
		for test in self.tests:
			if test.function == "info":
				continue
			if not functions or functions[-1].name != test.function:
				functions.append(Function(test.function, []))
			functions[-1].tests.append(test)
		return functions

	@property
	def info(self):
		return [test for test in self.tests if test.function == "info"]

	@property
	def conformity_score(self):
		"""(OK, OK + KO): WARN and SKIP are not counted."""
		counted = [check for check in self.checks if check.status in ("OK", "KO")]
		return sum(check.status == "OK" for check in counted), len(counted)

	@property
	def test_score(self):
		counted = [test for test in self.tests if test.function != "info"]
		return sum(not test.bad for test in counted), len(counted)

	@property
	def passed(self):
		return (self.error is None and all(check.status != "KO" for check in self.checks)
			and not any(test.bad for test in self.tests))

def failed(title, detail="", output=""):
	"""A report with only an error."""
	return Report([], [], error=(title, detail), output=output)

def parse(data, tester, output=""):
	"""The report of the JSON `data` of `tester`."""
	if not isinstance(data, dict) or data.get("format") not in tester.formats:
		found = data.get("format") if isinstance(data, dict) else None
		return failed(t("{tester} gave results in format {format}: update 42pal to read them.",
			tester=tester.name, format=found), output=output)
	checks = [Check(item.get("key", ""), item.get("group", ""), item.get("label", ""), item.get("status", ""),
		item.get("detail") or "") for item in data.get("conformity") or []]
	tests = [TestCase(item.get("name", ""), item.get("status", ""), item.get("detail") or "")
		for item in data.get("tests") or []]
	error = data.get("error")
	return Report(checks, tests, error=(error.get("title", ""), error.get("detail") or "") if error else None,
		notes=list(data.get("notes") or []), log=data.get("log"), lang=data.get("lang", "en"), output=output,
		data=data)

def run(tester, project, lang="en", root=None, timeout=RUN_TIMEOUT):
	"""Run the tester on the folder `project`, in the language `lang`; return its Report."""
	path = folder(tester, root)
	launcher = path / tester.launcher
	if not launcher.is_file():
		return failed(t("{tester} is not installed.", tester=tester.name))
	with tempfile.TemporaryDirectory(prefix="42pal-tester-") as scratch:
		results = Path(scratch) / "results.json"
		command = [sys.executable, str(launcher), str(project), "--json", str(results), "--no-color", "--lang", lang]
		try:
			finished = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=timeout,
				stdin=subprocess.DEVNULL, cwd=path)
		except subprocess.TimeoutExpired:
			return failed(t("{tester} took more than {seconds} s.", tester=tester.name, seconds=timeout))
		except OSError as error:
			return failed(t("{tester} could not start.", tester=tester.name), str(error))
		output = finished.stdout + finished.stderr
		try:
			data = json.loads(results.read_text(encoding="utf-8"))
		except (OSError, ValueError):
			return failed(t("{tester} gave no results.", tester=tester.name), _tail(output), output)
	return parse(data, tester, output)

def _tail(text, lines=20):
	return "\n".join(text.strip().splitlines()[-lines:])

def tester_language(tester, code):
	"""The language for the tester: the one of 42pal when the tester speaks it, else English."""
	return code if code in tester.languages else "en"

def last_project(tester, path=None):
	"""The project the tester was run on last, or None."""
	value = (settings.load(path).get("testers") or {}).get(tester.name) or {}
	return value.get("project") if isinstance(value, dict) else None

def remember_project(tester, project, path=None):
	"""Keep the project, to offer it the next time."""
	saved = settings.load(path).get("testers") or {}
	saved = dict(saved) if isinstance(saved, dict) else {}
	saved[tester.name] = {**(saved.get(tester.name) or {}), "project": str(project)}
	settings.save({"testers": saved}, path)

"""Tests of pal42.cli: the terminal front-end (display, workspace, shell).

Run all the tests from the project root with: python3 -m unittest -v
"""

import getpass
import os
import subprocess
import io
import tempfile
import unittest
from pathlib import Path
from random import Random

from pal42.cli.shell import Shell
from pal42.catalog import Catalog
from pal42.cli.workspace import Workspace
from pal42.exam import list_exams, load_exam
from pal42.subject import render
from pal42.themes import Theme
from pal42.variant import Variant
from rich.console import Console
from tests.helpers import make_exercise

ROOT = Path(__file__).resolve().parent.parent

# Made-up themes and catalog: one exercise, playable at rank02 levels 2 and 3.
THEMES = {"char_sets": Theme("char_sets", "Compare characters", {"rank02": (2, 3)})}
CATALOG = Catalog({"char_filter": make_exercise()}, [])

class TestVendoredRich(unittest.TestCase):
	"""rich comes from vendor/: nothing to install, no sudo."""

	def test_cli_uses_the_rich_copied_in_vendor(self):
		"""Importing pal42.cli makes the rich of vendor/ importable first."""
		import pal42.cli  # noqa: F401  (imported for its effect on sys.path)
		import rich
		self.assertEqual(Path(rich.__file__).resolve().parent, ROOT / "vendor" / "rich")

class TestWorkspace(unittest.TestCase):
	"""~/42pal_exam/: subjects/, rendu/ and traces/, like at the exam."""

	def setUp(self):
		"""A temporary folder stands for ~/42pal_exam in each test."""
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name) / "42pal_exam"
		self.variant = Variant(load_exam("rank02").exercises_at(2)[0], 0,
			{"mode": "common", "order": "ascii", "separator": "space"})

	def tearDown(self):
		self.tmp.cleanup()

	def test_give_subject_writes_it_and_prepares_the_rendu_folder(self):
		"""subjects/<name>/subject.en.txt holds the subject; rendu/<name>/ waits."""
		workspace = Workspace(self.root)
		path = workspace.give_subject(self.variant)
		self.assertEqual(path, self.root / "subjects/common_chars/subject.en.txt")
		self.assertEqual(path.read_text(encoding="utf-8"), render(self.variant))
		self.assertTrue((self.root / "rendu/common_chars").is_dir())
		self.assertTrue((self.root / "traces").is_dir())

	def test_student_work_already_in_rendu_is_kept(self):
		"""Giving a subject again never deletes what the student wrote."""
		work = self.root / "rendu/common_chars/common_chars.c"
		work.parent.mkdir(parents=True)
		work.write_text("int main(void) { return 0; }\n", encoding="utf-8")
		Workspace(self.root).give_subject(self.variant)
		self.assertEqual(work.read_text(encoding="utf-8"), "int main(void) { return 0; }\n")

class Script:
	"""Answers given in order, as if a student typed them.

	An empty answer takes the default, like pressing Enter. When there is no
	answer left, EOFError is raised, like Ctrl-D.
	"""

	def __init__(self, *answers):
		self.answers = list(answers)
		self.prompts = []

	def ask(self, prompt, default=None):
		self.prompts.append(prompt)
		if not self.answers:
			raise EOFError
		answer = self.answers.pop(0)
		return default if answer == "" and default is not None else answer

	def ask_password(self, prompt):
		self.prompts.append(prompt)
		return self.answers.pop(0)

class FakeClock:
	"""A clock that only moves when the test says so, in seconds."""

	def __init__(self):
		self.now = 1000.0

	def __call__(self):
		return self.now

def make_shell(script, root, clock=None):
	"""A shell that reads `script` and writes into a string, not the screen."""
	console = Console(file=io.StringIO(), width=100, color_system=None)
	return Shell(console, script.ask, script.ask_password, Workspace(root),
		rng=Random(1), clock=clock or FakeClock())

def output(shell):
	"""Everything the shell has printed."""
	return shell.console.file.getvalue()

class TestShell(unittest.TestCase):
	"""The examshell, driven by a Script."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name) / "42pal_exam"

	def tearDown(self):
		self.tmp.cleanup()

	def test_fake_login_takes_any_password_and_keeps_none(self):
		"""The login defaults to the user name; the password is never kept."""
		script = Script("", "my-secret-password")
		shell = make_shell(script, self.root)
		shell.login()
		self.assertEqual(shell.user, getpass.getuser())
		self.assertIn(f"Bienvenue {getpass.getuser()}", output(shell))
		self.assertNotIn("my-secret-password", output(shell))
		self.assertNotIn("my-secret-password", repr(vars(shell)))

	def test_exam_menu_asks_again_until_the_answer_is_valid(self):
		"""Numbered titles; 9 and x are refused, 2 picks the second exam."""
		shell = make_shell(Script("9", "x", "2"), self.root)
		exam = shell.choose_exam()
		self.assertEqual(exam.id, list_exams()[1])
		self.assertIn("1. Exam Piscine", output(shell))
		self.assertIn("2. Exam Rank 02", output(shell))
		self.assertEqual(output(shell).count("Choix invalide"), 2)

	def test_level_choice_only_accepts_playable_levels(self):
		"""Level 1 has no exercise yet: refused; Enter takes the first playable."""
		shell = make_shell(Script("1", ""), self.root)
		level = shell.choose_level(load_exam("rank02", catalog=CATALOG, themes=THEMES))
		self.assertEqual(level, 2)
		self.assertIn("Niveaux jouables : 2, 3", output(shell))
		self.assertEqual(output(shell).count("Choix invalide"), 1)

	def test_start_gives_the_subject_and_says_where_it_is(self):
		"""A subject is drawn at the level, written, and its paths are shown."""
		shell = make_shell(Script(), self.root)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		name = shell.variant.name
		self.assertTrue((self.root / "subjects" / name / "subject.en.txt").exists())
		self.assertTrue((self.root / "rendu" / name).is_dir())
		self.assertIn(name, output(shell))
		self.assertIn(f"subjects/{name}/subject.en.txt", output(shell))
		self.assertIn(f"rendu/{name}/", output(shell))

	def test_commands_help_status_grademe_and_unknown(self):
		"""Each command answers; status shows the time spent and the time left."""
		clock = FakeClock()
		shell = make_shell(Script("help", "status", "grademe", "foo", "finish"), self.root, clock)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		clock.now += 600
		shell.command_loop()
		text = output(shell)
		for command in ["status", "grademe", "finish", "help"]:
			self.assertIn(command, text)
		self.assertIn("0:10:00", text)
		self.assertIn("2:50:00", text)
		self.assertIn("pas encore branché", text)
		self.assertIn("Commande inconnue : foo", text)
		self.assertIn("Fin de l'exam", text)

	def test_ctrl_d_ends_the_exam_cleanly(self):
		"""No answer left (Ctrl-D): the exam ends, nothing crashes."""
		shell = make_shell(Script(), self.root)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		shell.command_loop()
		self.assertIn("Fin de l'exam", output(shell))

	def test_run_goes_from_login_to_finish(self):
		"""Login, exam 2, the first playable level, status, then finish."""
		shell = make_shell(Script("", "pw", "2", "", "status", "finish"), self.root)
		shell.run()
		text = output(shell)
		self.assertIn("Bienvenue", text)
		self.assertIn("Exam Rank 02", text)
		self.assertIn("Temps restant", text)
		self.assertIn("Fin de l'exam", text)
		self.assertEqual(len(list(self.root.glob("subjects/*/subject.en.txt"))), 1)

class TestLauncher(unittest.TestCase):
	"""./42pal with no argument starts the examshell."""

	def test_42pal_starts_the_examshell(self):
		"""Answers sent through a pipe; HOME is a temporary folder."""
		with tempfile.TemporaryDirectory() as home:
			result = subprocess.run(
				[str(ROOT / "42pal")], input="\npw\n2\n\nstatus\nfinish\n",
				capture_output=True, text=True, timeout=30,
				env=dict(os.environ, HOME=home),
				# A new session has no terminal: nothing can wait on the keyboard.
				start_new_session=True,
			)
			self.assertEqual(result.returncode, 0, result.stderr)
			self.assertIn("Bienvenue", result.stdout)
			self.assertIn("Fin de l'exam", result.stdout)
			self.assertEqual(len(list(Path(home).glob("42pal_exam/subjects/*/subject.en.txt"))), 1)

class TestShellQuit(unittest.TestCase):
	"""Leaving before the exam has started."""

	def test_ctrl_d_before_the_exam_says_goodbye(self):
		"""Ctrl-D at the login: the shell says goodbye, nothing crashes."""
		with tempfile.TemporaryDirectory() as tmp:
			shell = make_shell(Script(), Path(tmp))
			shell.run()
			self.assertIn("Au revoir", output(shell))

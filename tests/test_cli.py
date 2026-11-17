"""Tests of pal42.cli: the terminal front-end (display, workspace, shell).

Run all the tests from the project root with: python3 -m unittest -v
"""

import getpass
import os
import pty
import re
import select
import shutil
import subprocess
import time
import io
import tempfile
import unittest
from pathlib import Path
from random import Random

from pal42.cli.shell import Shell
from pal42.catalog import Catalog, load_catalog
from pal42.cli import check, display
from pal42.cli.workspace import Workspace
from pal42.exam import list_exams, load_exam
from pal42.grader import Grade
from pal42.subject import render
from pal42.themes import Theme
from pal42.variant import Variant
from rich.console import Console
from tests.helpers import ECHO, ECHO_OK, echo_oracle, echo_tests, make_exercise

ROOT = Path(__file__).resolve().parent.parent

# Made-up themes and catalog: one exercise, playable at rank02 levels 2 and 3.
THEMES = {"char_sets": Theme("char_sets", "Compare characters", {"rank02": (2, 3)})}
CATALOG = Catalog({"char_filter": make_exercise()}, [])
# echo_first, an exercise that can really be graded, at rank02 levels 1 and 2.
ECHO_THEMES = {"char_sets": Theme("char_sets", "Compare characters", {"rank02": (1, 2)})}
ECHO_CATALOG = Catalog({"echo_first": ECHO.exercise}, [])

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
		self.variant = Variant(load_catalog().exercises["char_filter"], 0,
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
		# A function stands for something done before typing (like letting
		# time pass): it is called, and what it returns is the answer.
		if callable(answer):
			answer = answer()
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
		rng=Random(1), clock=clock or FakeClock(), sleep=lambda seconds: None)

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
		self.assertIn(f"Welcome {getpass.getuser()}!\n\n", output(shell))
		self.assertNotIn("my-secret-password", output(shell))
		self.assertNotIn("my-secret-password", repr(vars(shell)))

	def test_exam_menu_asks_again_until_the_answer_is_valid(self):
		"""Numbered titles; 9 and x are refused, 2 picks the second exam."""
		shell = make_shell(Script("9", "x", "2"), self.root)
		exam = shell.choose_exam()
		self.assertEqual(exam.id, list_exams()[1])
		self.assertIn("1. Exam Piscine", output(shell))
		self.assertIn("2. Exam Rank 02", output(shell))
		self.assertEqual(output(shell).count("Invalid choice"), 2)

	def test_level_choice_only_accepts_playable_levels(self):
		"""Level 1 has no exercise yet: refused; Enter takes the first playable."""
		shell = make_shell(Script("1", ""), self.root)
		level = shell.choose_level(load_exam("rank02", catalog=CATALOG, themes=THEMES))
		self.assertEqual(level, 2)
		self.assertIn("Playable levels: 2, 3", output(shell))
		self.assertEqual(output(shell).count("Invalid choice"), 1)

	def test_retry_mode_menu_shows_the_waits_and_defaults_to_soft(self):
		"""soft and hard with their waits; x is refused, Enter takes soft, 2 hard."""
		exam = load_exam("rank02", catalog=CATALOG, themes=THEMES)
		shell = make_shell(Script("x", ""), self.root)
		self.assertEqual(shell.choose_retry_mode(exam), "soft")
		self.assertIn("1. soft: 0, 1, 2, 3, 5 min", output(shell))
		self.assertIn("2. hard: 0, 5, 10, 20, 40 min", output(shell))
		self.assertEqual(output(shell).count("Invalid choice"), 1)
		self.assertEqual(make_shell(Script("2"), self.root).choose_retry_mode(exam), "hard")

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

	def test_panel_comes_before_the_subject_and_is_as_wide(self):
		"""First the panel (where to read and hand in), 80 wide like the subject."""
		shell = make_shell(Script(), self.root)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		text = output(shell)
		self.assertLess(text.index("Read it"), text.index("Assignment name"))
		top_border = next(line for line in text.splitlines() if line.startswith("╭"))
		self.assertEqual(len(top_border), 80)

	def test_start_also_prints_the_whole_subject(self):
		"""The subject is in subject.en.txt and also printed, as plain text."""
		shell = make_shell(Script(), self.root)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		self.assertIn(render(shell.variant), output(shell))

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
		self.assertIn("Missing file", text)
		self.assertIn("Unknown command: foo", text)
		self.assertIn("End of the exam", text)

	def test_a_blank_line_separates_each_answer_from_the_next_prompt(self):
		"""After each command's answer, a blank line; Enter alone adds nothing."""
		shell = make_shell(Script("foo", "", "bar", "finish"), self.root)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		shell.command_loop()
		text = output(shell)
		self.assertIn("Type help for the list.\n\nUnknown command: bar", text)
		# Both answers are followed by a blank line; Enter alone added none.
		self.assertEqual(text.count("Type help for the list.\n\n"), 2)
		self.assertNotIn("\n\n\n", text.split("Display the characters")[1])

	def test_ctrl_d_ends_the_exam_cleanly(self):
		"""No answer left (Ctrl-D): the exam ends, nothing crashes."""
		shell = make_shell(Script(), self.root)
		shell.start(load_exam("rank02", catalog=CATALOG, themes=THEMES), 2)
		shell.command_loop()
		self.assertIn("End of the exam", output(shell))

	def test_run_goes_from_login_to_finish(self):
		"""Login, exam 2, the first playable level, status, then finish."""
		shell = make_shell(Script("", "pw", "2", "", "", "status", "finish"), self.root)
		shell.run()
		text = output(shell)
		self.assertIn("Welcome", text)
		self.assertIn("Exam Rank 02", text)
		self.assertIn("Time left", text)
		self.assertIn("End of the exam", text)
		self.assertEqual(len(list(self.root.glob("subjects/*/subject.en.txt"))), 1)

class TestLauncher(unittest.TestCase):
	"""./42pal with no argument starts the examshell."""

	def test_42pal_starts_the_examshell(self):
		"""Answers sent through a pipe; HOME is a temporary folder."""
		with tempfile.TemporaryDirectory() as home:
			result = subprocess.run(
				[str(ROOT / "42pal")], input="\npw\n2\n\n\nstatus\nfinish\n",
				capture_output=True, text=True, timeout=30,
				env=dict(os.environ, HOME=home),
				# A new session has no terminal: nothing can wait on the keyboard.
				start_new_session=True,
			)
			self.assertEqual(result.returncode, 0, result.stderr)
			self.assertIn("Welcome", result.stdout)
			self.assertIn("End of the exam", result.stdout)
			self.assertEqual(len(list(Path(home).glob("42pal_exam/subjects/*/subject.en.txt"))), 1)

class TestShellQuit(unittest.TestCase):
	"""Leaving before the exam has started."""

	def test_ctrl_d_before_the_exam_says_goodbye(self):
		"""Ctrl-D at the login: the shell says goodbye, nothing crashes."""
		with tempfile.TemporaryDirectory() as tmp:
			shell = make_shell(Script(), Path(tmp))
			shell.run()
			self.assertIn("Goodbye", output(shell))

class TestTypewriter(unittest.TestCase):
	"""The text that writes itself, one letter at a time."""

	def test_typewriter_prints_one_letter_at_a_time_in_a_terminal(self):
		"""In a terminal: one pause per letter, and the whole text in the end."""
		console = Console(file=io.StringIO(), force_terminal=True, color_system=None)
		pauses = []
		display.typewriter(console, "42pal", sleep=pauses.append)
		self.assertEqual(console.file.getvalue(), "42pal\n")
		self.assertEqual(len(pauses), 5)

	def test_typewriter_prints_at_once_outside_a_terminal(self):
		"""In a pipe or a test: no pause, nothing to wait for."""
		console = Console(file=io.StringIO(), color_system=None)
		pauses = []
		display.typewriter(console, "42pal", sleep=pauses.append)
		self.assertEqual(console.file.getvalue(), "42pal\n")
		self.assertEqual(pauses, [])

@unittest.skipUnless(hasattr(os, "fork"), "needs a pseudo-terminal (Linux, macOS)")
class TestRealTerminal(unittest.TestCase):
	"""./42pal in a pseudo-terminal: what a student really sees on the screen."""

	def test_enter_alone_goes_to_a_new_line(self):
		"""Enter with nothing typed: the next prompt starts on a new line."""
		with tempfile.TemporaryDirectory() as home:
			screen = run_in_terminal(home, [
				("login:", ""), ("password:", "x"), ("choice:", "2"),
				("level:", ""), ("mode:", ""), ("examshell>", ""), ("examshell>", "finish"),
			])
		self.assertNotIn("examshell> examshell>", screen)
		self.assertNotRegex(screen, "login:.*password:")
		self.assertIn("End of the exam", screen)

def run_in_terminal(home, steps, timeout=15):
	"""Run ./42pal in a pseudo-terminal; for each (prompt, answer), wait, then type.

	Returns everything the screen got, without the color codes. With a
	pseudo-terminal, readline and the echo behave as in a real terminal.
	"""
	pid, fd = pty.fork()
	if pid == 0:
		# The child: becomes ./42pal, with HOME set to the temporary folder.
		os.environ["HOME"] = home
		os.execv(str(ROOT / "42pal"), ["42pal"])
	screen = b""
	deadline = time.monotonic() + timeout

	def read_until(text):
		nonlocal screen
		start = len(screen)
		while text.encode() not in screen[start:] and time.monotonic() < deadline:
			if select.select([fd], [], [], 0.1)[0]:
				try:
					screen += os.read(fd, 4096)
				except OSError:
					return

	for prompt, answer in steps:
		read_until(prompt)
		os.write(fd, answer.encode() + b"\r")
	read_until("End of the exam")
	os.waitpid(pid, 0)
	os.close(fd)
	return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", screen.decode(errors="replace")).replace("\r", "")

class TestGrademe(unittest.TestCase):
	"""grademe in the shell: grade, show the result and the trace, move on."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name) / "42pal_exam"
		self.exam = load_exam("rank02", catalog=ECHO_CATALOG, themes=ECHO_THEMES)

	def tearDown(self):
		self.tmp.cleanup()

	def start(self, level, *answers):
		"""A shell at `level` of the exam, which will read `answers`."""
		self.script = Script(*answers)
		shell = make_shell(self.script, self.root)
		shell.start(self.exam, level)
		return shell

	def hand_in(self, code):
		"""Write the student's echo_first.c in rendu/echo_first/."""
		(self.root / "rendu/echo_first/echo_first.c").write_text(code, encoding="utf-8")

	def test_right_solution_gives_ok_a_log_and_the_next_level(self):
		"""OK with 3/3, a log in traces/ shown with its path, then level 2."""
		shell = self.start(1, "grademe", "finish")
		self.hand_in(ECHO_OK)
		shell.command_loop()
		text = output(shell)
		self.assertIn("OK", text)
		self.assertIn("3/3", text)
		log = self.root / "traces/01_echo_first.trace"
		self.assertIn("OK", log.read_text(encoding="utf-8"))
		self.assertIn("traces/01_echo_first.trace", text)
		self.assertEqual(shell.level, 2)

	def test_last_level_passed_ends_the_exam(self):
		"""grademe OK at the last playable level: the exam is passed and over."""
		shell = self.start(2, "grademe")
		self.hand_in(ECHO_OK)
		shell.command_loop()
		self.assertIn("Exam passed", output(shell))
		self.assertEqual(len(self.script.prompts), 1)

	def test_wrong_solution_shows_the_trace_and_keeps_the_subject(self):
		"""KO: the trace in the terminal and in traces/; same subject, same level."""
		shell = self.start(1, "grademe", "finish")
		subject = shell.variant
		self.hand_in(ECHO_OK.replace('\twrite(1, "\\n", 1);\n', ""))
		shell.command_loop()
		text = output(shell)
		self.assertIn("KO", text)
		self.assertIn("-hello", text)
		self.assertIn("Diff KO", text)
		# The 80-wide lines of the trace fit in its frame: none is cut in two.
		self.assertIn("= Test 1 " + "=" * 71, text)
		log = self.root / "traces/01_echo_first.trace"
		self.assertIn("Diff KO", log.read_text(encoding="utf-8"))
		self.assertEqual((shell.level, shell.variant), (1, subject))

	def test_long_trace_is_cut_on_screen_but_whole_in_the_file(self):
		"""60 wrong lines: the start on screen, a note, all of it in the file."""
		shell = self.start(1, "grademe", "finish")
		self.hand_in(
			"#include <unistd.h>\n\nint\tmain(void)\n{\n\tfor (int i = 0; i < 60; i++)\n"
			"\t\twrite(1, \"x\\n\", 2);\n\treturn (0);\n}\n"
		)
		shell.command_loop()
		self.assertIn("more lines", output(shell))
		log = self.root / "traces/01_echo_first.trace"
		self.assertEqual(log.read_text(encoding="utf-8").count("-x$"), 60)

	def test_the_animation_lasts_long_enough_to_be_seen_in_a_terminal(self):
		"""In a terminal, a quick grading still shows the spinner a moment."""
		pauses = []
		console = Console(file=io.StringIO(), width=100, force_terminal=True, color_system=None)
		shell = Shell(console, Script("grademe", "finish").ask, None, Workspace(self.root),
			rng=Random(1), clock=FakeClock(), sleep=pauses.append)
		shell.start(self.exam, 1)
		self.hand_in(ECHO_OK)
		shell.command_loop()
		self.assertGreater(sum(pauses), 0.5)

class TestGrademeWithLeaks(unittest.TestCase):
	"""grademe on an exercise that checks leaks."""

	def test_grade_result_shows_the_warnings(self):
		"""What could not be checked is said, under the verdict."""
		result = Grade(True, "", 3, 3, ("valgrind not found: memory leaks were not checked",))
		console = Console(file=io.StringIO(), width=100, color_system=None)
		console.print(display.grade_result(result, Path("/tmp/01_x.trace")))
		self.assertIn("valgrind not found", console.file.getvalue())

	@unittest.skipUnless(shutil.which("valgrind"), "valgrind is not installed")
	def test_grademe_checks_the_leaks_without_crashing(self):
		"""The spinner gets a third argument for the leak step: no crash, OK."""
		exo = make_exercise(
			name="echo_first", expected_files=("echo_first.c",),
			oracle=echo_oracle, generate_tests=echo_tests, check_leaks=True,
		)
		exam = load_exam("rank02", catalog=Catalog({"echo_first": exo}, []), themes=ECHO_THEMES)
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp) / "42pal_exam"
			shell = make_shell(Script("grademe"), root)
			shell.start(exam, 2)
			(root / "rendu/echo_first/echo_first.c").write_text(ECHO_OK, encoding="utf-8")
			shell.command_loop()
			self.assertIn("✓ OK", output(shell))

class TestCheckCatalog(unittest.TestCase):
	"""check_catalog(): every ref.c against its oracle, for the whole catalog."""

	def run_check(self, catalog=None):
		"""Run the check; return its exit code and what it printed."""
		console = Console(file=io.StringIO(), width=120, color_system=None)
		code = check.check_catalog(console, catalog)
		return code, console.file.getvalue()

	def test_real_catalog_passes(self):
		"""Every ref.c agrees with its oracle: exit code 0."""
		code, text = self.run_check()
		self.assertEqual(code, 0, text)
		self.assertIn("char_filter", text)
		self.assertIn("Catalog OK", text)

	def test_wrong_oracle_fails_naming_the_variant_and_the_test(self):
		"""An oracle that shouts: exit code 1, broken#seed and the test named."""
		exo = make_exercise(
			name="broken", expected_files=("broken.c",),
			oracle=lambda params, test: echo_oracle(params, test).upper(),
			generate_tests=echo_tests,
		)
		with tempfile.TemporaryDirectory() as folder:
			(Path(folder) / "ref.c").write_text(ECHO_OK, encoding="utf-8")
			code, text = self.run_check(Catalog({"broken": exo}, [], {"broken": Path(folder)}))
		self.assertEqual(code, 1)
		self.assertRegex(text, r"broken#\d+")
		self.assertIn("= Test 1", text)
		self.assertIn("Catalog KO", text)

	def test_missing_ref_c_and_catalog_warnings_fail(self):
		"""No ref.c, or a folder skipped by the catalog: both are errors here."""
		with tempfile.TemporaryDirectory() as folder:
			catalog = Catalog({"lonely": make_exercise(name="lonely")},
				["c/empty: no exercise.py, folder skipped"], {"lonely": Path(folder)})
			code, text = self.run_check(catalog)
		self.assertEqual(code, 1)
		self.assertIn("lonely: no ref.c", text)
		self.assertIn("c/empty: no exercise.py", text)

class TestRetryTimer(unittest.TestCase):
	"""The wait between two grademe, in hard mode: 0, 5, 10, 20, 40 minutes."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name) / "42pal_exam"
		self.exam = load_exam("rank02", catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		self.clock = FakeClock()

	def tearDown(self):
		self.tmp.cleanup()

	def run_commands(self, *answers, code=None):
		"""Start at level 1 in hard mode, hand in `code` (wrong by default), run."""
		shell = make_shell(Script(*answers), self.root, self.clock)
		shell.retry = self.exam.retry["hard"]
		shell.start(self.exam, 1)
		(self.root / "rendu/echo_first/echo_first.c").write_text(
			code or "int\tmain(void)\n{\n\treturn (0);\n}\n", encoding="utf-8")
		shell.command_loop()
		return shell

	def logs(self):
		return sorted(path.name for path in (self.root / "traces").glob("*.trace"))

	def test_first_failure_is_free(self):
		"""After the first KO, grademe can run again at once."""
		shell = self.run_commands("grademe", "grademe", "finish")
		self.assertEqual(output(shell).count("✗ KO"), 2)
		self.assertEqual(self.logs(), ["01_echo_first.trace", "02_echo_first.trace"])

	def test_after_the_second_failure_grademe_must_wait(self):
		"""Second KO: 5 minutes to wait; a grademe before is refused, not counted."""
		shell = self.run_commands("grademe", "grademe", "grademe", "finish")
		text = output(shell)
		self.assertIn("Next grademe in 0:05:00", text)
		self.assertIn("if KO again: 0:10:00", text)
		self.assertIn("Wait 0:05:00 before your next grademe", text)
		self.assertEqual(len(self.logs()), 2)

	def test_grademe_works_again_once_the_wait_is_over(self):
		"""5 minutes later, the third grademe runs."""
		def five_minutes_later():
			self.clock.now += 300
			return "grademe"
		shell = self.run_commands("grademe", "grademe", five_minutes_later, "finish")
		self.assertEqual(len(self.logs()), 3)
		self.assertNotIn("Wait", output(shell))

	def test_each_grademe_warns_of_the_wait_if_it_fails(self):
		"""Before grading: what a KO would cost. First time: right away."""
		shell = self.run_commands("grademe", "grademe", "finish")
		text = output(shell)
		self.assertIn("If KO: next grademe right away", text)
		self.assertIn("If KO: next grademe in 0:05:00", text)

	def test_status_shows_the_next_grademe_and_the_cost_of_a_ko(self):
		"""After two KO: next grademe in 5 minutes, and 10 if the next one fails."""
		shell = self.run_commands("grademe", "grademe", "status", "finish")
		text = output(shell)
		self.assertRegex(text, r"Next grademe\s+in 0:05:00")
		self.assertRegex(text, r"If KO\s+0:10:00")

	def test_ok_resets_the_count_of_failures(self):
		"""KO, KO, then OK (5 minutes later): the next subject starts with no wait."""
		def fix_it_and_wait():
			self.clock.now += 300
			(self.root / "rendu/echo_first/echo_first.c").write_text(ECHO_OK, encoding="utf-8")
			return "grademe"
		shell = self.run_commands("grademe", "grademe", fix_it_and_wait, "status", "finish")
		self.assertEqual(shell.level, 2)
		self.assertEqual(shell.failures, 0)
		self.assertRegex(output(shell), r"Next grademe\s+now")

class TestExamTime(unittest.TestCase):
	"""The exam ends when its time is up (rank02: 180 minutes)."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name) / "42pal_exam"
		self.exam = load_exam("rank02", catalog=ECHO_CATALOG, themes=ECHO_THEMES)
		self.clock = FakeClock()

	def tearDown(self):
		self.tmp.cleanup()

	def later(self, minutes, command):
		"""An answer typed `minutes` later: the clock moves, then `command`."""
		def answer():
			self.clock.now += minutes * 60
			return command
		return answer

	def run_commands(self, *answers, code=ECHO_OK):
		self.script = Script(*answers)
		shell = make_shell(self.script, self.root, self.clock)
		shell.start(self.exam, 1)
		(self.root / "rendu/echo_first/echo_first.c").write_text(code, encoding="utf-8")
		shell.command_loop()
		return shell

	def test_time_up_ends_the_exam_at_the_next_command(self):
		"""181 minutes later, status is not run: time is up, the exam ends."""
		shell = self.run_commands(self.later(181, "status"), "help")
		text = output(shell)
		self.assertIn("Time is up", text)
		self.assertIn("End of the exam", text)
		self.assertNotIn("Time spent  ", text.split("Time is up")[0])
		self.assertEqual(len(self.script.prompts), 1)

	def test_grademe_after_the_time_is_up_is_not_graded(self):
		"""A right solution, but too late: not graded, no log."""
		shell = self.run_commands(self.later(200, "grademe"))
		self.assertIn("Time is up", output(shell))
		self.assertEqual(list((self.root / "traces").glob("*.trace")), [])
		self.assertEqual(shell.level, 1)

	def test_a_warning_once_when_less_than_ten_minutes_are_left(self):
		"""171 minutes in: one warning, not repeated at the next command."""
		shell = self.run_commands(self.later(171, "help"), self.later(1, "help"), "finish")
		self.assertEqual(output(shell).count("Less than 10 minutes left"), 1)

	def test_the_end_of_the_exam_shows_a_summary(self):
		"""One OK (level 1), then finish: levels passed, grademe, time spent."""
		shell = self.run_commands("grademe", self.later(30, "finish"))
		text = output(shell)
		self.assertIn("Summary", text)
		self.assertRegex(text, r"Levels passed\s+1")
		self.assertRegex(text, r"Grademe\s+1 \(1 OK, 0 KO\)")
		self.assertRegex(text, r"Time spent\s+0:30:00")

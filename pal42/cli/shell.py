"""The examshell: fake login, choice of the exam and level, then commands.

Its input and output are given to it (ask, ask_password, console), so the
tests can drive it with answers written in advance; main() gives it the real
keyboard and terminal.
"""

import getpass
import random
import sys
import time
from datetime import datetime

from rich.console import Console
from rich.markup import escape

from pal42.catalog import load_catalog
from pal42.cli import display
from pal42.cli.workspace import Workspace
from pal42.exam import ExamError, list_exams, load_exam
from pal42.grader import grade
from pal42.retry import RetryPolicy
from pal42.runners.c import CRunner
from pal42.session import Session, SessionStore
from pal42.themes import load_themes

# The examshell commands and what they do, shown by help.
COMMANDS = {
	"status": "where you are: exam, level, subject, time",
	"grademe": "grade your work",
	"finish": "end the exam",
	"help": "show this help",
}

# Under this many seconds left, the student is warned once.
WARNING_SECONDS = 10 * 60

# The grademe spinner stays at least this long, even if the grading is quicker.
ANIMATION_SECONDS = 0.8

class Shell:
	"""One exam session in the terminal.

	ask(prompt, default) returns what the student types, ask_password(prompt)
	reads without showing it, and console is a rich Console. clock gives the
	time in seconds since 1970, so that a saved exam can be resumed later.
	store (a SessionStore) saves the exam in progress and the history; with
	None, nothing is saved. catalog and themes are loaded when not given.
	"""

	def __init__(self, console, ask, ask_password, workspace=None, rng=None,
			clock=time.time, sleep=time.sleep, retry_mode="soft",
			store=None, catalog=None, themes=None):
		self.console = console
		self.ask = ask
		self.ask_password = ask_password
		self.workspace = workspace or Workspace()
		self.rng = rng or random.Random()
		self.clock = clock
		# For the typewriter animation; the tests give one that does not wait.
		self.sleep = sleep
		self.user = None
		# "soft" or "hard" (./42pal --hard): its waits are taken from the exam.
		self.retry_mode = retry_mode
		self._reset()
		self.store = store
		self.catalog = catalog
		self.themes = themes

	def _reset(self):
		"""No exam in progress: the state before an exam starts."""
		# Set by start(): the exam, the level, the subject and when it began.
		self.exam = None
		self.level = None
		self.variant = None
		self.started_at = None
		# Number of grademe so far: it numbers the logs in traces/.
		self.attempts = 0
		# The waits after a failure, the failures on the current subject, and
		# when grademe is allowed again.
		self.retry = RetryPolicy((0,))
		self.failures = 0
		self.next_grademe_at = None
		# For the summary: the levels passed and the grademe that passed.
		self.passed_levels = []
		self.oks = 0
		# True once the "less than 10 minutes" warning has been given.
		self.warned = False

	def run(self):
		"""The whole session: login, exam (or the saved one), then the commands."""
		try:
			self.login()
			if not self.resume():
				exam = self.choose_exam()
				level = self.choose_level(exam)
				self.retry = exam.retry[self.retry_mode]
				self.start(exam, level)
		# Ctrl-D before the exam has started: just leave.
		except EOFError:
			self.console.print("\nGoodbye!")
			return
		self.command_loop()

	def login(self):
		"""Fake login, like at the exam: any password, never checked or kept."""
		display.typewriter(self.console, "42pal · examshell", sleep=self.sleep)
		self.user = self.ask("login:", getpass.getuser())
		# The password is read, then dropped at once: not checked, not stored.
		self.ask_password("password: ")
		display.typewriter(self.console, f"Welcome {self.user}!", sleep=self.sleep)
		self.console.print()

	def resume(self):
		"""Offer to resume the saved exam; return True if it was resumed.

		An exam whose time ran out while away goes to the history without a
		question; one whose subject is gone cannot be resumed. Refusing keeps
		it in the history as "abandoned".
		"""
		session = self.store.load() if self.store else None
		if session is None:
			return False
		catalog, themes = self._catalog()
		try:
			exam = load_exam(session.exam, catalog=catalog, themes=themes)
		except ExamError:
			exam = None
		variant = catalog.variant(session.variant)
		if exam is None or variant is None:
			self.store.clear()
			self.console.print(display.cannot_resume(session.variant))
			return False
		self._restore(session, exam, variant)
		left = self._time_left()
		if left <= 0:
			self.console.print(display.time_ran_out_while_away(exam))
			self._forget("time")
			return False
		answer = self.ask(display.resume_question(exam, self.level, variant, left), "y")
		if answer.strip().lower().startswith("n"):
			self._forget("abandoned")
			return False
		self._show_subject()
		return True

	def _restore(self, session, exam, variant):
		"""Put back the state of a saved exam."""
		self.exam, self.level, self.variant = exam, session.level, variant
		self.started_at = session.started_at
		self.retry_mode = session.retry_mode
		self.retry = exam.retry[session.retry_mode]
		self.attempts, self.oks, self.failures = session.attempts, session.oks, session.failures
		self.passed_levels = list(session.passed_levels)
		self.next_grademe_at = session.next_grademe_at
		self.warned = session.warned

	def _forget(self, end):
		"""Keep the restored exam in the history as `end`, then start afresh."""
		elapsed = min(self.clock() - self.started_at, self.exam.duration_minutes * 60)
		self.store.add_history(self._history_entry(end, elapsed))
		self.store.clear()
		self._reset()

	def choose_exam(self):
		"""Show the exams as a numbered menu and return the one picked."""
		catalog, themes = self._catalog()
		exams = [load_exam(exam_id, catalog=catalog, themes=themes) for exam_id in list_exams()]
		# An exam with no exercise at any level cannot be played: not offered.
		exams = [exam for exam in exams if exam.playable_levels]
		self.console.print("Choose your exam:")
		for number, exam in enumerate(exams, start=1):
			self.console.print(f"  {number}. {exam.title}")
		number = self._ask_choice("Your choice:", range(1, len(exams) + 1))
		return exams[number - 1]

	def choose_level(self, exam):
		"""Ask the starting level, among the levels that have exercises."""
		playable = exam.playable_levels
		self.console.print(f"Playable levels: {', '.join(map(str, playable))}")
		# Enter alone takes the first playable level.
		return self._ask_choice("Starting level:", playable, str(playable[0]))

	def start(self, exam, level):
		"""Draw a subject at `level`, write it in the workspace and show it.

		The exam's clock starts with the first subject only: passing a level
		does not give more time.
		"""
		self.exam = exam
		self.level = level
		self.variant = exam.draw(level, self.rng)
		if self.started_at is None:
			self.started_at = self.clock()
		self._show_subject()
		self._save()

	def _show_subject(self):
		"""Write the current subject in the workspace and show it."""
		exam, level = self.exam, self.level
		subject = self.workspace.give_subject(self.variant)
		rendu = self.workspace.rendu / self.variant.name
		# First the panel (where to read and hand in), then the subject as
		# plain text: markup=False so that rich changes nothing, and no frame,
		# so that the examples can be copied as they are.
		self.console.print()
		self.console.print(display.subject_panel(
			exam, level, self.variant, subject, rendu, self.retry_mode,
		))
		self.console.print()
		self.console.print(subject.read_text(encoding="utf-8"), markup=False, highlight=False, end="")
		self.console.print()

	def command_loop(self):
		"""Read and run the examshell commands until the exam ends.

		It ends with finish, Ctrl-D, the last level passed, or when the time
		is up: the time is checked each time a command is typed, so a command
		typed too late is not run.
		"""
		while True:
			try:
				command = self.ask("examshell>").strip()
			# Ctrl-D: the same as finish.
			except EOFError:
				command = "finish"
			left = self._time_left()
			if left <= 0:
				self.console.print(display.time_up())
				self.end_exam("time")
				return
			if left < WARNING_SECONDS and not self.warned:
				self.warned = True
				self.console.print(display.almost_over(left))
			if command == "finish":
				self.end_exam()
				return
			if command == "help":
				self.console.print(display.help_table(COMMANDS))
			elif command == "status":
				self.show_status()
			elif command == "grademe":
				if self.grademe():
					return
			elif command:
				# escape: what the student typed must not be read as rich markup.
				self.console.print(f"Unknown command: {escape(command)}. Type help for the list.")
			# A blank line after each answer sets it apart from the next prompt;
			# Enter alone gave no answer, so it adds nothing.
			if command:
				self.console.print()
			self._save()

	def grademe(self):
		"""Grade the rendu and show the result; return True when the exam is over.

		Passed: the next playable level, with a new subject, or the end of the
		exam after the last one. Failed: the trace, the same subject, and a
		wait before the next grademe that grows with each failure.
		"""
		wait = self._wait_left()
		if wait > 0:
			# Too early: refused, and not counted as an attempt.
			self.console.print(display.wait_message(wait))
			return False
		# What a KO would cost, said before grading.
		self.console.print(display.retry_preview(self.retry.wait_after(self.failures + 1)))
		self.attempts += 1
		rendu = self.workspace.rendu / self.variant.name
		runner = CRunner(self.exam.compile_command)
		# A spinner while grading, with the number of the test being run;
		# rich shows it only in a real terminal.
		with self.console.status("Grading…", spinner="dots") as status:
			# step is "memory" when the tests run again under valgrind.
			def progress(number, total, step="output"):
				doing = "Checking memory" if step == "memory" else "Grading"
				status.update(f"{doing}… test {number}/{total}")
			started = self.clock()
			result = grade(self.variant, rendu, runner, progress)
			# A grading often takes a tenth of a second: the spinner stays a
			# moment, so that it can be seen. Only in a real terminal.
			left = ANIMATION_SECONDS - (self.clock() - started)
			if self.console.is_terminal and left > 0:
				self.sleep(left)
		log_text = result.trace or f"OK: {result.tests_passed}/{result.tests_total} tests passed\n"
		log = self.workspace.write_trace(self.attempts, self.variant.name, log_text)
		self.console.print(display.grade_result(result, log))
		if not result.passed:
			self.console.print(display.trace_panel(result.trace))
			self.failures += 1
			wait = self.retry.wait_after(self.failures)
			self.next_grademe_at = self.clock() + wait
			self.console.print(display.next_grademe(wait, self.retry.wait_after(self.failures + 1)))
			return False
		# Passed: the next subject starts with no failure and no wait.
		self.failures = 0
		self.next_grademe_at = None
		self.oks += 1
		self.passed_levels.append(self.level)
		next_levels = [level for level in self.exam.playable_levels if level > self.level]
		if not next_levels:
			self.console.print(display.exam_passed_panel(self.exam))
			self.end_exam("passed")
			return True
		self.start(self.exam, next_levels[0])
		return False

	def end_exam(self, end="finish"):
		"""Show the summary of the exam, keep it in the history, say goodbye.

		end tells how it ended: "finish", "time" (time up) or "passed".
		"""
		elapsed = self.clock() - self.started_at
		self.console.print(display.summary_table(
			self.exam, self.passed_levels, self.attempts, self.oks, elapsed,
		))
		if self.store:
			self.store.add_history(self._history_entry(end, elapsed))
			self.store.clear()
		self.console.print("End of the exam. See you soon!")

	def _history_entry(self, end, elapsed):
		"""What the history keeps of a finished exam: the base of a future score."""
		return {
			"exam": self.exam.id,
			"title": self.exam.title,
			"ended_at": datetime.fromtimestamp(self.clock()).isoformat(timespec="seconds"),
			"levels_passed": self.passed_levels,
			"attempts": self.attempts,
			"oks": self.oks,
			"seconds": round(elapsed),
			"retry_mode": self.retry_mode,
			"end": end,
		}

	def _save(self):
		"""Save the exam in progress, to resume it if the terminal is closed."""
		if self.store and self.variant:
			self.store.save(Session(
				self.exam.id, self.level, self.variant.id, self.started_at,
				self.retry_mode, self.attempts, self.oks, self.failures,
				self.passed_levels, self.next_grademe_at, self.warned,
			))

	def _catalog(self):
		"""Return the catalog and the themes, loading them the first time."""
		if self.catalog is None:
			self.themes = self.themes or load_themes()
			self.catalog = load_catalog(themes=self.themes)
		return self.catalog, self.themes or load_themes()

	def _time_left(self):
		"""Seconds left before the end of the exam (0 or less: over)."""
		return self.exam.duration_minutes * 60 - (self.clock() - self.started_at)

	def show_status(self):
		"""Show the exam, the level, the subject, the times and the next grademe."""
		elapsed = self.clock() - self.started_at
		left = max(0, self._time_left())
		if_ko = self.retry.wait_after(self.failures + 1)
		self.console.print(display.status_table(
			self.exam, self.level, self.variant, elapsed, left, self._wait_left(), if_ko,
			f"{self.retry_mode} ({', '.join(map(str, self.retry.minutes))} min)",
		))

	def _wait_left(self):
		"""Seconds left before the next grademe is allowed (0: now)."""
		if self.next_grademe_at is None:
			return 0
		return max(0, self.next_grademe_at - self.clock())

	def _ask_choice(self, prompt, allowed, default=None):
		"""Ask until the answer is one of the numbers of `allowed`; return it."""
		allowed = list(allowed)
		while True:
			answer = self.ask(prompt, default)
			if answer.isdigit() and int(answer) in allowed:
				return int(answer)
			choices = ", ".join(map(str, allowed))
			self.console.print(f"Invalid choice: type one of these numbers: {choices}.")

def main(retry_mode="soft"):
	"""Start the examshell on the real keyboard and terminal; return the exit code.

	retry_mode is "soft", or "hard" with ./42pal --hard.
	"""
	# Once imported, readline gives input() the arrow keys: history and editing.
	try:
		import readline  # noqa: F401
	except ImportError:
		pass
	console = Console()

	def ask(prompt, default=None):
		"""Read a line; Enter alone gives `default`, shown in brackets."""
		shown = f"{prompt} [{default}] " if default else f"{prompt} "
		# The prompt goes to input() itself, not printed before by rich:
		# readline must know it, or Enter alone stays on the same line.
		answer = input(shown).strip()
		return answer if answer or default is None else default

	def ask_password(prompt):
		"""Read without showing what is typed, when the input is a terminal."""
		if sys.stdin.isatty():
			return getpass.getpass(prompt)
		# Answers sent through a pipe: getpass would wait on the keyboard.
		return input(prompt)

	try:
		Shell(console, ask, ask_password, retry_mode=retry_mode, store=SessionStore()).run()
	except KeyboardInterrupt:
		console.print("\nExam stopped (Ctrl-C): run ./42pal again to resume it.")
		return 130
	return 0

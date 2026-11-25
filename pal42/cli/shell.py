"""The examshell: fake login, choice of the exam and level, then commands.

Its input and output are given to it (ask, ask_password, console), so the
tests can drive it with answers written in advance; main() gives it the real
keyboard and terminal.
"""

import getpass
import math
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from pal42 import cheat, i18n, settings
from pal42 import testers as testers_core
from pal42.i18n import N_, t
from pal42.catalog import load_catalog
from pal42.cli import display
from pal42.cli.workspace import Workspace
from pal42.exam import AUDIENCES, ExamError, list_exams, load_exam
from pal42.grader import grade
from pal42.retry import RetryPolicy
from pal42.runners import runner_for
from pal42.progress import exam_rows, summary, weak_themes
from pal42.report import full_report
from pal42.session import STATE_DIR, Session, SessionStore
from pal42.themes import load_themes
from pal42.update import apply_update, restart

# The examshell commands and what they do, shown by help.
# The names stay, like the commands of the real examshell; what they do is
# translated where it is shown (N_, see pal42/i18n.py).
COMMANDS = {
	"status": N_("where you are: exam, level, subject, time"),
	"grademe": N_("grade your work"),
	"report": N_("write a report for an issue: subject, your code, last trace"),
	"finish": N_("end the exam"),
	"back": N_("back to the menus (asks first)"),
	"help": N_("show this help"),
}

# One letter (then Enter) for each command: g, s, r, f, b and ?.
SHORTCUTS = {"g": "grademe", "s": "status", "r": "report", "f": "finish", "b": "back", "?": "help"}

# The two modes and the waits each one takes from the exam file: the exam
# mode is 42_EXAM's (hard waits, the real duration), the revision mode is
# softer (soft waits, no time limit).
RETRY_OF_MODE = {"exam": "hard", "revision": "soft"}

# Under this many seconds left, the student is warned once.
WARNING_SECONDS = 10 * 60

# The grademe spinner stays at least this long, even if the grading is quicker.
ANIMATION_SECONDS = 0.8

def make_completer(commands):
	"""Return readline's completer for `commands`.

	readline calls it with the text typed and state 0, 1, 2... until it
	returns None, then completes (one match) or lists the matches (several).
	"""
	def complete(text, state):
		matches = [command for command in commands if command.startswith(text)]
		return matches[state] if state < len(matches) else None
	return complete

# The completer of the examshell commands.
complete_command = make_completer(COMMANDS)

# What a menu returns when its last choice is picked: back to the menu before,
# or quit when it is the first menu shown.
BACK = object()

# The choices of the first menu that lead to practice, or to the progress, instead of an exam.
PRACTICE = "practice"
PROGRESS = "progress"
# Settings, in the first menu: the language of 42pal.
SETTINGS = "settings"
# Testers, in the first menu: the testers of projects (pal42/testers.py).
TESTERS = "testers"
# The choices of the first menu that come back to it.
SIDE_CHOICES = (PRACTICE, PROGRESS, SETTINGS, TESTERS)

class Shell:
	"""One exam session in the terminal.

	ask(prompt, default) returns what the student types, ask_password(prompt)
	reads without showing it, and console is a rich Console. clock gives the
	time in seconds since 1970, so that a saved exam can be resumed later.
	store (a SessionStore) saves the exam in progress and the history; with
	None, nothing is saved. catalog and themes are loaded when not given.
	"""

	def __init__(self, console, ask, ask_password, workspace=None, rng=None,
			clock=time.time, sleep=time.sleep, mode="exam",
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
		# How many menus have been shown: tells choose_start which ones were.
		self.menus_shown = 0
		# "exam" or "revision", chosen in a menu by run().
		self.mode = mode
		self._reset()
		self.store = store
		self.catalog = catalog
		self.themes = themes
		# The check for a newer 42pal started at launch (an UpdateCheck), the
		# function that pulls it, and True once pulled: 42pal must restart.
		self.update_check = None
		self.updater = apply_update
		self.restart = False
		# The encrypted cheat menu: cheat.PACK unless a test gives its own.
		self.cheat_pack = None
		# Where Settings keeps the language (None: ~/.42pal/settings.json).
		self.settings_file = None
		# True once back was confirmed: the commands stop, the menus come again.
		self.back_requested = False
		# The testers offered (None: those of pal42/testers.py this system runs),
		# where they are kept (None: ~/.42pal/testers) and the environment of
		# their download (None: the one of 42pal). The tests give their own.
		self.tester_list = None
		self.testers_root = None
		self.testers_environ = None
		# How a command runs on the terminal (the visualizer of a tester; the tests give their own).
		self.run_command = subprocess.run
		# Where the folders of a project are looked for (None: the home folder).
		self.projects_root = None

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
		# True once the cheat menu was used: the history says so.
		self.cheated = False
		# The last trace written by grademe, and the last report written.
		self.last_trace = None
		self.last_report = None

	def run(self):
		"""The whole session: login, exam (or the saved one), then the commands.

		back during an exam (after a wrong click in the menus) comes to the
		first menu again.
		"""
		try:
			self.login()
			if self.offer_update():
				return
			resumed = self.resume()
		# Ctrl-D before the exam has started: just leave.
		except EOFError:
			self.console.print("\n" + t("Goodbye!"))
			return
		while True:
			if not resumed and not self._start_from_menus():
				return
			resumed = False
			self.command_loop()
			if not self.back_requested:
				return
			self.back_requested = False
			self.leave_exam()
			self.console.print()

	def _start_from_menus(self):
		"""The menus until an exam begins (True); False once the session is over (quit, a practice done)."""
		try:
			start = self.choose_start()
			while start in SIDE_CHOICES:
				if start == SETTINGS:
					self.choose_settings()
				elif start == TESTERS:
					self.choose_tester()
				else:
					theme = self.show_progress() if start == PROGRESS else None
					if (start == PRACTICE or theme is not None) and self.practise(theme):
						return False
				start = self.choose_start()
			if start is None:
				self.console.print(t("Goodbye!"))
				return False
			self.begin(*start)
			return True
		# Ctrl-D in a menu: just leave.
		except EOFError:
			self.console.print("\n" + t("Goodbye!"))
			return False

	def back_consequence(self):
		"""What going back to the menus does to the exam: said before the student confirms."""
		if self.attempts:
			return t("This exam goes to your history as abandoned.")
		return t("Nothing is kept: no grademe was made yet.")

	def confirm_back(self):
		"""Ask before going back to the menus; True when the student says yes."""
		answer = self.ask(f"{t('Back to the menus?')} {self.back_consequence()} (y/n)", "n")
		return answer.strip().lower().startswith("y")

	def leave_exam(self):
		"""Leave the exam for the menus: kept as abandoned after a grademe, else forgotten."""
		if self.exam is None:
			return
		if self.store and self.attempts:
			self._forget("abandoned")
			return
		if self.store:
			self.store.clear()
		self._reset()

	def login(self):
		"""Fake login, like at the exam: any password, never checked or kept."""
		display.typewriter(self.console, "42pal · examshell", sleep=self.sleep)
		self.user = self.ask(t("login:"), getpass.getuser())
		# The password is read, then dropped at once: not checked, not stored.
		self.ask_password(t("password: "))
		display.typewriter(self.console, t("Welcome {user}!", user=self.user), sleep=self.sleep)
		self.console.print()

	def offer_update(self):
		"""Offer the newer 42pal found at launch; return True once pulled (to restart)."""
		update = self.update_check.result() if self.update_check else None
		if update is None:
			return False
		self.console.print(display.update_message(update))
		if self.ask(t("Update now?") + " (y/n)", "y").strip().lower().startswith("n"):
			self.console.print()
			return False
		ok, why = self.updater()
		if not ok:
			self.console.print(display.update_failed(why))
			self.console.print()
			return False
		self.console.print(t("42pal is updated: it starts again."))
		self.restart = True
		return True

	def resume(self):
		"""Offer to resume the saved exam; return True if it was resumed.

		Refusing keeps it in the history as "abandoned".
		"""
		if not self.restore_saved():
			return False
		question = display.resume_question(self.exam, self.level, self.variant, self._time_left())
		if self.ask(question, "y").strip().lower().startswith("n"):
			self.abandon_saved()
			return False
		self.show_subject()
		return True

	def restore_saved(self):
		"""Put back the saved exam, if there is one to resume; return True then.

		An exam whose time ran out while away goes to the history without a
		question; one whose subject is gone cannot be resumed. Both are said.
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
		if self._time_left() <= 0:
			self.console.print(display.time_ran_out_while_away(exam))
			self._forget("time")
			return False
		return True

	def abandon_saved(self):
		"""Give up the restored exam: kept in the history as "abandoned"."""
		self._forget("abandoned")

	def _restore(self, session, exam, variant):
		"""Put back the state of a saved exam."""
		self.exam, self.level, self.variant = exam, session.level, variant
		self.started_at = session.started_at
		self.mode = session.mode
		self.retry = exam.retry[RETRY_OF_MODE[session.mode]]
		self.attempts, self.oks, self.failures = session.attempts, session.oks, session.failures
		self.passed_levels = list(session.passed_levels)
		self.next_grademe_at = session.next_grademe_at
		self.warned = session.warned
		self.cheated = session.cheat

	def _forget(self, end):
		"""Keep the restored exam in the history as `end`, then start afresh."""
		elapsed = self.clock() - self.started_at
		if self.mode == "exam":
			elapsed = min(elapsed, self.exam.duration_minutes * 60)
		self.store.add_history(self._history_entry(end, elapsed))
		self.store.clear()
		self._reset()

	def choose_start(self):
		"""The menus before an exam: who, which exam, which mode, which level.

		The last choice of each menu goes back to the menu before it; in the
		first menu shown, it quits. A step that needs no menu (a single exam,
		the level in exam mode) is skipped again on the way back. Return
		(exam, mode, level), PRACTICE when practice is chosen in the first
		menu, or None to quit.
		"""
		steps = [
			lambda chosen, first: self.choose_audience(first),
			lambda chosen, first: self.choose_exam(chosen[0], first),
			lambda chosen, first: self.choose_mode(chosen[1], first),
			lambda chosen, first: self.choose_level(chosen[1], chosen[2], first),
		]
		chosen = []
		# For each answer in chosen: True if a menu was shown to get it.
		shown = []
		while len(chosen) < len(steps):
			menus_before = self.menus_shown
			answer = steps[len(chosen)](chosen, not any(shown))
			if answer is BACK:
				if not any(shown):
					return None
				# Undo the answers up to the last menu shown, that one included.
				while not shown.pop():
					chosen.pop()
				chosen.pop()
				continue
			if answer in SIDE_CHOICES:
				return answer
			chosen.append(answer)
			shown.append(self.menus_shown > menus_before)
		_, exam, mode, level = chosen
		return exam, mode, level

	def choose_audience(self, first=True):
		"""The first menu: "piscine" or "student" (their exams), or PRACTICE; or BACK.

		Asked only when there is more than one choice.
		"""
		by_audience = {}
		for exam in self._exams():
			by_audience.setdefault(exam.audience, []).append(exam)
		by_audience = {audience: by_audience[audience] for audience in AUDIENCES
			if audience in by_audience}
		choices = list(by_audience) + ([PRACTICE] if self._can_practise() else [])
		choices += [PROGRESS] if self.store and self.store.grades() else []
		choices.append(TESTERS)
		choices.append(SETTINGS)
		self._print_lines(display.audience_menu(by_audience, first, practice=PRACTICE in choices,
			progress=PROGRESS in choices, settings=True, language=i18n.languages()[i18n.language()],
			testers=True))
		last = len(choices) + 1
		number = self._ask_choice(t("Your choice:"), range(1, last + 1))
		self.console.print()
		return BACK if number == last else choices[number - 1]

	def choose_settings(self):
		"""Settings: the language of 42pal, each one under its own name; the choice is kept."""
		languages = i18n.languages()
		self._print_lines(display.language_menu(languages, i18n.language()))
		codes = list(languages)
		last = len(codes) + 1
		number = self._ask_choice(t("Language:"), range(1, last + 1))
		self.console.print()
		if number != last:
			settings.choose_language(codes[number - 1], self.settings_file)

	def _testers(self):
		"""The testers offered: all of them, even those this system cannot run (said when chosen)."""
		return list(self.tester_list or testers_core.TESTERS)

	def choose_tester(self):
		"""Testers: the testers of projects; the one chosen runs, then this menu again until Back."""
		while True:
			items = [(tester, tester.name, t(tester.summary) if testers_core.available(tester)
				else t("{summary} (Linux only)", summary=t(tester.summary)), "") for tester in self._testers()]
			tester = self._numbered_menu((t("Testers:"), items), first=False)
			if tester is BACK:
				return
			self.use_tester(tester)

	def use_tester(self, tester):
		"""Download the tester if needed, ask the folder, run it, show the results; again until Back."""
		if not testers_core.available(tester):
			self.console.print(t("{tester} runs on Linux only.", tester=tester.name), markup=False)
			self.console.print()
			return
		if not self._tester_ready(tester):
			return
		project = self._ask_project(tester)
		while project is not None:
			self._show_tester_report(tester, project)
			items = [("again", t("Run again"), t("same folder"), ""),
				("another", t("Another folder"), "", "")]
			if tester.visualizer:
				items.append(("visualize", t("Visualize"), t("the sort, operation by operation"), ""))
			choice = self._numbered_menu((t("What now?"), items), first=False)
			if choice is BACK:
				return
			if choice == "another":
				project = self._ask_project(tester)
			elif choice == "visualize":
				self._visualize(tester, project)

	def _visualize(self, tester, project):
		"""The visualizer of the tester on `project`, on this terminal, until it is left."""
		if testers_core.state(tester, self.testers_root) != testers_core.READY:
			self.console.print(t("Update {tester} to get its visualizer.", tester=tester.name), markup=False)
			return
		lang = testers_core.tester_language(tester, i18n.language())
		self.run_command(testers_core.visualizer_command(tester, project, lang, self.testers_root))
		self.console.print()

	def _tester_ready(self, tester):
		"""Download the tester, or its new version, when the student agrees; True when it can run."""
		state = testers_core.state(tester, self.testers_root)
		if state == testers_core.READY:
			return True
		if state == testers_core.MISSING:
			self.console.print(t("{tester} is not downloaded yet: it comes from {url}, version {tag}.",
				tester=tester.name, url=testers_core.source(tester, self.testers_environ), tag=tester.tag),
				markup=False)
			question = t("Download it now?")
		else:
			self.console.print(t("A new version of {tester} comes with this 42pal: {tag}.", tester=tester.name,
				tag=tester.tag), markup=False)
			question = t("Update it now?")
		if self.ask(question + " (y/n)", "y").strip().lower().startswith("n"):
			self.console.print()
			# Not updated: the version already there runs.
			return state == testers_core.OUTDATED
		with self._status(t("Downloading {tester}…", tester=tester.name)):
			ok, why = testers_core.install(tester, self.testers_root, self.testers_environ)
		if not ok:
			self.console.print(f"[red]{t('The download failed:')}[/] {escape(why)}")
			self.console.print()
			return state == testers_core.OUTDATED
		self.console.print(f"[green]{t('{tester} is ready ({tag}).', tester=escape(tester.name), tag=tester.tag)}[/]")
		return True

	def _ask_project(self, tester):
		"""The folder to test, in a small shell: the folders found by their number, cd, ls, test; None goes back.

		It starts in the folder tested last, else here when it is the project,
		else in the home folder. Enter alone tests the folder you are in when
		it is the project; a path tests that folder.
		"""
		last = testers_core.last_project(tester, self.settings_file)
		if last and Path(last).is_dir():
			here = Path(last)
		elif self._has_marker(tester, Path.cwd()):
			here = Path.cwd()
		else:
			here = Path.home()
		found = self._list_projects(tester, last)
		self.console.print(t("Type its number, or move with cd and ls, then test. back goes back, help for more."),
			markup=False)
		while True:
			with completing_paths(here):
				answer = self.ask(f"{display.short_path(here)} $", None).strip()
			command, _, argument = answer.partition(" ")
			argument = argument.strip()
			if not answer:
				if self._has_marker(tester, here):
					return here
				self.console.print(t("No {project} here: cd to yours, or type its number.", project=tester.project),
					markup=False)
			elif answer.isdigit():
				if 1 <= int(answer) <= len(found):
					return found[int(answer) - 1]
				self.console.print(t("No folder number {number}: cd to yours, then test.", number=answer)
					if not found else t("No folder number {number}: type a number from 1 to {count}.",
					number=answer, count=len(found)), markup=False)
			elif command in ("back", "b", "exit", "quit"):
				self.console.print()
				return None
			elif command == "ls":
				self._list_folders(tester, folder_from(argument, here) if argument else here)
			elif command == "cd":
				target = folder_from(argument or "~", here)
				if target.is_dir():
					here = target
				else:
					self.console.print(t("No folder here: {path}", path=display.short_path(target)), markup=False)
			elif command == "pwd":
				self.console.print(str(here), markup=False)
			elif command in ("test", "t"):
				target = folder_from(argument, here) if argument else here
				if target.is_dir():
					return target
				self.console.print(t("No folder here: {path}", path=display.short_path(target)), markup=False)
			elif command in ("help", "?"):
				self._print_lines([t("Commands:"),
					"  " + t("ls [folder]     the folders here (★: the {project})", project=tester.project),
					"  " + t("cd <folder>     go into a folder (cd .. goes up, cd alone goes home)"),
					"  " + t("test [folder]   test the folder you are in (Enter alone does it too)"),
					"  " + t("<number>        test a folder found"),
					"  " + t("back            back to the testers")])
			elif "/" in answer or answer.startswith(("~", ".")):
				target = folder_from(answer, here)
				if target.is_dir():
					return target
				self.console.print(t("No folder here: {path}", path=display.short_path(target)), markup=False)
			else:
				self.console.print(t("Unknown command: {command} (help lists them).", command=command),
					markup=False)

	def _has_marker(self, tester, folder):
		return testers_core.has_marker(tester, folder)

	def _list_projects(self, tester, last):
		"""The folders of the project, each one printed as soon as it is found; return them."""
		self.console.print(t("Where is your {project}?", project=tester.project), markup=False)
		found = []
		if last and Path(last).is_dir():
			found.append(Path(last))
			self.console.print(f"  1. {display.short_path(last)}   ({t('last tested')})", markup=False)
		for path in testers_core.iter_projects(tester, self.projects_root):
			if path in found:
				continue
			found.append(path)
			self.console.print(f"  {len(found)}. {display.short_path(path)}", markup=False)
		if not found:
			self.console.print("  " + t("None found in your home folder."), markup=False)
		return found

	def _list_folders(self, tester, folder):
		"""ls: the folders in `folder`, ★ for those of the project; said when `folder` is one."""
		try:
			names = sorted(name for name in os.listdir(folder) if not name.startswith(".")
				and (Path(folder) / name).is_dir())
		except OSError:
			self.console.print(t("No folder here: {path}", path=display.short_path(folder)), markup=False)
			return
		for name in names[:200]:
			star = "★ " if self._has_marker(tester, Path(folder) / name) else "  "
			self.console.print(f"  {star}{name}/", markup=False)
		if not names:
			self.console.print("  " + t("(no folder)"), markup=False)
		if self._has_marker(tester, folder):
			self.console.print(t("✓ a {project} here: test (or Enter) runs {tester} on it.", project=tester.project,
				tester=tester.name), markup=False)

	def _show_tester_report(self, tester, project):
		"""Run the tester on `project` and show what it found; the folder is kept for the next time."""
		lang = testers_core.tester_language(tester, i18n.language())
		with self._status(t("{tester} is testing {project}…", tester=tester.name,
				project=display.short_path(project))) as status:
			report = testers_core.run(tester, project, lang, self.testers_root,
				on_progress=lambda progress, item: status.update(display.tester_progress(tester, progress)))
		testers_core.remember_project(tester, project, self.settings_file)
		for line in display.tester_report(report, tester, project):
			self.console.print(line)
		self.console.print()

	def _can_practise(self):
		"""Practice is offered when the catalog has exercises."""
		return bool(self._catalog()[0].exercises)

	def show_progress(self):
		"""The progress: a summary, the exams, then the weak themes; return the one to practise, or None.

		None: Back, to the first menu.
		"""
		history, grades = self.store.history(), self.store.grades()
		self.console.print(display.progress_summary(summary(history, grades)))
		rows = exam_rows(history)
		if rows:
			self.console.print(display.exam_progress_table(rows))
		weak = weak_themes(grades)
		_, themes = self._catalog()
		items = [(row.theme, row.theme, display.theme_score(row), t(themes[row.theme].skill) if row.theme in themes else "")
			for row in weak if row.theme in themes]
		if not items:
			self.console.print(t("No weak theme: every theme you met passed its last grademe."))
			return None
		value = self._numbered_menu((t("Practise a weak theme:"), items), first=False)
		return None if value is BACK else value

	def practise(self, theme=None):
		"""Practice, chosen in the first menu: True once it is over, False after Back.

		The practice shell takes over with the same terminal and workspace;
		with a theme (from the progress), it starts on that theme at once.
		"""
		# Imported here: pal42.cli.practice imports this module.
		from pal42.cli.practice import PRACTICE_COMMANDS, PracticeShell
		catalog, themes = self._catalog()
		practice = PracticeShell(self.console, self.ask, self.workspace, rng=self.rng,
			catalog=catalog, themes=themes, sleep=self.sleep, store=self.store)
		complete_with(PRACTICE_COMMANDS)
		if practice.run(theme, first=False) is BACK:
			complete_with(COMMANDS)
			return False
		return True

	def choose_exam(self, audience, first=False):
		"""Show the exams of `audience` as a numbered menu; return the one picked, or BACK.

		A single exam is taken without asking, and said.
		"""
		exams = [exam for exam in self._exams() if exam.audience == audience]
		if len(exams) == 1:
			exam = exams[0]
			self.console.print(f"{t('Your exam:')} {exam.title} ({display.exam_summary(exam)})")
			self.console.print()
			return exam
		self._print_lines(display.exam_menu(exams, first))
		last = len(exams) + 1
		number = self._ask_choice(t("Exam:"), range(1, last + 1))
		self.console.print()
		return BACK if number == last else exams[number - 1]

	def choose_mode(self, exam, first=False):
		"""Ask the mode: "exam" (hard waits, the real duration) or "revision", or BACK."""
		self._print_lines(display.mode_menu(exam, first))
		# Enter alone takes revision.
		number = self._ask_choice(t("Mode:"), [1, 2, 3], "2")
		self.console.print()
		return {1: "exam", 2: "revision", 3: BACK}[number]

	def choose_level(self, exam, mode="revision", first=False):
		"""Ask the starting level in revision mode; return it, or BACK.

		Exam mode starts at the first level, like the real exam: no question.
		"""
		playable = exam.playable_levels
		if mode == "exam":
			self.console.print(t("Exam mode starts at level {level}, like the real exam.", level=playable[0]))
			return playable[0]
		self._print_lines(display.level_menu(exam, first))
		last = exam.level_count + 1
		# Enter alone takes the first playable level.
		level = self._ask_choice(t("Starting level:"), [*playable, last], str(playable[0]))
		if level == last:
			self.console.print()
			return BACK
		return level

	def _exams(self):
		"""The exams that can be played: those with exercises at one level at least."""
		catalog, themes = self._catalog()
		exams = [load_exam(exam_id, catalog=catalog, themes=themes) for exam_id in list_exams()]
		return [exam for exam in exams if exam.playable_levels]

	def _print_lines(self, lines):
		"""Print the lines of a menu as they are: no rich markup is read in them."""
		for line in lines:
			self.console.print(line, markup=False, highlight=False)

	def begin(self, exam, mode, level):
		"""Start an exam in `mode` ("exam" or "revision") at `level`, without menus."""
		self.mode = mode
		self.retry = exam.retry[RETRY_OF_MODE[mode]]
		self.start(exam, level)

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
		self.show_subject()
		self._save()

	def show_subject(self):
		"""Write the current subject in the workspace and show it."""
		exam, level = self.exam, self.level
		subject = self.workspace.give_subject(self.variant)
		rendu = self.workspace.rendu / self.variant.name
		# First the panel (where to read and hand in), then the subject as
		# plain text: markup=False so that rich changes nothing, and no frame,
		# so that the examples can be copied as they are.
		self.console.print()
		self.console.print(display.subject_panel(
			exam, level, self.variant, subject, rendu, self.mode,
		))
		self.console.print()
		# The words of the variant stand out; rich reads no markup in a Text.
		self.console.print(display.subject_text(self.variant, subject.read_text(encoding="utf-8")), end="")
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
			if self.handle(command):
				return

	def handle(self, command):
		"""Run one examshell command; return True when the exam is over.

		The time is checked first: a command typed too late is not run.
		"""
		command = SHORTCUTS.get(command.strip(), command.strip())
		left = self._time_left()
		if left <= 0:
			self.console.print(display.time_up())
			self.end_exam("time")
			return True
		if left < WARNING_SECONDS and not self.warned:
			self.warned = True
			self.console.print(display.almost_over(left))
		if command == "finish":
			self.end_exam()
			return True
		if command == "help":
			self.console.print(display.help_table(COMMANDS))
		elif command == "status":
			self.show_status()
		elif command == "grademe":
			if self.grademe():
				return True
		elif command == "report":
			self.write_report()
		elif command == "back":
			if self.confirm_back():
				self.back_requested = True
				return True
		elif command == "cheat":
			# Hidden: in no help nor completion, for the owner of 42pal only.
			if self.cheat():
				return True
		elif command:
			# escape: what the student typed must not be read as rich markup.
			self.console.print(t("Unknown command: {command}. Type help for the list.", command=escape(command)))
		# A blank line after each answer sets it apart from the next prompt;
		# Enter alone gave no answer, so it adds nothing.
		if command:
			self.console.print()
		self._save()
		return False

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
		result = self._grade_and_show(self.exam.compile_command)
		if not result.passed:
			self.failures += 1
			wait = self.retry.wait_after(self.failures)
			self.next_grademe_at = self.clock() + wait
			self.console.print(display.next_grademe(wait, self.retry.wait_after(self.failures + 1)))
			return False
		return self._level_passed()

	def _level_passed(self):
		"""The current level is passed: its points, then the next level or the end.

		Return True when the exam is over.
		"""
		# Passed: the next subject starts with no failure and no wait.
		self.failures = 0
		self.next_grademe_at = None
		self.oks += 1
		self.passed_levels.append(self.level)
		self.console.print(display.points_won(self.exam.points_per_level, self.grade))
		if self.grade >= 100:
			self.console.print(display.exam_passed_panel(self.exam))
			self.end_exam("passed")
			return True
		next_levels = [level for level in self.exam.playable_levels if level > self.level]
		if not next_levels:
			# The next levels have no exercise yet: the exam stops below 100.
			self.console.print(display.no_more_levels(self.grade))
			self.end_exam("no more levels")
			return True
		self.start(self.exam, next_levels[0])
		return False

	def _grade_and_show(self, compile_command):
		"""Grade the current subject's rendu, show the result; return the Grade.

		A spinner while grading, then OK or KO with the clickable log (written
		in traces/ at each grademe), then the trace of a failure.
		"""
		self.attempts += 1
		rendu = self.workspace.rendu / self.variant.name
		# The language of the subject: practice has no exam, only a subject.
		runner = runner_for(self.variant.exercise.language, compile_command)
		# A spinner while grading, with the number of the test being run.
		with self._status(t("Grading…")) as status:
			# step is "memory" when the tests run again under valgrind.
			def progress(number, total, step="output"):
				doing = t("Checking memory…") if step == "memory" else t("Grading…")
				status.update(f"{doing} {t('test {number}/{total}', number=number, total=total)}")
			started = self.clock()
			result = grade(self.variant, rendu, runner, progress)
			# A grading often takes a tenth of a second: the spinner stays a
			# moment, so that it can be seen. Only in a real terminal.
			left = ANIMATION_SECONDS - (self.clock() - started)
			if self.console.is_terminal and left > 0:
				self.sleep(left)
		log_text = result.trace or f"OK: {result.tests_passed}/{result.tests_total} tests passed\n"
		log = self.workspace.write_trace(self.attempts, self.variant.name, log_text)
		self.last_trace = log
		self._keep_grade(result.passed)
		self.console.print(display.grade_result(result, log))
		if not result.passed:
			self.console.print(display.trace_panel(result.trace))
		return result

	def _keep_grade(self, passed):
		"""Keep this grademe in grades.json, for the progress: the subject, its themes, OK or KO."""
		if not self.store:
			return
		exo = self.variant.exercise
		self.store.add_grade({
			"when": datetime.fromtimestamp(self.clock()).isoformat(timespec="seconds"),
			"variant": self.variant.id,
			"exercise": exo.name,
			"themes": list(exo.themes),
			"language": exo.language,
			"passed": passed,
			"source": self.exam.id if self.exam else "practice",
			**({"cheat": True} if self.cheated else {}),
		})

	def _status(self, text):
		"""The spinner shown while grading: rich shows it only in a real terminal.

		It returns a context manager whose update(text) changes the text; the
		full-screen interface puts its own instead.
		"""
		return self.console.status(text, spinner="dots")

	@property
	def grade(self):
		"""The grade out of 100: the points of each level passed, like 42_EXAM."""
		return self.exam.points_per_level * len(self.passed_levels)

	def end_exam(self, end="finish"):
		"""Show the summary of the exam, keep it in the history, say goodbye.

		end tells how it ended: "finish", "time" (time up) or "passed".
		"""
		elapsed = self.clock() - self.started_at
		self.console.print(display.summary_table(
			self.exam, self.passed_levels, self.attempts, self.oks, elapsed, self.grade,
		))
		if self.store:
			self.store.add_history(self._history_entry(end, elapsed))
			self.store.clear()
		self.console.print(t("End of the exam. See you soon!"))

	def _history_entry(self, end, elapsed):
		"""What the history keeps of a finished exam: the base of a future score."""
		return {
			"exam": self.exam.id,
			"title": self.exam.title,
			"ended_at": datetime.fromtimestamp(self.clock()).isoformat(timespec="seconds"),
			"levels_passed": self.passed_levels,
			"grade": self.grade,
			"attempts": self.attempts,
			"oks": self.oks,
			"seconds": round(elapsed),
			"mode": self.mode,
			"end": end,
			**({"cheat": True} if self.cheated else {}),
		}

	def _save(self):
		"""Save the exam in progress, to resume it if the terminal is closed."""
		if self.store and self.variant:
			self.store.save(Session(
				self.exam.id, self.level, self.variant.id, self.started_at,
				self.mode, self.attempts, self.oks, self.failures,
				self.passed_levels, self.next_grademe_at, self.warned, self.cheated,
			))

	def _catalog(self):
		"""Return the catalog and the themes, loading them the first time."""
		if self.catalog is None:
			self.themes = self.themes or load_themes()
			self.catalog = load_catalog(themes=self.themes)
		return self.catalog, self.themes or load_themes()

	def _time_left(self):
		"""Seconds left before the end of the exam (0 or less: over; revision: no end)."""
		if self.mode == "revision":
			return math.inf
		return self.exam.duration_minutes * 60 - (self.clock() - self.started_at)

	def show_status(self):
		"""Show the exam, the level, the subject, the times and the next grademe."""
		elapsed = self.clock() - self.started_at
		left = max(0, self._time_left())
		if_ko = self.retry.wait_after(self.failures + 1)
		self.console.print(display.status_table(
			self.exam, self.level, self.variant, elapsed, left, self._wait_left(), if_ko,
			f"{RETRY_OF_MODE[self.mode]} ({', '.join(map(display.points, self.retry.minutes))} min)",
			self.grade, self.mode,
		))

	def _wait_left(self):
		"""Seconds left before the next grademe is allowed (0: now)."""
		if self.next_grademe_at is None:
			return 0
		return max(0, self.next_grademe_at - self.clock())

	def write_report(self):
		"""Write a report for an issue in reports/: the system, the subject, the code, the last trace.

		Return its path (kept in last_report).
		"""
		variant = self.variant
		subject = self.workspace.subjects / variant.name / "subject.en.txt"
		files = {}
		for name in variant.expected_files:
			path = self.workspace.rendu / variant.name / name
			files[name] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
		trace = None
		if self.last_trace and self.last_trace.name.endswith(f"_{variant.name}.trace") and self.last_trace.is_file():
			trace = self.last_trace.read_text(encoding="utf-8", errors="replace")
		text = full_report(f"{variant.id} ({variant.name})",
			subject.read_text(encoding="utf-8") if subject.is_file() else "", files, trace,
			variant.exercise.language, store=self.store)
		stamp = datetime.fromtimestamp(self.clock()).strftime("%Y%m%d-%H%M%S")
		self.workspace.reports.mkdir(parents=True, exist_ok=True)
		self.last_report = self.workspace.reports / f"{stamp}_{variant.name}.md"
		self.last_report.write_text(text, encoding="utf-8")
		self.console.print(display.report_written(self.last_report))
		return self.last_report

	def cheat(self):
		"""The cheat menu: the passphrase, then the menus of the pack; True if the exam is over.

		Back in a menu goes to the menu before; in the first one, back to the
		exam. A choice that opens no menu goes back to the exam too.
		"""
		menu = cheat.unlock(self.ask_password("Passphrase: "), self.cheat_pack)
		if menu is None:
			self.console.print("Wrong passphrase.")
			return False
		current, before = menu.first_menu(self), []
		while True:
			value = self._numbered_menu(current, first=not before)
			if value is BACK:
				if not before:
					return False
				current = before.pop()
				continue
			step = menu.choose(self, value)
			if step.text:
				self.console.print(step.text)
			if step.over or not step.menu:
				return step.over
			before.append(current)
			current = step.menu

	def _numbered_menu(self, menu, first):
		"""Show a menu (of the cheat menu, of the progress) as a numbered list; return the value picked, or BACK."""
		title, items = menu
		width = max(len(label) for _, label, _, _ in items) + 3
		lines = [title, *(f"  {number}. {label:{width}}{summary}"
			for number, (_, label, summary, _) in enumerate(items, start=1))]
		last = len(items) + 1
		lines.append(f"  {last}. {t('Back to the exam') if first else t('Back (previous menu)')}")
		self._print_lines(lines)
		number = self._ask_choice(t("Your choice:"), range(1, last + 1))
		self.console.print()
		return BACK if number == last else items[number - 1][0]

	def _ask_choice(self, prompt, allowed, default=None):
		"""Ask until the answer is one of the numbers of `allowed`; return it."""
		self.menus_shown += 1
		allowed = list(allowed)
		while True:
			answer = self.ask(prompt, default)
			if answer.isdigit() and int(answer) in allowed:
				return int(answer)
			choices = ", ".join(map(str, allowed))
			self.console.print(t("Invalid choice: type one of these numbers: {choices}.", choices=choices))

def folder_from(text, here):
	"""The folder `text` names, from the folder `here` (~ is the home folder)."""
	path = Path(text).expanduser()
	return (path if path.is_absolute() else Path(here) / path).resolve()

def folder_matches(text, base=None):
	"""The folders whose path starts with `text`, each ending with /, as typed (~ stays ~).

	A relative path is read from `base` (the folder of the process when
	None). Hidden folders only when their dot is typed.
	"""
	if not text:
		return []
	parent, start = os.path.split(text)
	listed = os.path.join(base or ".", os.path.expanduser(parent or "."))
	try:
		names = sorted(os.listdir(listed))
	except OSError:
		return []
	return [text + name[len(start):] + "/" for name in names
		if name.startswith(start) and (start.startswith(".") or not name.startswith("."))
		and os.path.isdir(os.path.join(listed, name))]

def complete_path(text, state, base=None):
	"""readline's completer for a folder."""
	matches = folder_matches(text, base)
	return matches[state] if state < len(matches) else None

def suggest_folder(text):
	"""The first folder whose path starts with `text`, or None: the completion of the full screen."""
	matches = folder_matches(text)
	return matches[0] if matches else None

class completing_paths:
	"""While a folder is asked, Tab completes paths from `base` (a / does not cut the word); then the commands again."""

	def __init__(self, base=None):
		self.base = base

	def __enter__(self):
		self.readline = sys.modules.get("readline")
		if self.readline is not None:
			self.completer = self.readline.get_completer()
			self.delims = self.readline.get_completer_delims()
			self.readline.set_completer(lambda text, state: complete_path(text, state, self.base))
			self.readline.set_completer_delims(" \t\n")
		return self

	def __exit__(self, *error):
		if self.readline is not None:
			self.readline.set_completer(self.completer)
			self.readline.set_completer_delims(self.delims)

def complete_with(commands):
	"""Tab completes `commands` from now on, if readline is in use."""
	readline = sys.modules.get("readline")
	if readline is not None:
		readline.set_completer(make_completer(commands))

def terminal(commands):
	"""Prepare the real keyboard and terminal; return (console, ask, ask_password).

	readline gives input() the arrow keys (history, editing) and Tab to
	complete the `commands`.
	"""
	try:
		import readline
		readline.set_completer(make_completer(commands))
		# macOS ships libedit instead of GNU readline: another syntax.
		if "libedit" in (readline.__doc__ or ""):
			readline.parse_and_bind("bind ^I rl_complete")
		else:
			readline.parse_and_bind("tab: complete")
	except ImportError:
		pass

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

	return Console(), ask, ask_password

def main(full_screen=False, update_check=None):
	"""Start the examshell on the real keyboard and terminal; return the exit code.

	full_screen: the full-screen interface (pal42.cli.tui) instead of the text
	one. update_check: the check for a newer 42pal started at launch, if any.
	"""
	# rendu/ is a git repository that pushes to a bare one in ~/.42pal.
	workspace = Workspace(remote=STATE_DIR / "rendu.git")
	if full_screen:
		from pal42.cli.tui import run_exam
		return run_exam(workspace, SessionStore(), update_check)
	console, ask, ask_password = terminal(COMMANDS)
	try:
		shell = Shell(console, ask, ask_password, workspace=workspace, store=SessionStore())
		shell.update_check = update_check
		shell.run()
		if shell.restart:
			restart()
	except KeyboardInterrupt:
		console.print("\n" + t("Exam stopped (Ctrl-C): run ./42pal again to resume it."))
		return 130
	return 0

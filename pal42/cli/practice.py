"""./42pal practice: subjects of one theme, one after the other.

No login, no exam timer, no wait between two grademe: a passed grademe
gives the next subject of the theme, and next skips to another one.
"""

import random
import time

from rich.markup import escape

from pal42.cli import display
from pal42.cli.shell import STATE_DIR, Shell, terminal
from pal42.cli.workspace import Workspace
from pal42.practice import draw_practice
from pal42.runners.c import DEFAULT_COMMAND

# The practice commands and what they do, shown by help.
PRACTICE_COMMANDS = {
	"grademe": "grade your work",
	"next": "another subject of the same theme",
	"finish": "stop practising",
	"help": "show this help",
}

# One letter (then Enter) for each command: g, n, f and ?.
PRACTICE_SHORTCUTS = {"g": "grademe", "n": "next", "f": "finish", "?": "help"}

class PracticeShell(Shell):
	"""Practising one theme: the grading and display of the examshell, no exam."""

	def __init__(self, console, ask, workspace=None, rng=None, catalog=None, themes=None,
			sleep=time.sleep, language="c"):
		super().__init__(console, ask, None, workspace, rng or random.Random(),
			sleep=sleep, catalog=catalog, themes=themes)
		self.language = language
		self.theme = None
		# The subjects given so far (exo#seed), and how many were passed.
		self.seen = set()
		self.passed = 0

	def run(self, theme=None):
		"""Practise `theme` (asked if None); return the exit code.

		1 when the theme has no exercise (unknown, or none written yet).
		"""
		choices = self.practisable_themes()
		try:
			if theme is None:
				theme = self.choose_theme(choices)
				if theme is None:
					self.console.print("Goodbye!")
					return 0
			elif theme not in choices:
				self.console.print(
					f"No exercise to practise '{escape(theme)}' yet. Themes: {', '.join(choices)}"
				)
				return 1
			self.theme = theme
			self.next_subject()
		except EOFError:
			return 0
		self.command_loop()
		return 0

	def practisable_themes(self):
		"""The ids of the themes that have at least one exercise, sorted."""
		catalog, themes = self._catalog()
		return sorted(theme for theme in themes if catalog.find(self.language, theme))

	def choose_theme(self, choices):
		"""Show the themes as a numbered menu, with their skill; return the one picked.

		The last choice quits: None is returned.
		"""
		_, themes = self._catalog()
		self.console.print("Choose a theme to practise:")
		for number, theme in enumerate(choices, start=1):
			self.console.print(f"  {number}. {theme} · {escape(themes[theme].skill)}")
		last = len(choices) + 1
		self.console.print(display.last_choice(last, first=True), markup=False)
		number = self._ask_choice("Your choice:", range(1, last + 1))
		return None if number == last else choices[number - 1]

	def next_subject(self):
		"""Give a new subject of the theme, one not given before."""
		catalog, themes = self._catalog()
		self.variant = draw_practice(catalog.find(self.language, self.theme), self.rng, self.seen)
		self.seen.add(self.variant.id)
		subject = self.workspace.give_subject(self.variant)
		rendu = self.workspace.rendu / self.variant.name
		self.console.print()
		self.console.print(display.practice_panel(
			themes[self.theme], self.variant, subject, rendu,
		))
		self.console.print()
		self.console.print(subject.read_text(encoding="utf-8"), markup=False, highlight=False, end="")
		self.console.print()

	def command_loop(self):
		"""Read and run the practice commands until finish or Ctrl-D."""
		while True:
			try:
				command = self.ask("practice>").strip()
			except EOFError:
				command = "finish"
			if self.handle(command):
				return

	def handle(self, command):
		"""Run one practice command; return True when the practice is over."""
		command = PRACTICE_SHORTCUTS.get(command.strip(), command.strip())
		if command == "finish":
			self.console.print(
				f"Practice summary: {self.passed} subject{'s' if self.passed != 1 else ''}"
				f" passed, {self.attempts} grademe"
			)
			return True
		if command == "help":
			self.console.print(display.help_table(PRACTICE_COMMANDS))
		elif command == "next":
			self.next_subject()
		elif command == "grademe":
			if self._grade_and_show(DEFAULT_COMMAND).passed:
				self.passed += 1
				self.next_subject()
		elif command:
			self.console.print(f"Unknown command: {escape(command)}. Type help for the list.")
		if command:
			self.console.print()
		return False

def main(theme=None):
	"""Practise on the real keyboard and terminal; return the exit code."""
	console, ask, _ = terminal(PRACTICE_COMMANDS)
	try:
		workspace = Workspace(remote=STATE_DIR / "rendu.git")
		return PracticeShell(console, ask, workspace).run(theme)
	except KeyboardInterrupt:
		console.print("\nPractice stopped (Ctrl-C).")
		return 130

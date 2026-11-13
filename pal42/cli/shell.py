"""The examshell: fake login, choice of the exam and level, then commands.

Its input and output are given to it (ask, ask_password, console), so the
tests can drive it with answers written in advance; main() gives it the real
keyboard and terminal.
"""

import getpass
import random
import sys
import time

from rich.console import Console
from rich.markup import escape

from pal42.catalog import load_catalog
from pal42.cli import display
from pal42.cli.workspace import Workspace
from pal42.exam import list_exams, load_exam
from pal42.themes import load_themes

# The examshell commands and what they do, shown by help.
COMMANDS = {
	"status": "où tu en es : exam, niveau, sujet, temps",
	"grademe": "fait corriger ton rendu",
	"finish": "termine l'exam",
	"help": "affiche cette aide",
}

class Shell:
	"""One exam session in the terminal.

	ask(prompt, default) returns what the student types, ask_password(prompt)
	reads without showing it, and console is a rich Console.
	"""

	def __init__(self, console, ask, ask_password, workspace=None, rng=None, clock=time.monotonic):
		self.console = console
		self.ask = ask
		self.ask_password = ask_password
		self.workspace = workspace or Workspace()
		self.rng = rng or random.Random()
		self.clock = clock
		self.user = None
		# Set by start(): the exam, the level, the subject and when it began.
		self.exam = None
		self.level = None
		self.variant = None
		self.started_at = None

	def run(self):
		"""The whole session: login, exam, level, subject, then the commands."""
		try:
			self.login()
			exam = self.choose_exam()
			self.start(exam, self.choose_level(exam))
		# Ctrl-D before the exam has started: just leave.
		except EOFError:
			self.console.print("\nAu revoir !")
			return
		self.command_loop()

	def login(self):
		"""Fake login, like at the exam: any password, never checked or kept."""
		self.user = self.ask("login:", getpass.getuser())
		# The password is read, then dropped at once: not checked, not stored.
		self.ask_password("password: ")
		self.console.print(f"Bienvenue {self.user} !")

	def choose_exam(self):
		"""Show the exams as a numbered menu and return the one picked."""
		# Themes and catalog are loaded once, for all the exams of the menu.
		themes = load_themes()
		catalog = load_catalog(themes=themes)
		exams = [load_exam(exam_id, catalog=catalog, themes=themes) for exam_id in list_exams()]
		self.console.print("Choisis ton exam :")
		for number, exam in enumerate(exams, start=1):
			self.console.print(f"  {number}. {exam.title}")
		number = self._ask_choice("Ton choix :", range(1, len(exams) + 1))
		return exams[number - 1]

	def choose_level(self, exam):
		"""Ask the starting level, among the levels that have exercises."""
		playable = exam.playable_levels
		self.console.print(f"Niveaux jouables : {', '.join(map(str, playable))}")
		# Enter alone takes the first playable level.
		return self._ask_choice("Niveau de départ :", playable, str(playable[0]))

	def start(self, exam, level):
		"""Draw a subject at `level`, write it in the workspace and show it."""
		self.exam = exam
		self.level = level
		self.variant = exam.draw(level, self.rng)
		subject = self.workspace.give_subject(self.variant)
		self.started_at = self.clock()
		rendu = self.workspace.rendu / self.variant.name
		self.console.print(display.subject_panel(exam, level, self.variant, subject, rendu))

	def command_loop(self):
		"""Read and run the examshell commands until finish or Ctrl-D."""
		while True:
			try:
				command = self.ask("examshell>").strip()
			# Ctrl-D: the same as finish.
			except EOFError:
				command = "finish"
			if command == "finish":
				self.console.print("Fin de l'exam. À bientôt !")
				return
			if command == "help":
				self.console.print(display.help_table(COMMANDS))
			elif command == "status":
				self.show_status()
			elif command == "grademe":
				self.console.print(
					"Le correcteur n'est pas encore branché : il arrive avec les étapes 9 à 15."
				)
			elif command:
				# escape: what the student typed must not be read as rich markup.
				self.console.print(f"Commande inconnue : {escape(command)}. Tape help pour la liste.")

	def show_status(self):
		"""Show the exam, the level, the subject, the time spent and left."""
		elapsed = self.clock() - self.started_at
		left = max(0, self.exam.duration_minutes * 60 - elapsed)
		self.console.print(display.status_table(self.exam, self.level, self.variant, elapsed, left))

	def _ask_choice(self, prompt, allowed, default=None):
		"""Ask until the answer is one of the numbers of `allowed`; return it."""
		allowed = list(allowed)
		while True:
			answer = self.ask(prompt, default)
			if answer.isdigit() and int(answer) in allowed:
				return int(answer)
			choices = ", ".join(map(str, allowed))
			self.console.print(f"Choix invalide : tape un de ces nombres : {choices}.")

def main():
	"""Start the examshell on the real keyboard and terminal; return the exit code."""
	# Once imported, readline gives input() the arrow keys: history and editing.
	try:
		import readline  # noqa: F401
	except ImportError:
		pass
	console = Console()

	def ask(prompt, default=None):
		"""Read a line; Enter alone gives `default`, shown in brackets."""
		shown = f"{prompt} [{default}] " if default else f"{prompt} "
		answer = console.input(escape(shown)).strip()
		return answer if answer or default is None else default

	def ask_password(prompt):
		"""Read without showing what is typed, when the input is a terminal."""
		if sys.stdin.isatty():
			return getpass.getpass(prompt)
		# Answers sent through a pipe: getpass would wait on the keyboard.
		return input(prompt)

	try:
		Shell(console, ask, ask_password).run()
	except KeyboardInterrupt:
		console.print("\nExam interrompu (Ctrl-C).")
		return 130
	return 0

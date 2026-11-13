"""How the examshell looks: the rich panels and tables it prints.

Each function returns something rich can print; the shell prints it.
"""

from datetime import timedelta
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

def short_path(path):
	"""Write `path` with ~ for the home folder, like a shell does."""
	path = Path(path)
	home = Path.home()
	if path == home or home in path.parents:
		return "~/" + path.relative_to(home).as_posix()
	return path.as_posix()

def subject_panel(exam, level, variant, subject, rendu):
	"""The panel shown when a subject is given."""
	# escape: a [ in a path would otherwise be read as rich markup.
	lines = [
		f"[bold]{escape(exam.title)}[/] · niveau {level} · {exam.duration_minutes} min",
		"",
		f"Sujet  : [bold cyan]{escape(variant.name)}[/]",
		f"Lis-le : {escape(short_path(subject))}",
		f"Rends  : {escape(short_path(rendu))}/",
	]
	return Panel("\n".join(lines), title="42pal", expand=False)

def duration(seconds):
	"""Write a number of seconds as H:MM:SS, like 0:10:00."""
	return str(timedelta(seconds=int(seconds)))

def help_table(commands):
	"""The table of the examshell commands, from {command: what it does}."""
	table = Table(title="Commandes", show_header=False, box=None)
	for command, meaning in commands.items():
		table.add_row(f"[bold]{command}[/]", meaning)
	return table

def status_table(exam, level, variant, elapsed, left):
	"""Where the student is: exam, level, subject, time spent and left."""
	table = Table(show_header=False, box=None)
	table.add_row("Exam", escape(exam.title))
	table.add_row("Niveau", f"{level} sur {exam.level_count}")
	table.add_row("Sujet", f"[bold cyan]{escape(variant.name)}[/]")
	table.add_row("Temps passé", duration(elapsed))
	table.add_row("Temps restant", duration(left))
	return table

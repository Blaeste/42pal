"""How the examshell looks: the rich panels and tables it prints.

Each function returns something rich can print; the shell prints it.
"""

import time
from datetime import timedelta
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
	# 80 wide, like the subject printed under it (narrower if the terminal is).
	return Panel("\n".join(lines), title="42pal", width=80)

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

def typewriter(console, text, sleep=time.sleep, delay=0.02):
	"""Print `text` one letter at a time, as if someone were typing it.

	Only in a real terminal: in a pipe or a test, it is printed at once.
	sleep is given by the tests, so that they do not wait.
	"""
	if not console.is_terminal:
		console.print(text, markup=False, highlight=False)
		return
	for char in text:
		console.print(char, end="", markup=False, highlight=False)
		# Without flush, the terminal would show the line only once complete.
		console.file.flush()
		sleep(delay)
	console.print()

# A trace longer than this is cut on screen; the whole of it is in its file.
TRACE_LINES_SHOWN = 25

def grade_result(grade, log):
	"""The result of a grademe: OK or KO, the tests passed, the clickable log."""
	if grade.passed:
		verdict = f"[bold green]✓ OK[/]  {grade.tests_passed}/{grade.tests_total} tests"
	else:
		verdict = f"[bold red]✗ KO[/]  {grade.tests_passed}/{grade.tests_total} tests réussis"
	# [link=...]: the terminal opens the file when the path is clicked.
	link = f"[link={log.resolve().as_uri()}]{escape(short_path(log))}[/link]"
	return f"{verdict}\nTrace : {link}"

def trace_panel(trace):
	"""The trace in a red frame, cut after TRACE_LINES_SHOWN lines."""
	lines = trace.rstrip("\n").splitlines()
	shown = "\n".join(lines[:TRACE_LINES_SHOWN])
	# Text: the trace is shown as it is, with no rich markup read in it.
	text = Text(shown)
	if len(lines) > TRACE_LINES_SHOWN:
		more = len(lines) - TRACE_LINES_SHOWN
		text.append(f"\n… {more} lignes de plus : voir le fichier de trace", style="dim")
	# 84 wide: the 80 columns of a trace line, plus the frame and its margins.
	return Panel(text, title="trace", border_style="red", width=84)

def exam_passed_panel(exam):
	"""The panel shown when the last playable level is passed."""
	return Panel(
		f"[bold green]Bravo ! Exam réussi[/] : tous les niveaux jouables de "
		f"{escape(exam.title)} sont validés.",
		border_style="green", width=80,
	)

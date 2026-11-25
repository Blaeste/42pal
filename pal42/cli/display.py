"""How the examshell looks: the rich panels and tables it prints.

Each function returns something rich can print; the shell prints it.
"""

import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pal42 import subject as subject_module
from pal42.i18n import N_, t

def short_path(path):
	"""Write `path` with ~ for the home folder, like a shell does."""
	path = Path(path)
	home = Path.home()
	if path == home:
		return "~"
	if home in path.parents:
		return "~/" + path.relative_to(home).as_posix()
	return path.as_posix()

def path_link(path, end=""):
	"""A path the terminal opens when it is clicked: [link=file://...]~/path[/link]."""
	return f"[link={Path(path).resolve().as_uri()}]{escape(short_path(path))}{end}[/link]"

# How the words of a variant stand out in its subject, on the screen.
VARIANT_STYLE = "bold #c4b5fd"

def subject_text(variant, text):
	"""The subject as a rich Text, the texts of the params of `variant` in VARIANT_STYLE.

	What changes from a variant to another stands out; the file of the
	subject stays plain text. Only the statement is looked at (between the
	line of dashes and the examples); a text cut by the wrapping is found
	all the same.
	"""
	styled = Text(text)
	start = max(0, text.find("-" * 80))
	end = text.find("\n" + subject_module.examples_label())
	end = len(text) if end < 0 else end
	for param in variant.exercise.params:
		# The words as the subject in the language in use writes them.
		words = subject_module.param_text(variant, param).split()
		if not words:
			continue
		pattern = r"\s+".join(map(re.escape, words))
		# A short text, like 5, only as a whole word.
		if words[0][0].isalnum():
			pattern = r"\b" + pattern
		if words[-1][-1].isalnum():
			pattern += r"\b"
		for match in re.compile(pattern).finditer(text, start, end):
			styled.stylize(VARIANT_STYLE, match.start(), match.end())
	return styled

def subject_panel(exam, level, variant, subject, rendu, mode="exam"):
	"""The panel shown when a subject is given; mode is "exam" or "revision"."""
	if mode == "revision":
		how = t("revision mode · soft waits · no time limit")
	else:
		how = t("exam mode · hard waits · {minutes} min", minutes=exam.duration_minutes)
	# escape: a [ in a path would otherwise be read as rich markup.
	lines = [
		f"[bold]{escape(exam.title)}[/] · {t('level {level}', level=level)} · {how}",
		t("This level is worth {points} points.", points=points(exam.points_per_level)),
		"",
		f"{t('Subject:')} [bold cyan]{escape(variant.name)}[/]",
		f"{t('Read it:')} {path_link(subject)}",
		f"{t('Hand in:')} {path_link(rendu, '/')}",
	]
	# 80 wide, like the subject printed under it (narrower if the terminal is).
	return Panel("\n".join(lines), title="42pal", width=80)

def duration(seconds):
	"""Write a number of seconds as H:MM:SS, like 0:10:00."""
	return str(timedelta(seconds=int(seconds)))

def report_written(path):
	"""Said after the report command: where the report is, and what to do with it."""
	return (f"{t('Report written:')} {path_link(path)}\n"
		+ t("Attach it to an issue on GitHub (Issues, then New issue), or paste it there."
		" It holds your code: share it only if you want to."))

def help_table(commands):
	"""The table of the examshell commands, from {command: what it does}."""
	table = Table(title=t("Commands"), show_header=False, box=None,
		caption=t("Something wrong? Run ./42pal --report and open an issue on GitHub."))
	for command, meaning in commands.items():
		table.add_row(f"[bold]{command}[/]", t(meaning))
	return table

def status_table(exam, level, variant, elapsed, left, wait=0, if_ko=0, retry="", grade=0,
		mode="exam"):
	"""Where the student is: exam, level, subject, times, and the next grademe.

	wait is the time left before grademe is allowed again; if_ko the wait
	that a failed grademe would bring; retry describes the retry timer.
	"""
	table = Table(show_header=False, box=None)
	table.add_row(t("Exam"), escape(exam.title))
	table.add_row(t("Mode"), t(MODE_NAMES.get(mode, mode)))
	table.add_row(t("Level"), t("{level} of {count}", level=level, count=exam.level_count))
	table.add_row(t("Subject"), f"[bold cyan]{escape(variant.name)}[/]")
	table.add_row(t("Grade"), f"{points(grade)}/100")
	table.add_row(t("Time spent"), duration(elapsed))
	table.add_row(t("Time left"), t("no limit") if left == float("inf") else duration(left))
	table.add_row(t("Next grademe"), t("in {duration}", duration=duration(wait)) if wait else t("now"))
	table.add_row(t("If KO"), duration(if_ko) if if_ko else t("no wait"))
	if retry:
		table.add_row(t("Retry timer"), retry)
	return table

def retry_preview(wait):
	"""Said before grading: the wait a KO would bring."""
	when = t("in {duration}", duration=duration(wait)) if wait else t("right away")
	return f"[dim]{t('If KO: next grademe {when}', when=when)}[/]"

def next_grademe(wait, next_wait):
	"""Said after a KO: when grademe is allowed again, and what the next KO costs."""
	if wait:
		at = (datetime.now() + timedelta(seconds=wait)).strftime("%H:%M")
		when = t("in {duration} (at {at})", duration=duration(wait), at=at)
	else:
		when = t("now (the first retry is free)")
	again = duration(next_wait) if next_wait else t("no wait")
	return f"[yellow]{t('Next grademe {when}', when=when)}[/] · {t('if KO again: {wait}', wait=again)}"

def wait_message(wait):
	"""Said when grademe comes before the end of the wait."""
	return f"[yellow]{t('Wait {duration} before your next grademe.', duration=duration(wait))}[/]"

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
	tests = f"{grade.tests_passed}/{grade.tests_total}"
	if grade.passed:
		verdict = f"[bold green]✓ OK[/]  {t('{tests} tests', tests=tests)}"
	else:
		verdict = f"[bold red]✗ KO[/]  {t('{tests} tests passed', tests=tests)}"
	# [link=...]: the terminal opens the file when the path is clicked.
	link = path_link(log)
	warnings = "".join(f"\n[yellow]! {escape(t(warning))}[/]" for warning in grade.warnings)
	return f"{verdict}\n{t('Trace:')} {link}{warnings}"

def trace_panel(trace):
	"""The trace in a red frame, cut after TRACE_LINES_SHOWN lines."""
	lines = trace.rstrip("\n").splitlines()
	shown = "\n".join(lines[:TRACE_LINES_SHOWN])
	# Text: the trace is shown as it is, with no rich markup read in it.
	text = Text(shown)
	if len(lines) > TRACE_LINES_SHOWN:
		more = len(lines) - TRACE_LINES_SHOWN
		text.append("\n… " + t("{count} more lines: see the trace file", count=more), style="dim")
	# 84 wide: the 80 columns of a trace line, plus the frame and its margins.
	return Panel(text, title="trace", border_style="red", width=84)

def exam_passed_panel(exam):
	"""The panel shown when the last playable level is passed."""
	return Panel(
		f"[bold green]{t('Well done! Exam passed')}[/]: "
		+ t("{exam}, grade 100/100.", exam=escape(exam.title)),
		border_style="green", width=80,
	)

def time_up():
	"""Said when a command comes after the end of the exam."""
	return f"[bold red]{t('Time is up!')}[/] {t('The exam is over: no more grademe.')}"

def almost_over(left):
	"""Said once, when less than 10 minutes are left."""
	return f"[bold yellow]{t('Less than 10 minutes left')}[/] ({duration(left)})."

def summary_table(exam, passed_levels, attempts, oks, elapsed, grade=0):
	"""The summary at the end of the exam: grade, levels passed, grademe, time spent."""
	table = Table(title=f"{t('Summary')} · {escape(exam.title)}", show_header=False, box=None)
	levels = ", ".join(map(str, passed_levels)) or t("none")
	table.add_row(t("Grade"), f"{points(grade)}/100")
	table.add_row(t("Levels passed"), f"{len(passed_levels)} ({levels})")
	table.add_row(t("Grademe"), f"{attempts} ({oks} OK, {attempts - oks} KO)")
	table.add_row(t("Time spent"), duration(elapsed))
	return table

def resume_question(exam, level, variant, left):
	"""The question asked when a saved exam can be resumed."""
	time = t("no time limit") if left == float("inf") else t("{duration} left", duration=duration(left))
	# (y/n) stays: the answer is read by its first letter.
	return f"{t('Resume your exam?')} {exam.title} · {t('level {level}', level=level)} · {variant.name} · {time} (y/n)"

def time_ran_out_while_away(exam):
	"""Said when the saved exam ended while the terminal was closed."""
	return ("[yellow]" + t("Your last exam ({exam}) time ran out while you were away: it is kept in your history.",
		exam=escape(exam.title)) + "[/]")

def cannot_resume(variant_id):
	"""Said when the subject of the saved exam no longer exists."""
	return ("[yellow]" + t("Your last exam cannot be resumed: its subject {subject} is gone.",
		subject=escape(variant_id)) + "[/]")

def practice_panel(theme, variant, subject, rendu):
	"""The panel shown when a practice subject is given."""
	lines = [
		f"[bold]{t('Practice')} · {escape(theme.id)}[/] · {escape(t(theme.skill))}",
		t("No timer, no wait: grademe, next, finish"),
		"",
		f"{t('Subject:')} [bold cyan]{escape(variant.name)}[/]",
		f"{t('Read it:')} {path_link(subject)}",
		f"{t('Hand in:')} {path_link(rendu, '/')}",
	]
	return Panel("\n".join(lines), title="42pal", width=80)

def update_message(update):
	"""Said when a newer 42pal is found: how many commits, and the last ones."""
	text = (t("A new version of 42pal is available: {count} new commits.", count=update.count) if update.count != 1
		else t("A new version of 42pal is available: 1 new commit."))
	lines = [f"[bold #a5b4fc]{text}[/]"]
	lines += [f"  · {escape(change)}" for change in update.changes]
	return "\n".join(lines)

def update_failed(why):
	"""Said when git pull refused: nothing was changed."""
	return (f"[yellow]{t('The update failed: {why}', why=escape(why))}[/] "
		+ t("Nothing was changed; 42pal goes on."))

def points(value):
	"""Write points with 2 decimals at most and no useless zero: 25, 12.5, 16.67."""
	return f"{round(value, 2):g}"

# The menus before the exam. Their lines stay under 80 characters.

# How the first menu names each audience (see AUDIENCES in pal42/exam.py).
AUDIENCE_TEXTS = {"piscine": N_("Piscine (piscineux)"), "student": N_("Student (cursus)")}

# The names of the two modes, in the status.
MODE_NAMES = {"exam": N_("exam"), "revision": N_("revision")}

def exam_length(minutes):
	"""Write a duration for a menu: 3 h, 4 h 30, or 45 min."""
	hours, rest = divmod(minutes, 60)
	if not hours:
		return t("{minutes} min", minutes=rest)
	return t("{hours} h {minutes:02d}", hours=hours, minutes=rest) if rest else t("{hours} h", hours=hours)

# How a menu names the language of an exam.
LANGUAGE_NAMES = {"c": "C", "cpp": "C++", "python": "Python"}

def exam_summary(exam):
	"""The size and language of an exam, for a menu: 8 levels, 4 h, C."""
	return (t("{count} levels", count=exam.level_count) + f", {exam_length(exam.duration_minutes)}, "
		f"{LANGUAGE_NAMES.get(exam.language, exam.language)}")

def exam_tools(exam):
	"""How the rendus of an exam are built: compiled in C, run in Python."""
	command = " ".join(exam.compile_command)
	if exam.language == "python":
		return t("Run with {command}.", command=command)
	return t("Compiled with {command}.", command=command)

def last_choice(number, first):
	"""The last choice of a menu: back to the menu before, or quit in the first one."""
	return f"  {number}. {t('Quit') if first else t('Back (previous menu)')}"

# Said at the bottom of each launcher, and at the end of the results of a tester.
DISCLAIMER = N_("A helper tool, not an oracle: it does not cover every test of the evaluation. Test your project yourself too.")

# The first menu: its title, and the choice that leads to practice.
# N_: marked to be translated where they are shown, with t() (the language
# can change after these lines run).
FIRST_MENU_TITLE = N_("What do you want to do?")
PRACTICE_TEXT = N_("Practice")
PRACTICE_SUMMARY = N_("one theme, no timer")

# The choice of the first menu that shows the progress.
PROGRESS_TEXT = N_("Progress")
PROGRESS_SUMMARY = N_("your exams and weak themes")

# The choice of the first menu for the testers of projects (libfterator...).
TESTERS_TEXT = N_("Testers")
TESTERS_SUMMARY = N_("test your projects")

# The choice of the first menu for the settings: the language, for now.
SETTINGS_TEXT = N_("Settings")

def audience_menu(exams_by_audience, first=True, practice=False, progress=False, settings=False, language="",
		testers=False):
	"""The first menu: the exams of the piscine or of the students, then practice, progress, testers, settings."""
	lines = [t(FIRST_MENU_TITLE)]
	for number, (audience, exams) in enumerate(exams_by_audience.items(), start=1):
		leads_to = exams[0].title if len(exams) == 1 else t("{count} exams", count=len(exams))
		lines.append(f"  {number}. {t(AUDIENCE_TEXTS[audience]):22}{leads_to}")
	count = len(exams_by_audience)
	if practice:
		count += 1
		lines.append(f"  {count}. {t(PRACTICE_TEXT):22}{t(PRACTICE_SUMMARY)}")
	if progress:
		count += 1
		lines.append(f"  {count}. {t(PROGRESS_TEXT):22}{t(PROGRESS_SUMMARY)}")
	if testers:
		count += 1
		lines.append(f"  {count}. {t(TESTERS_TEXT):22}{t(TESTERS_SUMMARY)}")
	if settings:
		count += 1
		lines.append(f"  {count}. {t(SETTINGS_TEXT):22}{settings_summary(language)}")
	return lines + [last_choice(count + 1, first)]

def settings_summary(language):
	"""The grey line of Settings: the language in use."""
	return t("language: {language}", language=language)

def language_menu(languages, current):
	"""The menu of the languages: each one under its own name, the one in use said."""
	lines = [t("Language:")]
	in_use = "  (" + t("in use") + ")"
	for number, (code, name) in enumerate(languages.items(), start=1):
		lines.append(f"  {number}. {name}{in_use if code == current else ''}")
	return lines + [last_choice(len(languages) + 1, first=False)]

def progress_summary(text):
	"""The first line of the progress."""
	return f"[bold]{t('Progress')}[/] · {escape(text)}"

def exam_progress_table(rows):
	"""The exams taken: how many times, passed, and the best grade."""
	table = Table(show_header=True, box=None, header_style="dim")
	for column in (t("Exam"), t("Taken"), t("Passed"), t("Best")):
		table.add_column(column)
	for row in rows:
		table.add_row(escape(row.title), str(row.tries), str(row.passed), f"{points(row.best)}/100")
	return table

def theme_score(row):
	"""How a theme went: 1 OK out of 3 grademe."""
	return t("{oks} OK out of {tries} grademe", oks=row.oks, tries=row.tries)

def exam_menu(exams, first=False):
	"""The menu of the exams: each title with its levels and duration."""
	width = max(len(exam.title) for exam in exams) + 3
	lines = [t("Choose your exam:")]
	for number, exam in enumerate(exams, start=1):
		lines.append(f"  {number}. {exam.title:{width}}{exam_summary(exam)}")
	return lines + [last_choice(len(exams) + 1, first)]

def mode_menu(exam, first=False):
	"""The menu of the modes: what each one means for the time and the waits."""
	hard = ", ".join(map(points, exam.retry["hard"].minutes))
	soft = ", ".join(map(points, exam.retry["soft"].minutes))
	indent = " " * 15
	return [
		t("Choose the mode:"),
		f"  1. {t('Exam'):10}"
			+ t("The real conditions: {length}, then the exam ends.", length=exam_length(exam.duration_minutes)),
		f"{indent}{t('Waits after a failed grademe grow fast (minutes):')}",
		f"{indent}{hard}",
		f"  2. {t('Revision'):10}{t('No time limit.')}",
		f"{indent}{t('Waits after a failed grademe stay short (minutes):')}",
		f"{indent}{soft}",
		last_choice(3, first),
		t("Enter alone takes revision."),
	]

def level_menu(exam, first=False):
	"""What the starting level means: the points of a level, the levels skipped.

	Its last choice comes after the last level: 5 for an exam of 4 levels.
	"""
	playable = ", ".join(map(str, exam.playable_levels))
	return [
		t("Choose the starting level:"),
		"  " + t("{count} levels, worth {points} points each: pass them all for 100/100.",
			count=exam.level_count, points=points(exam.points_per_level)),
		"  " + t("If you start higher, the levels before it give no points."),
		"  " + t("Levels you can play: {levels}.", levels=playable),
		last_choice(exam.level_count + 1, first),
	]

def points_won(won, grade):
	"""Said after an OK: the points of the level, and the grade now."""
	return (f"[bold green]+{t('{points} points', points=points(won))}[/] · "
		+ t("grade {grade}/100", grade=points(grade)))

def no_more_levels(grade):
	"""Said when the last playable level is passed but the grade is below 100."""
	return ("[yellow]" + t("No more playable level for now: your grade is {grade}/100.", grade=points(grade))
		+ "[/] " + t("The next levels have no exercise yet."))

# The style of each status of a tester; any other one (FAIL, CRASH, LEAK...) is a failure.
TESTER_STYLES = {"OK": "green", "PASS": "green", "KO": "red", "WARN": "yellow", "SKIP": "dim", "INFO": "cyan"}

def _status(status):
	return Text(f"{status:8}", style=TESTER_STYLES.get(status, "red"))

def _leader(name, width=32):
	"""`name` and dots up to `width`, like the lines of a tester."""
	text = Text("  " + name + " ")
	text.append("." * max(2, width - len(name)), style="dim")
	return text

def _details(text, indent=12, lines=6):
	"""The lines of a detail, in grey, under the line they explain."""
	return [Text(" " * indent + line, style="dim") for line in text.splitlines()[:lines]]

def _score(passed, total):
	return Text(f" {passed}/{total}", style="green" if passed == total else "red")

def tester_report(report, tester, project):
	"""The results of a tester in the style of 42pal: a list of what rich prints.

	The subject (each check, with the detail of the bad ones), the functions
	(each one, with its failing tests), the undefined cases (not counted),
	then the verdict and the full log of the tester.
	"""
	head = Text(tester.name, style="bold #a5b4fc")
	head.append(f" · {short_path(project)}", style="dim")
	lines = [head]
	if report.error is not None:
		title, detail = report.error
		lines.append(Text("✗ " + t("The tests could not run: {why}", why=title), style="bold red"))
		if detail:
			lines.append(Panel(Text(detail), border_style="red"))
	if report.checks:
		passed, counted = report.conformity_score
		section = Text("\n" + t("The subject"), style="bold")
		section.append_text(_score(passed, counted))
		lines.append(section)
		group = None
		for check in report.checks:
			if check.group != group:
				group = check.group
				lines.append(Text("  " + group, style="bold"))
			line = Text("    ")
			line.append_text(_status(check.status))
			line.append(check.label)
			lines.append(line)
			if check.status != "OK" and check.detail:
				lines += _details(check.detail, indent=14)
	if report.functions:
		passed, total = report.test_score
		section = Text("\n" + t(tester.tests_title), style="bold")
		section.append_text(_score(passed, total))
		lines.append(section)
		names = report.names
		for function in report.functions:
			line = _leader(names.get(function.name) or tester.prefix + function.name)
			line.append_text(_score(function.passed, function.total))
			lines.append(line)
			bad = function.bad
			# A function absent from the library: once, not for each of its tests.
			if bad and all(test.status == "MISSING" for test in function.tests):
				line = Text("    ")
				line.append_text(_status("MISSING"))
				line.append(bad[0].detail)
				lines.append(line)
				continue
			# A whole suite failing the same way: once.
			if len(bad) > 2 and len(bad) == function.total and len({test.detail for test in bad}) == 1:
				line = Text("    ")
				line.append_text(_status(bad[0].status))
				line.append(t("all {count}", count=len(bad)))
				lines.append(line)
				lines += _details(bad[0].detail)
				continue
			# The failures, then the warnings (not counted, but to look at).
			for test in bad + function.warnings:
				line = Text("    ")
				line.append_text(_status(test.status))
				line.append(test.short_name)
				lines.append(line)
				lines += _details(test.detail)
	if report.info:
		lines.append(Text("\n" + t("Undefined cases, not counted"), style="bold"))
		for test in report.info:
			line = _leader(test.short_name)
			line.append(" " + (test.detail.splitlines() or [""])[0], style="cyan")
			lines.append(line)
	lines += [Text("! " + note, style="yellow") for note in report.notes or ()]
	lines.append(Text())
	lines.append(tester_verdict(report))
	if report.log:
		log = Text(t("Full log:") + " ", style="dim")
		log.append(short_path(report.log), style=f"link {Path(report.log).resolve().as_uri()}")
		lines.append(log)
	lines.append(Text("\n" + t(DISCLAIMER), style="dim italic"))
	return lines

# The colors of the cells of the panel of a tester.
CELL_GOOD, CELL_BAD, CELL_WAITING = "#4ade80", "#f87171", "#2a2f3a"

def tester_panel(rows, done, width=44, label_width=22):
	"""The panel of the suites of a tester: a group of rows, each its label, a cell a test, its score.

	rows: the suites the tester gives (testers.suites_of); done: {suite: [True
	when it passed, ...]}. A cell is green when its test passed, red when it
	failed, dim while waiting; with more tests than room, a cell stands for
	several (red when one failed). The tester draws the same on its own.
	"""
	text, group = Text(), None
	for row in rows:
		if row["group"] != group:
			group = row["group"]
			if text:
				text.append("\n\n")
			text.append(group, style="bold")
			label_room = min(label_width, max(len(other["label"]) for other in rows if other["group"] == group))
		results = done.get(row["key"], [])
		label = row["label"] if len(row["label"]) <= label_room else row["label"][:label_room - 1] + "…"
		text.append("\n " + label.ljust(label_room) + " ", style="#d1d5db")
		tests = max(row["tests"], len(results), 1)
		cells = min(tests, max(4, width - label_room - 10))
		for cell in range(cells):
			part = results[cell * tests // cells:(cell + 1) * tests // cells]
			covered = (cell + 1) * tests // cells - cell * tests // cells
			if False in part:
				style = CELL_BAD
			elif part and len(part) == covered:
				style = CELL_GOOD
			else:
				style = CELL_WAITING
			text.append("■", style=style)
		if results:
			bad = results.count(False)
			finished = len(results) >= row["tests"]
			text.append(f" {len(results) - bad}/{len(results)}",
				style=CELL_BAD if bad else CELL_GOOD if finished else "#9ca3af")
	return text

def progress_bar(done, total, width=24):
	"""A bar of `width` characters, filled as `done` goes to `total`."""
	filled = round(width * done / total) if total else 0
	return "━" * filled + "─" * (width - filled)

def tester_progress(tester, progress):
	"""What the tester is doing, for the spinner: the step, then the tests done and failed."""
	if progress.step == "subject":
		count = len(progress.checks)
		return t("{tester} · the subject: 1 check", tester=tester.name) if count == 1 else t(
			"{tester} · the subject: {count} checks", tester=tester.name, count=count)
	if progress.step == "build":
		return t("{tester} · building the tests…", tester=tester.name)
	if progress.step == "tests":
		return t("{tester} · tests {done}/{total} {bar} {bad} KO", tester=tester.name, done=progress.tests_done,
			total=progress.tests_total, bar=progress_bar(progress.tests_done, progress.tests_total),
			bad=len(progress.bad))
	return t("{tester} is starting…", tester=tester.name)

def tester_live_lines(tester, item, group, names=None):
	"""The lines of a check or of a failed test as it comes, and the group of checks now.

	A check under the name of its group when the group changes; a failed
	test with its function (or the name of its suite, from names) and the
	first line of its detail.
	"""
	lines = []
	if hasattr(item, "label"):
		if item.group != group:
			group = item.group
			lines.append(Text("  " + group, style="bold"))
		line = Text("    ")
		line.append_text(_status(item.status))
		line.append(item.label)
		lines.append(line)
		if item.status != "OK" and item.detail:
			lines += _details(item.detail, indent=14, lines=2)
	elif item is not None and item.bad:
		line = Text("    ")
		line.append_text(_status(item.status))
		suite = (names or {}).get(item.function) or f"{tester.prefix}{item.function}"
		line.append(f"{suite} · {item.short_name}")
		lines.append(line)
		lines += _details(item.detail, lines=1)
	return lines, group

def tester_verdict(report):
	"""✓ OK or ✗ KO, with the scores of the subject and of the tests."""
	verdict = Text("✓ OK" if report.passed else "✗ KO", style="bold green" if report.passed else "bold red")
	scores = []
	if report.checks:
		scores.append(t("subject {passed}/{total}", passed=report.conformity_score[0], total=report.conformity_score[1]))
	if report.functions:
		scores.append(t("tests {passed}/{total}", passed=report.test_score[0], total=report.test_score[1]))
	if scores:
		verdict.append("  " + " · ".join(scores))
	return verdict

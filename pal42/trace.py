"""The text of a trace, like the moulinette's, explaining a failed grademe.

The traces of a test start with its command: "./name args | cat -e" for a
program, the call for a function (see subject.test_command).

Like the rest of the core, this module never prints: it returns the text,
and the front-ends show it or write it in traces/. The words are in the
language chosen in Settings (see pal42/i18n.py).
"""

import difflib

from pal42.i18n import N_, t
from pal42.subject import cat_e

# A trace is as wide as a subject.
WIDTH = 80

def header(title):
	"""Return a title line padded with = up to WIDTH, like "= Test 1 =====..."."""
	start = f"= {title} "
	return start + "=" * (WIDTH - len(start))

def diff_trace(number, command, student, expected):
	"""Return the trace of test `number`, whose output differs from the oracle's.

	Both outputs are shown like cat -e, the student's lines as - and the
	expected ones as +, so that even a missing \\n can be seen.
	"""
	student_lines = cat_e(student).splitlines()
	expected_lines = cat_e(expected).splitlines()
	# n: as much context as there are lines, so that the whole output shows.
	diff = difflib.unified_diff(
		student_lines, expected_lines, t("student"), "moulinette",
		n=max(len(student_lines), len(expected_lines)), lineterm="",
	)
	# The @@ lines (line numbers of the diff) would only clutter the trace.
	lines = [line for line in diff if not line.startswith("@@")]
	return "\n".join([
		header(t("Test {number}", number=number)),
		f"$> {command}",
		*lines,
		"",
		"Diff KO",
	]) + "\n"

# What a student reads when a signal killed the program.
SIGNAL_MESSAGES = {
	"SIGSEGV": N_("Segmentation fault"),
	"SIGBUS": N_("Bus error"),
	"SIGABRT": N_("Abort (double free, assert...)"),
	"SIGFPE": N_("Floating point exception (division by zero?)"),
	"SIGXFSZ": N_("Output too long: over 1 MB"),
	"SIGKILL": N_("Killed"),
}

def crash_trace(number, command, result):
	"""Return the trace of test `number`, whose program timed out or crashed."""
	if result.timed_out:
		reason = t("Timeout")
	else:
		reason = t(SIGNAL_MESSAGES[result.signal]) if result.signal in SIGNAL_MESSAGES else result.signal
	return "\n".join([
		header(t("Test {number}", number=number)),
		f"$> {command}",
		"",
		reason,
	]) + "\n"

def compile_trace(command_line, output):
	"""Return the trace of a failed compilation: the command, then the compiler's words."""
	return "\n".join([
		header(t("Compilation")),
		f"$> {command_line}",
		output.rstrip("\n"),
		"",
		"Compilation KO",
	]) + "\n"

def missing_trace(files):
	"""Return the trace of a rendu that lacks some expected `files`."""
	return "\n".join([
		header(t("Files")),
		*(t("Missing file: {file}", file=file) for file in files),
		"",
		"Files KO",
	]) + "\n"

def forbidden_trace(forbidden, allowed):
	"""Return the trace of a program that calls `forbidden` functions."""
	return "\n".join([
		header(t("Forbidden functions")),
		*(t("Forbidden function: {name}", name=name) for name in forbidden),
		t("Allowed functions: {names}", names=", ".join(allowed) or t("none")),
		"",
		"Functions KO",
	]) + "\n"

def python_forbidden_trace(found, allowed_imports, forbidden_calls):
	"""Return the trace of a Python file that imports or calls what it may not."""
	forbidden = ", ".join(f"{name}()" for name in forbidden_calls)
	return "\n".join([
		header(t("Forbidden")),
		*(t("Forbidden: {name}", name=name) for name in found),
		t("Allowed imports: {names}", names=", ".join(allowed_imports) or t("none")),
		*([t("Forbidden calls: {names}", names=forbidden)] if forbidden else []),
		"",
		"Forbidden KO",
	]) + "\n"

def main_trace():
	"""Return the trace of a function rendu that has its own main."""
	return "\n".join([
		header(t("Files")),
		t("Your files contain a main: for a function, hand in the function only."),
		t("The test main is given by the moulinette."),
		"",
		"Files KO",
	]) + "\n"

def leak_trace(number, command, report):
	"""Return the trace of test `number`, where valgrind found a leak or a memory error."""
	return "\n".join([
		header(t("Test {number}", number=number)),
		f"$> {command}",
		"",
		t("Memory leaks or errors (valgrind):"),
		report.rstrip("\n"),
		"",
		"Leaks KO",
	]) + "\n"

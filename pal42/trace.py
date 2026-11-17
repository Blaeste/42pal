"""The text of a trace, like the moulinette's, explaining a failed grademe.

Like the rest of the core, this module never prints: it returns the text,
and the front-ends show it or write it in traces/.
"""

import difflib

from pal42.subject import cat_e, example_command

# A trace is as wide as a subject.
WIDTH = 80

def header(title):
	"""Return a title line padded with = up to WIDTH, like "= Test 1 =====..."."""
	start = f"= {title} "
	return start + "=" * (WIDTH - len(start))

def diff_trace(number, name, test, student, expected):
	"""Return the trace of test `number`, whose output differs from the oracle's.

	Both outputs are shown like cat -e, the student's lines as - and the
	expected ones as +, so that even a missing \\n can be seen.
	"""
	student_lines = cat_e(student).splitlines()
	expected_lines = cat_e(expected).splitlines()
	# n: as much context as there are lines, so that the whole output shows.
	diff = difflib.unified_diff(
		student_lines, expected_lines, "student", "moulinette",
		n=max(len(student_lines), len(expected_lines)), lineterm="",
	)
	# The @@ lines (line numbers of the diff) would only clutter the trace.
	lines = [line for line in diff if not line.startswith("@@")]
	return "\n".join([
		header(f"Test {number}"),
		f"$> {example_command(name, test)} | cat -e",
		*lines,
		"",
		"Diff KO",
	]) + "\n"

# What a student reads when a signal killed the program.
SIGNAL_MESSAGES = {
	"SIGSEGV": "Segmentation fault",
	"SIGBUS": "Bus error",
	"SIGABRT": "Abort (double free, assert...)",
	"SIGFPE": "Floating point exception (division by zero?)",
	"SIGXFSZ": "Output too long: over 1 MB",
	"SIGKILL": "Killed",
}

def crash_trace(number, name, test, result):
	"""Return the trace of test `number`, whose program timed out or crashed."""
	if result.timed_out:
		reason = "Timeout"
	else:
		reason = SIGNAL_MESSAGES.get(result.signal, result.signal)
	return "\n".join([
		header(f"Test {number}"),
		f"$> {example_command(name, test)} | cat -e",
		"",
		reason,
	]) + "\n"

def compile_trace(command, files, name, output):
	"""Return the trace of a failed compilation: the command, then the compiler's words."""
	return "\n".join([
		header("Compilation"),
		f"$> {' '.join([*command, *files, '-o', name])}",
		output.rstrip("\n"),
		"",
		"Compilation KO",
	]) + "\n"

def missing_trace(files):
	"""Return the trace of a rendu that lacks some expected `files`."""
	return "\n".join([
		header("Files"),
		*(f"Missing file: {file}" for file in files),
		"",
		"Files KO",
	]) + "\n"

def forbidden_trace(forbidden, allowed):
	"""Return the trace of a program that calls `forbidden` functions."""
	return "\n".join([
		header("Forbidden functions"),
		*(f"Forbidden function: {name}" for name in forbidden),
		f"Allowed functions: {', '.join(allowed) or 'none'}",
		"",
		"Functions KO",
	]) + "\n"

def main_trace():
	"""Return the trace of a function rendu that has its own main."""
	return "\n".join([
		header("Files"),
		"Your files contain a main: for a function, hand in the function only.",
		"The test main is given by the moulinette.",
		"",
		"Files KO",
	]) + "\n"

def leak_trace(number, name, test, report):
	"""Return the trace of test `number`, where valgrind found a leak or a memory error."""
	return "\n".join([
		header(f"Test {number}"),
		f"$> {example_command(name, test)} | cat -e",
		"",
		"Memory leaks or errors (valgrind):",
		report.rstrip("\n"),
		"",
		"Leaks KO",
	]) + "\n"

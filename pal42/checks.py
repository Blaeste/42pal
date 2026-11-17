"""Checks made on the student's compiled code, beyond its output.

They read the symbols of the student's objects (.o) with nm: the library
functions called, to refuse the forbidden ones, and whether a main is
defined. They also run the program under valgrind, for leaks and memory
errors. Like the rest of the core, this module never prints.
"""

import re
import subprocess
import tempfile
from pathlib import Path

from pal42.runners.base import run_command

def used_functions(*files, nm="nm"):
	"""Return the names of the library functions that `files` call.

	files are objects or programs. A function defined in one of them (one
	student file calling another) is not counted. Names starting with _
	belong to the C runtime (__libc_start_main...), not to the student's code.
	Without nm on the machine, the check cannot be made: nothing is listed,
	so nothing is refused.
	"""
	undefined = _symbols(files, nm, "-u", kind="U")
	if undefined is None:
		return set()
	defined = _symbols(files, nm, "--defined-only")
	return {name for name in undefined - defined if not name.startswith("_")}

def defines_main(*files, nm="nm"):
	"""True when `files` define a main: a function rendu must not have one."""
	return "main" in (_symbols(files, nm, "--defined-only") or set())

def _symbols(files, nm, option, kind=None):
	"""Return the symbol names nm lists with `option`, or None without nm.

	nm prints one symbol per line: "U printf@GLIBC_2.2.5" for an undefined
	one, "0000000000001139 T main" for a defined one; the letter before the
	name is its kind. kind keeps only one kind; the @version is dropped.
	"""
	try:
		process = subprocess.run([nm, option, *map(str, files)], capture_output=True, text=True)
	except FileNotFoundError:
		return None
	names = set()
	for line in process.stdout.splitlines():
		parts = line.split()
		# Lines with one word are the "file.o:" headers nm adds for several files.
		if len(parts) >= 2 and (kind is None or parts[-2] == kind):
			names.add(parts[-1].split("@")[0])
	return names

# Exit code valgrind is asked to give when it finds a leak or a memory error.
VALGRIND_ERROR = 42

def memory_report(program, test, timeout=30.0, valgrind="valgrind"):
	"""Return what valgrind says about `program` run on `test`.

	"" when every allocation is freed and no memory error is seen; otherwise
	the report (leaks, invalid reads or writes...), without valgrind's ==pid==
	marks. None when valgrind is not on the machine: nothing could be checked.
	The timeout is long: a program runs much slower under valgrind.
	"""
	with tempfile.TemporaryDirectory() as tmp:
		# The report goes to a file: run_command does not keep stderr.
		log = Path(tmp) / "valgrind.log"
		argv = [
			valgrind, "-q", "--leak-check=full",
			# Only the memory really lost counts, not "still reachable".
			"--errors-for-leak-kinds=definite,indirect",
			f"--error-exitcode={VALGRIND_ERROR}", f"--log-file={log}",
			str(program), *test.args,
		]
		try:
			result = run_command(argv, test.stdin, timeout)
		except FileNotFoundError:
			return None
		if result.exit_code != VALGRIND_ERROR:
			return ""
		text = log.read_text(encoding="utf-8", errors="replace")
	# Each line starts with ==12345==, the number of the process: dropped.
	lines = [re.sub(r"^==\d+== ?", "", line) for line in text.splitlines()]
	return "\n".join(lines).strip("\n") + "\n"

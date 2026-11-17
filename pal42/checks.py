"""Checks made on a compiled program, beyond its output.

For now: the library functions it uses, to refuse the forbidden ones. Like
the rest of the core, this module never prints.
"""

import subprocess

def used_functions(program, nm="nm"):
	"""Return the names of the library functions `program` calls.

	nm -u lists the symbols a program takes from outside, one per line, like
	"U printf@GLIBC_2.2.5". Only the U lines (functions) are kept, without the
	@version. Names starting with _ belong to the C runtime itself
	(__libc_start_main...), not to the student's code: they are left out.
	Without nm on the machine, the check cannot be made: nothing is listed,
	so nothing is refused.
	"""
	try:
		process = subprocess.run([nm, "-u", str(program)], capture_output=True, text=True)
	except FileNotFoundError:
		return set()
	functions = set()
	for line in process.stdout.splitlines():
		parts = line.split()
		if len(parts) == 2 and parts[0] == "U":
			name = parts[1].split("@")[0]
			if not name.startswith("_"):
				functions.add(name)
	return functions

"""The C runner: compiles a student's .c files like the moulinette."""

import shutil
import subprocess
from pathlib import Path

from pal42.runners.base import DEFAULT_TIMEOUT, MAX_OUTPUT, CompileResult, run_command

# The flags of the moulinette; an exam can give its own command instead.
DEFAULT_COMMAND = ("cc", "-Wall", "-Wextra", "-Werror")

class CRunner:
	"""Compiles C files with a compile command (DEFAULT_COMMAND by default)."""

	def __init__(self, command=DEFAULT_COMMAND, timeout=DEFAULT_TIMEOUT):
		self.command = tuple(command)
		# Seconds the student's program may run on one test.
		self.timeout = timeout

	def compile(self, sources, workdir, name):
		"""Compile `sources` into the program workdir/name.

		The sources are first copied into workdir and compiled there, by their
		own names: the errors read "bad.c:3:6", without the folder, and the
		student's folder is left untouched.
		"""
		workdir = Path(workdir)
		for source in sources:
			# resolve() gives the full path, so the same folder is recognized
			# however it is written; a file already there needs no copy.
			if Path(source).resolve().parent != workdir.resolve():
				shutil.copy(source, workdir)
		names = [Path(source).name for source in sources]
		try:
			process = subprocess.run(
				[*self.command, *names, "-o", name],
				cwd=workdir, capture_output=True, text=True,
			)
		# The command of an exam may name a compiler this machine lacks.
		except FileNotFoundError:
			return CompileResult(False, f"compilateur introuvable : {self.command[0]}", None)
		ok = process.returncode == 0
		binary = workdir / name if ok else None
		return CompileResult(ok, process.stdout + process.stderr, binary)

	def run(self, program, test, max_output=MAX_OUTPUT):
		"""Run the compiled `program` on `test`: its arguments and standard input."""
		return run_command([str(program), *test.args], test.stdin, self.timeout, max_output)

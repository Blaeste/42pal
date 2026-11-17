"""The grader: checks a student's rendu against the oracle, like the moulinette.

It compiles the rendu in a temporary folder, runs each test of the variant,
and stops at the first one whose output differs from the oracle's. Like the
rest of the core, it never prints: the trace comes back as text.
"""

import random
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pal42 import trace

@dataclass(frozen=True)
class Grade:
	"""The result of a grademe.

	passed tells whether every test passed; trace explains the first failure
	(empty when passed); tests_passed counts the tests passed before it.
	"""
	passed: bool
	trace: str
	tests_passed: int
	tests_total: int

def grade(variant, rendu, runner, progress=None):
	"""Grade the files of `rendu` (the student's folder) for `variant`.

	In order: the expected files must be there, they must compile, then each
	test must neither crash nor time out, and print what the oracle says.
	The first failure stops the grading and gives the trace.
	progress(number, total), if given, is called before each test: the
	front-ends use it to show how far the grading is.
	"""
	exo = variant.exercise
	# The tests depend on the variant's seed: grading twice runs the same ones.
	tests = exo.generate_tests(variant.params, random.Random(variant.seed))
	sources = [Path(rendu) / file for file in variant.expected_files]
	missing = [source.name for source in sources if not source.is_file()]
	if missing:
		return Grade(False, trace.missing_trace(missing), 0, len(tests))
	with tempfile.TemporaryDirectory() as work:
		compiled = runner.compile(sources, work, variant.name)
		if not compiled.ok:
			text = trace.compile_trace(
				runner.command, variant.expected_files, variant.name, compiled.output
			)
			return Grade(False, text, 0, len(tests))
		program = compiled.binary
		for number, test in enumerate(tests, start=1):
			if progress:
				progress(number, len(tests))
			result = runner.run(program, test)
			if result.timed_out or result.signal:
				text = trace.crash_trace(number, variant.name, test, result)
				return Grade(False, text, number - 1, len(tests))
			expected = exo.oracle(variant.params, test)
			if result.stdout != expected.encode():
				text = trace.diff_trace(number, variant.name, test, result.stdout, expected)
				return Grade(False, text, number - 1, len(tests))
	return Grade(True, "", len(tests), len(tests))

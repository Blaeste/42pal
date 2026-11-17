"""Tests of pal42.subject: writing the subject of a variant in the 42 format.

Run all the tests from the project root with: python3 -m unittest -v
"""

import subprocess
import unittest
from pathlib import Path

from pal42.model import Param, TestCase
from pal42.subject import cat_e, render, shell_quote
from pal42.variant import Variant
from tests.helpers import make_exercise

# Snapshots of subjects, reviewed once by hand, then compared at each run.
GOLDEN = Path(__file__).resolve().parent / "golden"

def repeat_oracle(params, test):
	"""Oracle of the demo exercise: the argument 2 or 3 times, or a newline."""
	if len(test.args) != 1:
		return "\n"
	count = {"twice": 2, "thrice": 3}[params["times"]]
	return " ".join([test.args[0]] * count) + "\n"

def make_repeat_exercise(**changes):
	"""A small made-up exercise, to render: display the argument 2 or 3 times."""
	fields = dict(
		name="repeat",
		assignment_name="repeat_${times}",
		expected_files=("repeat_${times}.c",),
		allowed_functions=("write",),
		params=(
			Param("times", ("twice", "thrice"), {"twice": "2 times", "thrice": "3 times"}),
		),
		subject=(
			"Write a program that takes a string and displays it $times,\n"
			"separated by spaces, followed by a newline.\n"
			"\n"
			"If the number of arguments is not 1, the program displays a newline."
		),
		oracle=repeat_oracle,
	)
	fields.update(changes)
	return make_exercise(**fields)

def repeat_twice(**changes):
	"""The variant of the demo exercise where times is "twice"."""
	return Variant(make_repeat_exercise(**changes), 0, {"times": "twice"})

def system_cat_e(data):
	"""Return what the system's `cat -e` prints for `data` (bytes)."""
	result = subprocess.run(["cat", "-e"], input=data, capture_output=True, check=True)
	return result.stdout.decode()

class TestCatE(unittest.TestCase):
	"""cat_e(text) shows a text the way `cat -e` does."""

	def test_newline_shows_as_dollar(self):
		"""Each end of line gets a `$`, so a missing \\n can be seen."""
		self.assertEqual(cat_e("hello\nworld\n"), "hello$\nworld$\n")

	def test_same_as_system_cat_e_for_every_byte(self):
		"""Invisible bytes are shown like `cat -e` does: ^A, ^?, M-a..."""
		every_byte = bytes(range(256))
		self.assertEqual(cat_e(every_byte), system_cat_e(every_byte))

class TestShellQuote(unittest.TestCase):
	"""shell_quote(arg) writes an argument the way an example shows it."""

	def test_plain_word_stays_bare_and_others_get_double_quotes(self):
		"""Like in the 42 subjects: hello stays hello, ab c becomes "ab c"."""
		self.assertEqual(shell_quote("hello"), "hello")
		self.assertEqual(shell_quote("ab c"), '"ab c"')

	def test_shell_reads_back_the_same_argument(self):
		"""An example copied into a shell gives the program the same argument."""
		for arg in ["", "ab c", 'say "hi"', "cost $5", "back\\slash", "`ls`", "*"]:
			# printf "[%s]" shows exactly the argument the shell has built.
			command = f'printf "[%s]" {shell_quote(arg)}'
			result = subprocess.run(["sh", "-c", command], capture_output=True, text=True)
			self.assertEqual(result.stdout, f"[{arg}]", command)

class TestRender(unittest.TestCase):
	"""render(variant) writes the whole subject of a variant."""

	def test_header_follows_the_42_format(self):
		"""Assignment name, Expected files and Allowed functions, then dashes."""
		lines = render(repeat_twice(allowed_functions=("write", "malloc"))).splitlines()
		self.assertEqual(lines[:4], [
			"Assignment name  : repeat_twice",
			"Expected files   : repeat_twice.c",
			"Allowed functions: write, malloc",
			"-" * 80,
		])

	def test_statement_holes_get_the_texts_of_the_values(self):
		"""Under the dashes: an empty line, then the statement, $times filled."""
		statement = render(repeat_twice()).split("-" * 80 + "\n")[1]
		self.assertEqual(statement, (
			"\n"
			"Write a program that takes a string and displays it 2 times,\n"
			"separated by spaces, followed by a newline.\n"
			"\n"
			"If the number of arguments is not 1, the program displays a newline.\n"
		))

	def test_examples_are_computed_by_the_oracle(self):
		"""Each example: the command to type, then the oracle's output in cat -e."""
		examples = (TestCase(("hello",)), TestCase(("ab c",)), TestCase())
		subject = render(repeat_twice(examples=examples))
		self.assertTrue(subject.endswith(
			"\n"
			"Examples:\n"
			"\n"
			"$>./repeat_twice hello | cat -e\n"
			"hello hello$\n"
			'$>./repeat_twice "ab c" | cat -e\n'
			"ab c ab c$\n"
			"$>./repeat_twice | cat -e\n"
			"$\n"
		), subject)

class TestGolden(unittest.TestCase):
	"""The subject stays the same as a snapshot reviewed once by hand."""

	def test_subject_matches_the_reviewed_snapshot(self):
		"""The subject of repeat_twice is the one saved in tests/golden/.

		If the file is missing, the test writes it and fails: read it, and if
		it is right, run the tests again. After a wanted change of the format,
		delete the file so that the test writes it again.
		"""
		path = GOLDEN / "repeat_twice.txt"
		examples = (TestCase(("hello",)), TestCase(("ab c",)), TestCase())
		subject = render(repeat_twice(examples=examples))
		if not path.exists():
			path.parent.mkdir(exist_ok=True)
			# encoding: the campus locale may not be UTF-8 by default.
			path.write_text(subject, encoding="utf-8")
			self.fail(f"snapshot written: read {path}, then run the tests again")
		self.assertEqual(subject, path.read_text(encoding="utf-8"))

"""Tests of pal42.model: the data that describes an exercise and its checks.

Run all the tests from the project root with: python3 -m unittest -v
"""

import unittest

from pal42.model import Exercise, ExerciseError, Param

def fake_oracle(params, test):
	"""Stand-in oracle: these tests only build exercises, they never grade."""
	return ""

def fake_generate_tests(params, rng):
	"""Stand-in test generator: these tests never ask for test cases."""
	return []

def make_exercise(**changes):
	"""Build a valid exercise, with the fields given in `changes` replaced.

	Each test changes only the field it is about, so the rest stays valid.
	"""
	fields = dict(
		name="char_filter",
		language="c",
		kind="program",
		expected_files=("char_filter.c",),
		allowed_functions=("write",),
		themes=("char_sets",),
		params=(Param("mode", ("common", "only_first")),),
		subject="Display the characters $mode, without doubles.",
		oracle=fake_oracle,
		generate_tests=fake_generate_tests,
	)
	fields.update(changes)
	return Exercise(**fields)

class TestParam(unittest.TestCase):
	"""Building a Param."""

	def test_param_without_values_raises(self):
		"""A param with no value could never be drawn; its name is in the message."""
		with self.assertRaisesRegex(ExerciseError, "mode"):
			Param("mode", ())

class TestExercise(unittest.TestCase):
	"""Building an Exercise and checking it as soon as it is created."""

	def test_valid_exercise_is_created(self):
		"""An exercise whose subject only uses its own params is accepted."""
		exo = make_exercise()
		self.assertEqual(exo.name, "char_filter")
		self.assertEqual(exo.params[0].values, ("common", "only_first"))

	def test_subject_with_unknown_param_raises(self):
		"""A `$hole` that matches no param is an error, named in the message."""
		with self.assertRaisesRegex(ExerciseError, "order"):
			make_exercise(subject="Display the characters $mode, in $order.")

	def test_lone_dollar_in_subject_raises(self):
		"""A `$` that starts no hole is an error that gives its line; `$$` is the fix."""
		with self.assertRaisesRegex(ExerciseError, r"ligne 2.*\$\$"):
			make_exercise(subject="Display the characters $mode.\nEach costs 5$.")

	def test_forbidden_combination_with_unknown_param_raises(self):
		"""A forbidden combination that names no param would never match."""
		with self.assertRaisesRegex(ExerciseError, "order"):
			make_exercise(forbidden=({"mode": "common", "order": "first"},))

	def test_forbidden_combination_with_unknown_value_raises(self):
		"""A typo in a forbidden value would let the real subject be drawn."""
		with self.assertRaisesRegex(ExerciseError, "comon"):
			make_exercise(forbidden=({"mode": "comon"},))

	def test_unknown_kind_raises(self):
		"""kind must be "program" or "function", the two kinds the graders know."""
		with self.assertRaisesRegex(ExerciseError, "fonction"):
			make_exercise(kind="fonction")

	def test_unknown_language_raises(self):
		"""language must be one the project has a runner for: c, cpp or python."""
		with self.assertRaisesRegex(ExerciseError, "rust"):
			make_exercise(language="rust")

"""Helpers shared by the tests: a valid exercise to start from, and fakes.

Not a test module itself (its name does not start with test_), so unittest
does not look for tests in it.
"""

from pal42.model import Exercise, Param

def fake_oracle(params, test):
	"""Stand-in oracle, for tests that never grade."""
	return ""

def fake_generate_tests(params, rng):
	"""Stand-in test generator, for tests that never ask for test cases."""
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

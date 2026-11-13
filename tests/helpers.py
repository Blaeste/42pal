"""Helpers shared by the tests: a valid exercise to start from, and fakes.

Why: an Exercise needs 10 fields, but each test is about only one of them.
make_exercise() builds a valid exercise with default values, and a test
replaces only the fields it is about:

	from tests.helpers import make_exercise

	exo = make_exercise()                    # the default char_filter exercise
	exo = make_exercise(kind="fonction")     # same, but kind is "fonction"
	exo = make_exercise(                     # several fields replaced at once
		subject="Display $mode.",
		forbidden=({"mode": "common"},),
	)

Not a test module itself (its name does not start with test_), so unittest
does not look for tests in it.
"""

from pal42.model import Exercise, Param

# An Exercise must be given two functions (like function pointers in C):
# the oracle, which computes the expected output, and the test generator.
# The tests of the model and of the draw never grade anything, so these
# do nothing; they only fill the two fields.

def fake_oracle(params, test):
	"""Stand-in oracle, for tests that never grade."""
	return ""

def fake_generate_tests(params, rng):
	"""Stand-in test generator, for tests that never ask for test cases."""
	return []

def make_exercise(**changes):
	"""Build a valid exercise, with the fields given in `changes` replaced.

	Each test changes only the field it is about, so the rest stays valid.
	Any field of Exercise can be replaced, by its name (see pal42/model.py).
	"""
	# **changes gathers the named arguments into a dict:
	# make_exercise(kind="fonction") gives changes = {"kind": "fonction"}.

	# The default values: together, they make a valid exercise.
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
	# update replaces the default values by the ones given in changes;
	# the fields that are not in changes keep their default value.
	fields.update(changes)
	# **fields unpacks the dict back into named arguments: the same as
	# Exercise(name="char_filter", language="c", kind="fonction", ...).
	return Exercise(**fields)

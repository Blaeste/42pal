"""Tests of the reference solutions: one ref.c per exercise, for every variant.

Run all the tests from the project root with: python3 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pal42.catalog import load_catalog
from pal42.reference import check_variant, reference_files, variants_to_check
from pal42.runners.c import DEFAULT_COMMAND, CRunner
from pal42.variant import Variant, draw
from tests.helpers import ECHO_OK, echo_oracle, echo_tests, make_exercise

CATALOG = load_catalog()

def compile_reference(name, params, work, flags=None):
	"""Compile the ref.c of exercise `name` for `params`; return the CompileResult.

	The other expected files (a header) are taken next to ref.c, like
	check-catalog does. flags are the -D flags of the variant unless given.
	A function exercise is compiled with its test main, like a student's
	rendu.
	"""
	variant = Variant(CATALOG.exercises[name], 0, params)
	extra = []
	if variant.exercise.kind == "function":
		extra.append(Path(work) / "main_42pal.c")
		extra[0].write_text(variant.harness, encoding="utf-8")
	command = DEFAULT_COMMAND + (variant.defines if flags is None else flags)
	# ref.c, with the header the student hands in too, if any, next to it.
	sources = list(reference_files(variant, CATALOG.folders[name] / "ref.c").values())
	return CRunner(command).compile(sources, work, variant.name, extra=extra)

class TestReferences(unittest.TestCase):
	"""Every exercise of the catalog has a ref.c that builds each of its variants."""

	def test_ref_c_compiles_for_every_allowed_combination(self):
		"""cc -Wall -Wextra -Werror -D...: no error, for every variant."""
		for name, exo in CATALOG.exercises.items():
			for params in exo.combinations():
				with self.subTest(f"{name} {params}"), tempfile.TemporaryDirectory() as work:
					result = compile_reference(name, params, work)
					self.assertTrue(result.ok, result.output)

	def test_ref_c_refuses_to_compile_without_its_flags(self):
		"""No -D flag: #error says which one to choose, so the flags are really used."""
		for name, exo in CATALOG.exercises.items():
			with self.subTest(name), tempfile.TemporaryDirectory() as work:
				result = compile_reference(name, exo.combinations()[0], work, flags=())
				self.assertFalse(result.ok)
				self.assertIn("choose", result.output)

class TestVariantsToCheck(unittest.TestCase):
	"""variants_to_check(exo): which variants check-catalog grades."""

	def test_every_combination_once_with_a_seed_that_draws_it_again(self):
		"""Each combination once; exo#seed draws the same variant again."""
		exo = CATALOG.exercises["char_filter"]
		variants = variants_to_check(exo)
		combinations = [variant.params for variant in variants]
		self.assertEqual(len(variants), len(exo.combinations()))
		self.assertCountEqual(combinations, exo.combinations())
		for variant in variants:
			self.assertEqual(draw(exo, variant.seed).params, variant.params)

	def test_too_many_combinations_gives_at_most_max_variants(self):
		"""18 combinations, at most 5 asked: 5 variants, seeds 0 to 4."""
		variants = variants_to_check(CATALOG.exercises["shift_letters"], max_variants=5)
		self.assertEqual([variant.seed for variant in variants], [0, 1, 2, 3, 4])

class TestCheckVariant(unittest.TestCase):
	"""check_variant(variant, ref): ref.c graded like a student's rendu."""

	def test_real_ref_c_passes_its_variant(self):
		"""char_filter#0: ref.c, with its -D flags, passes every test."""
		variant = draw(CATALOG.exercises["char_filter"], 0)
		result = check_variant(variant, CATALOG.folders["char_filter"] / "ref.c")
		self.assertTrue(result.passed, result.trace)

	def test_wrong_oracle_makes_the_reference_fail(self):
		"""An oracle that shouts (upper case) disagrees with ref.c: KO, with the trace."""
		exo = make_exercise(
			name="echo_first", expected_files=("echo_first.c",),
			oracle=lambda params, test: echo_oracle(params, test).upper(),
			generate_tests=echo_tests,
		)
		with tempfile.TemporaryDirectory() as tmp:
			ref = Path(tmp) / "ref.c"
			ref.write_text(ECHO_OK, encoding="utf-8")
			result = check_variant(Variant(exo, 3, {"mode": "common"}), ref)
		self.assertFalse(result.passed)
		self.assertIn("-hello$\n+HELLO$", result.trace)

	def test_a_header_the_student_hands_in_is_taken_next_to_ref_c(self):
		"""Expected files echo_first.c and echo.h: echo.h comes from the folder of ref.c."""
		exo = make_exercise(
			name="echo_first", expected_files=("echo_first.c", "echo.h"),
			oracle=echo_oracle, generate_tests=echo_tests,
		)
		variant = Variant(exo, 3, {"mode": "common"})
		with tempfile.TemporaryDirectory() as tmp:
			ref = Path(tmp) / "ref.c"
			ref.write_text(f'#include "echo.h"\n{ECHO_OK}', encoding="utf-8")
			missing = check_variant(variant, ref)
			(Path(tmp) / "echo.h").write_text("typedef int\tt_echo;\n", encoding="utf-8")
			result = check_variant(variant, ref)
		self.assertFalse(missing.passed)
		self.assertIn("echo.h", missing.trace)
		self.assertTrue(result.passed, result.trace)

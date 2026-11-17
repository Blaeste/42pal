"""Tests of the reference solutions: one ref.c per exercise, for every variant.

Run all the tests from the project root with: python3 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pal42.catalog import load_catalog
from pal42.runners.c import DEFAULT_COMMAND, CRunner
from pal42.variant import Variant

CATALOG = load_catalog()

def compile_reference(name, params, work, flags=None):
	"""Compile the ref.c of exercise `name` for `params`; return the CompileResult.

	flags are the -D flags of the variant unless given. A function exercise
	is compiled with its test main, like a student's rendu.
	"""
	variant = Variant(CATALOG.exercises[name], 0, params)
	extra = []
	if variant.exercise.kind == "function":
		extra.append(Path(work) / "main_42pal.c")
		extra[0].write_text(variant.harness, encoding="utf-8")
	command = DEFAULT_COMMAND + (variant.defines if flags is None else flags)
	ref = CATALOG.folders[name] / "ref.c"
	return CRunner(command).compile([ref], work, variant.name, extra=extra)

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

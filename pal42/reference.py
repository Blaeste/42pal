"""Checking the catalog: each ref.c must pass its own exercise, variant by variant.

If the oracle and ref.c, written separately, disagree on a test, one of them
is wrong: that is how the grading itself is checked. Like the rest of the
core, this module never prints.
"""

import shutil
import tempfile
from pathlib import Path

from pal42.grader import grade
from pal42.runners.c import DEFAULT_COMMAND, CRunner
from pal42.variant import draw

# Past this many combinations, check-catalog grades this many variants only.
MAX_VARIANTS = 50

def variants_to_check(exo, max_variants=MAX_VARIANTS):
	"""Return the variants of `exo` to grade: each combination once.

	They are drawn like at the exam, with the seeds 0, 1, 2..., so that a
	failure named exo#seed can be drawn again exactly. With more than
	max_variants combinations, only the first max_variants seeds are taken.
	"""
	if len(exo.combinations()) > max_variants:
		return [draw(exo, seed) for seed in range(max_variants)]
	found = {}
	seed = 0
	while len(found) < len(exo.combinations()):
		variant = draw(exo, seed)
		# A dict is not hashable: its sorted pairs stand for the combination.
		found.setdefault(tuple(sorted(variant.params.items())), variant)
		seed += 1
	return list(found.values())

def check_variant(variant, ref):
	"""Grade the reference solution `ref` (a ref.c) for `variant`; return the Grade.

	ref.c is put in a temporary rendu under the expected file's name, then
	graded like a student's work, compiled with the -D flags of the variant:
	it must call no forbidden function and pass every test of the oracle.
	"""
	with tempfile.TemporaryDirectory() as rendu:
		shutil.copy(ref, Path(rendu) / variant.expected_files[0])
		runner = CRunner(DEFAULT_COMMAND + variant.defines)
		return grade(variant, rendu, runner)

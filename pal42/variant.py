"""Drawing a variant: one value for each param of an exercise, from a seed.

A variant is reproducible: the same exercise and the same seed always give
the same variant, so `exo#seed` is enough to find it again.
"""

import random
from dataclasses import dataclass
from string import Template

from pal42.model import Exercise

@dataclass(frozen=True)
class Variant:
	"""One variant of an exercise: the values drawn for its params."""
	exercise: Exercise
	seed: int
	params: dict[str, str]

	@property
	def id(self):
		"""`exo#seed`, like "char_filter#42": enough to draw this variant again."""
		return f"{self.exercise.name}#{self.seed}"

	@property
	def name(self):
		"""Assignment name of this variant: its holes filled with the drawn values."""
		template = self.exercise.assignment_name or self.exercise.name
		return Template(template).substitute(self.params)

	@property
	def expected_files(self):
		"""Files the student must hand in, holes filled like the name."""
		return tuple(
			Template(file).substitute(self.params)
			for file in self.exercise.expected_files
		)

def draw(exo, seed):
	"""Draw the variant of `exo` given by `seed`.

	It is picked among the allowed combinations only: no forbidden one can
	come out, and there is no draw-again loop that could never end.
	"""
	# A private Random seeded with `seed`: same seed, same draws, and the
	# global random module stays untouched.
	rng = random.Random(seed)
	params = rng.choice(exo.combinations())
	return Variant(exo, seed, params)

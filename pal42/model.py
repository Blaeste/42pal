"""Data model of an exercise: its parameters, its subject and its checks.

An Exercise is a template: drawing a value for each Param gives a variant
(see variant.py). Like the rest of the core, this module never prints.
"""

from dataclasses import dataclass
from string import Template
from typing import Callable

# Languages that have a runner (runners/), and the kinds of exercise graded:
# a whole program, or a function called by a generated main (harness.py).
LANGUAGES = ("c", "cpp", "python")
KINDS = ("program", "function")

class ExerciseError(ValueError):
	"""An exercise is badly written; the message says which one and why."""

@dataclass(frozen=True)
class Param:
	"""A parameter of an exercise and the values a variant can draw for it.

	name is used as `$name` in the subject; values are short ids like "common".
	"""
	name: str
	values: tuple[str, ...]

	def __post_init__(self):
		"""Check the param as soon as it is created (dataclass hook)."""
		if not self.values:
			raise ExerciseError(f"paramètre « {self.name} » sans aucune valeur")

@dataclass(frozen=True)
class TestCase:
	"""One run of the student's program: its arguments and its standard input."""
	args: tuple[str, ...] = ()
	stdin: str = ""

@dataclass(frozen=True)
class Exercise:
	"""An exercise template, the same for all its variants.

	oracle(params, test) returns the expected output of one TestCase, and
	generate_tests(params, rng) returns the TestCases of a variant; params maps
	each param name to the value drawn for it.
	forbidden lists combinations a variant must never have, like
	{"mode": "common", "order": "first"}: all the pairs must match to forbid.
	"""
	name: str
	language: str
	kind: str
	expected_files: tuple[str, ...]
	allowed_functions: tuple[str, ...]
	themes: tuple[str, ...]
	params: tuple[Param, ...]
	subject: str
	oracle: Callable
	generate_tests: Callable
	forbidden: tuple[dict[str, str], ...] = ()

	def __post_init__(self):
		"""Check the exercise as soon as it is created (dataclass hook)."""
		if self.language not in LANGUAGES:
			self._fail(
				f"langage inconnu « {self.language} », choix : {', '.join(LANGUAGES)}"
			)
		if self.kind not in KINDS:
			self._fail(
				f"type d'exo inconnu « {self.kind} », choix : {', '.join(KINDS)}"
			)
		self._check_subject()
		self._check_forbidden()

	def _check_subject(self):
		"""Each `$name` or `${name}` hole of the subject must be a param."""
		param_names = {param.name for param in self.params}
		# Template.pattern is the regex that string.Template itself uses, so we
		# check exactly the holes it will fill. Not get_identifiers(): 3.11+.
		for match in Template.pattern.finditer(self.subject):
			hole = match.group("named") or match.group("braced")
			if hole is not None and hole not in param_names:
				self._fail(f"le sujet utilise le paramètre inconnu « ${hole} »")
			# "invalid" matches a $ that starts no hole and is not $$.
			if match.group("invalid") is not None:
				line = self.subject.count("\n", 0, match.start()) + 1
				self._fail(
					f"« $ » seul dans le sujet (ligne {line}) : écris « $$ » pour un $"
				)

	def _check_forbidden(self):
		"""Each forbidden combination must use existing params and values.

		A typo there would match no variant, so the combination that gives back
		the real subject could be drawn without anyone noticing.
		"""
		values_of = {param.name: param.values for param in self.params}
		for combination in self.forbidden:
			for name, value in combination.items():
				if name not in values_of:
					self._fail(
						f"combinaison interdite avec le paramètre inconnu « {name} »"
					)
				if value not in values_of[name]:
					self._fail(
						f"combinaison interdite avec la valeur inconnue « {value} »"
						f" pour « {name} »"
					)

	def _fail(self, reason):
		"""Raise an ExerciseError that names this exercise."""
		raise ExerciseError(f"{self.name} : {reason}")

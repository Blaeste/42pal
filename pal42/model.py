"""Data model of an exercise: its parameters, its subject and its checks.

An Exercise is a template: drawing a value for each Param gives a variant
(see variant.py). Like the rest of the core, this module never prints.
"""

import itertools
from dataclasses import dataclass, field
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

	name is used as `$name` in the subject; values are short ids like "common",
	used to draw, to forbid a combination and in the assignment name.
	texts gives the words that `$name` becomes in the subject for each value,
	like {"common": "that appear in both strings"}; empty means the value itself.
	"""
	name: str
	values: tuple[str, ...]
	# field(default_factory=dict): each Param gets its own empty dict;
	# a plain `= {}` default is refused by dataclasses (shared between all).
	texts: dict[str, str] = field(default_factory=dict)

	def __post_init__(self):
		"""Check the param as soon as it is created (dataclass hook)."""
		if not self.values:
			raise ExerciseError(f"paramètre « {self.name} » sans aucune valeur")
		# texts is all or nothing: a text for each value, and nothing else,
		# so no raw id shows up in the middle of a sentence of the subject.
		if self.texts:
			for value in self.texts:
				if value not in self.values:
					raise ExerciseError(
						f"paramètre « {self.name} » : texte pour la valeur inconnue « {value} »"
					)
			for value in self.values:
				if value not in self.texts:
					raise ExerciseError(
						f"paramètre « {self.name} » : pas de texte pour la valeur « {value} »"
					)

	def text(self, value):
		"""Return what `value` becomes in the subject: its text, or itself."""
		return self.texts.get(value, value)

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
	assignment_name is the name the student sees, with holes like the subject
	("${mode}_chars"); empty means `name`, which never changes since it
	identifies the exercise (in `exo#seed`, for example).
	expected_files can have the same holes ("${mode}_chars.c").
	examples are the inputs shown in the subject; their outputs are never
	written by hand: the oracle computes them for the drawn variant.
	The subject may also use $assignment: the name the student sees.
	harness is the C source of the test main of a "function" exercise: it
	reads a test's arguments in argv, calls the student's function and prints
	the result. Its holes take the drawn values, like the name.
	check_leaks asks the grader to run the tests under valgrind too, once
	every output is right: a leak or a memory error then fails the rendu.
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
	assignment_name: str = ""
	examples: tuple[TestCase, ...] = ()
	harness: str = ""
	check_leaks: bool = False

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
		self._check_kind()
		self._check_template(self.subject, "le sujet", extra=("assignment",))
		self._check_template(self.assignment_name, "le nom")
		self._check_template(self.harness, "le main de test")
		for file in self.expected_files:
			self._check_template(file, "un fichier attendu")
		self._check_forbidden()

	def _check_kind(self):
		"""A function needs a test main and has no automatic examples; a program has neither."""
		if self.kind == "function" and not self.harness:
			self._fail("un exo « fonction » a besoin d'un main de test (harness)")
		if self.kind == "program" and self.harness:
			self._fail("un exo « programme » a déjà son main : pas de main de test (harness)")
		if self.kind == "function" and self.examples:
			self._fail(
				"les exemples automatiques lancent ./programme : pas d'exemples pour une"
				" fonction, écris-les dans le sujet"
			)

	def _check_template(self, text, where, extra=()):
		"""Each `$name` or `${name}` hole of `text` must be a param (or in `extra`).

		where names the text in the error messages, like "le sujet".
		"""
		param_names = {param.name for param in self.params} | set(extra)
		# Template.pattern is the regex that string.Template itself uses, so we
		# check exactly the holes it will fill. Not get_identifiers(): 3.11+.
		for match in Template.pattern.finditer(text):
			hole = match.group("named") or match.group("braced")
			if hole is not None and hole not in param_names:
				self._fail(f"{where} utilise le paramètre inconnu « ${hole} »")
			# "invalid" matches a $ that starts no hole and is not $$.
			if match.group("invalid") is not None:
				line = text.count("\n", 0, match.start()) + 1
				self._fail(
					f"« $ » seul dans {where} (ligne {line}) : écris « $$ » pour un $"
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
		# Only once names and values are known: combinations() relies on it.
		if not self.combinations():
			self._fail("aucune combinaison possible, elles sont toutes interdites")

	def combinations(self):
		"""Return every allowed combination of param values, as dicts.

		Params and values keep the order they are written in, so the list is
		always the same, and a seed always picks the same combination.
		"""
		names = [param.name for param in self.params]
		allowed = []
		# product gives every tuple of one value per param: 3 x 2 values -> 6.
		for values in itertools.product(*(param.values for param in self.params)):
			combination = dict(zip(names, values))
			if not self.is_forbidden(combination):
				allowed.append(combination)
		return allowed

	def is_forbidden(self, combination):
		"""True when `combination` matches all the pairs of a forbidden one."""
		return any(
			all(combination[name] == value for name, value in forbidden.items())
			for forbidden in self.forbidden
		)

	def _fail(self, reason):
		"""Raise an ExerciseError that names this exercise."""
		raise ExerciseError(f"{self.name} : {reason}")

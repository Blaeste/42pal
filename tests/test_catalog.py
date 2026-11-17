"""Tests of pal42.catalog: finding the exercises in exercises/ and indexing them.

Run all the tests from the project root with: python3 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pal42.catalog import load_catalog

# A valid exercise.py, to write in a temporary exercises/ folder.
EXERCISE_SOURCE = """
from pal42.model import Exercise, Param
EXERCISE = Exercise(
	name="{name}", language="c", kind="program",
	expected_files=("{name}.c",), allowed_functions=("write",),
	themes=("char_sets",), params=(Param("mode", ("a", "b")),),
	subject="Do $mode.", oracle=None, generate_tests=None,
)
"""

def write_exercise(root, folder, source):
	"""Write `source` as exercise.py in root/folder (like "c/demo")."""
	path = root / folder
	path.mkdir(parents=True)
	(path / "exercise.py").write_text(source, encoding="utf-8")

class TestLoading(unittest.TestCase):
	"""Loading a made-up exercises/ folder, written in a temporary directory."""

	def setUp(self):
		"""Each test gets its own empty folder, removed after the test."""
		self.tmp = tempfile.TemporaryDirectory()
		self.root = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def test_folder_without_exercise_py_is_ignored_with_a_warning(self):
		"""A folder with no exercise.py is skipped, and a warning names it."""
		write_exercise(self.root, "c/demo", EXERCISE_SOURCE.format(name="demo"))
		(self.root / "c" / "empty").mkdir()
		catalog = load_catalog(self.root)
		self.assertEqual(list(catalog.exercises), ["demo"])
		self.assertEqual(len(catalog.warnings), 1)
		self.assertIn("c/empty", catalog.warnings[0])

	def test_broken_exercise_is_ignored_with_a_warning_that_says_why(self):
		"""An exercise refused by the model, or no EXERCISE: skipped, with why."""
		bad_hole = EXERCISE_SOURCE.format(name="bad").replace("$mode", "$order")
		write_exercise(self.root, "c/bad", bad_hole)
		write_exercise(self.root, "c/nothing", "x = 1\n")
		write_exercise(self.root, "c/demo", EXERCISE_SOURCE.format(name="demo"))
		catalog = load_catalog(self.root)
		self.assertEqual(list(catalog.exercises), ["demo"])
		self.assertEqual(len(catalog.warnings), 2)
		self.assertRegex(catalog.warnings[0], "c/bad.*unknown param")
		self.assertRegex(catalog.warnings[1], "c/nothing.*EXERCISE")

	def test_exercise_with_an_unknown_theme_is_ignored_with_a_warning(self):
		"""Each theme of an exercise must be in themes.json."""
		unknown = EXERCISE_SOURCE.format(name="lost").replace('"char_sets"', '"nope"')
		write_exercise(self.root, "c/lost", unknown)
		catalog = load_catalog(self.root)
		self.assertEqual(catalog.exercises, {})
		self.assertEqual(len(catalog.warnings), 1)
		self.assertRegex(catalog.warnings[0], "c/lost.*unknown theme.*nope")

	def test_two_exercises_with_the_same_name_keep_the_first(self):
		"""exo#seed must name one exercise: a second "same" is skipped."""
		write_exercise(self.root, "c/one", EXERCISE_SOURCE.format(name="same"))
		write_exercise(self.root, "c/two", EXERCISE_SOURCE.format(name="same"))
		catalog = load_catalog(self.root)
		self.assertEqual(list(catalog.exercises), ["same"])
		self.assertEqual(len(catalog.warnings), 1)
		self.assertRegex(catalog.warnings[0], "c/two.*same.*c/one")

class TestRealCatalog(unittest.TestCase):
	"""The catalog of the project itself, in exercises/."""

	def test_char_filter_is_found_under_its_theme(self):
		"""char_filter is a C exercise of the theme char_sets."""
		catalog = load_catalog()
		names = [exo.name for exo in catalog.find("c", "char_sets")]
		self.assertIn("char_filter", names)

	def test_real_catalog_has_no_warning(self):
		"""Every folder of exercises/ gives an exercise: none is skipped."""
		self.assertEqual(load_catalog().warnings, [])

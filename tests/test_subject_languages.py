"""The subject in the language chosen: the statement and the words of the variant translated.

The header stays in English, like the subjects of 42; Examples is
translated. An exercise without translation, or with a broken one, keeps
its English subject (docs/plans/languages.md).
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pal42.cli  # noqa: F401  (puts vendor/ in Python's path)
from pal42 import i18n, subject
from pal42.cli import display
from pal42.cli.workspace import Workspace
from tests.helpers import make_exercise
from pal42.model import Param
from pal42.variant import Variant

EXERCISE = make_exercise(
	name="char_filter", expected_files=("char_filter.c",),
	params=(Param("mode", ("common", "only_first"),
		{"common": "that appear in both strings", "only_first": "that appear only in the first string"}),),
	subject="Write a program that displays the characters $mode, in the order\nthey appear.",
)
VARIANT = Variant(EXERCISE, 0, {"mode": "common"})

FRENCH = {
	"subject": "Écrire un programme qui affiche les caractères $mode, dans l'ordre\noù ils apparaissent.",
	"texts": {"mode": {"common": "qui apparaissent dans les deux chaînes",
		"only_first": "qui apparaissent seulement dans la première chaîne"}},
}

def flat(text):
	"""The text on one line: the subjects are wrapped at 80 columns."""
	return " ".join(text.split())

def translated(table):
	"""subject.translation giving `table` in French, and nothing in the other languages."""
	return mock.patch.object(subject, "translation", lambda exo, code: table if code == "fr" else None)

class LanguageTestCase(unittest.TestCase):

	def setUp(self):
		self.addCleanup(i18n.set_language, "en")

class TestRender(LanguageTestCase):

	def test_english_is_unchanged(self):
		with translated(FRENCH):
			text = subject.render(VARIANT, "en")
		self.assertIn("Write a program that displays the characters that appear in both strings", flat(text))

	def test_the_statement_and_the_words_of_the_variant_in_french(self):
		i18n.set_language("fr")
		with translated(FRENCH):
			text = subject.render(VARIANT)
		self.assertIn("Écrire un programme qui affiche les caractères qui apparaissent dans les deux chaînes", flat(text))
		# The header of 42 stays in English.
		self.assertIn("Assignment name  : char_filter", text)
		self.assertIn("Expected files   : char_filter.c", text)

	def test_no_translation_keeps_the_english_subject(self):
		i18n.set_language("fr")
		with translated(None):
			self.assertIn("Write a program", subject.render(VARIANT))

	def test_a_broken_translation_keeps_the_english_subject(self):
		"""A $field the exercise does not have: English, never a crash."""
		i18n.set_language("fr")
		with translated({"subject": "Afficher $nope.", "texts": {}}):
			self.assertIn("Write a program", subject.render(VARIANT))

	def test_a_word_of_the_variant_not_translated_stays_in_english(self):
		i18n.set_language("fr")
		with translated({"subject": FRENCH["subject"], "texts": {}}):
			self.assertIn("caractères that appear in both strings", flat(subject.render(VARIANT)))

class TestWorkspace(LanguageTestCase):

	def test_the_subject_in_english_and_in_the_language_chosen(self):
		i18n.set_language("fr")
		with tempfile.TemporaryDirectory() as root, translated(FRENCH):
			workspace = Workspace(Path(root))
			given = workspace.give_subject(VARIANT)
			self.assertEqual(given.name, "subject.fr.txt")
			self.assertEqual(workspace.subject_file(VARIANT), given)
			self.assertIn("Écrire un programme", given.read_text(encoding="utf-8"))
			english = given.parent / "subject.en.txt"
			self.assertIn("Write a program", english.read_text(encoding="utf-8"))

	def test_in_english_only_the_english_subject(self):
		with tempfile.TemporaryDirectory() as root:
			given = Workspace(Path(root)).give_subject(VARIANT)
			self.assertEqual(given.name, "subject.en.txt")
			self.assertEqual([path.name for path in given.parent.glob("subject.*")], ["subject.en.txt"])

class TestDisplay(LanguageTestCase):

	def test_the_words_of_the_variant_stand_out_in_french(self):
		i18n.set_language("fr")
		with translated(FRENCH):
			text = subject.render(VARIANT)
			styled = display.subject_text(VARIANT, text)
		start = text.index("qui apparaissent")
		styles = [span for span in styled.spans if span.start <= start < span.end]
		self.assertTrue(styles, "the words of the variant are not styled")

class TestTheFrenchSubjectsOf42pal(LanguageTestCase):
	"""The real translations: every exercise of the catalog has its French subject, complete."""

	def test_every_exercise_has_a_complete_french_subject(self):
		from runpy import run_path
		tool = run_path(str(Path(__file__).resolve().parent.parent / "tools" / "locales.py"))
		self.assertEqual(tool["check_subjects"]("fr"), [])

class TestEveryFrenchSubjectRenders(LanguageTestCase):
	"""Each French subject fills with the words of each variant: no silent fall back to English."""

	def test_every_variant_renders_in_french(self):
		from pal42.catalog import load_catalog
		from pal42.reference import variants_to_check
		for exo in load_catalog().exercises.values():
			table = subject.translation(exo, "fr")
			self.assertIsNotNone(table, exo.name)
			for variant in variants_to_check(exo, max_variants=10):
				with self.subTest(variant=variant.id):
					# _statement, not statement: an error here must show, not give English.
					text = subject._statement(variant, table["subject"], "fr")
					self.assertNotIn("$", text.replace("$>", ""))

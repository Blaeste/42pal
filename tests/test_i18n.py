"""Tests of pal42.i18n and pal42.settings: the language of 42pal, and keeping it.

Run all the tests from the project root with: python3 -m unittest -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from pal42 import i18n, settings
from pal42.i18n import t

def write_catalog(folder, code, texts):
	"""A catalog of `code` in `folder`: {"_name": ..., English text: translation}."""
	(folder / f"{code}.json").write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")

class LocalesTestCase(unittest.TestCase):
	"""A folder of catalogs of its own; English again at the end."""

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)
		write_catalog(self.folder, "fr", {
			"_name": "Français",
			"Practice": "Entraînement",
			"Level {level} of {count}": "Niveau {level} sur {count}",
			"Grade {grade:g}/100": "Note {grade:g}/100",
			"Broken {field}": "Cassé {other}",
		})
		self.addCleanup(i18n.set_language, "en")

class TestTranslate(LocalesTestCase):

	def test_english_is_the_default_and_needs_no_catalog(self):
		self.assertEqual(i18n.language(), "en")
		self.assertEqual(t("Practice"), "Practice")
		self.assertEqual(t("Level {level} of {count}", level=2, count=4), "Level 2 of 4")

	def test_a_language_translates_and_fills_the_fields(self):
		self.assertEqual(i18n.set_language("fr", self.folder), "fr")
		self.assertEqual(t("Practice"), "Entraînement")
		self.assertEqual(t("Level {level} of {count}", level=2, count=4), "Niveau 2 sur 4")
		self.assertEqual(t("Grade {grade:g}/100", grade=12.5), "Note 12.5/100")

	def test_a_text_the_catalog_lacks_stays_in_english(self):
		i18n.set_language("fr", self.folder)
		self.assertEqual(t("Quit"), "Quit")

	def test_a_translation_with_wrong_fields_falls_back_to_english(self):
		"""A mistake in a catalog never breaks 42pal: the English text is shown."""
		i18n.set_language("fr", self.folder)
		self.assertEqual(t("Broken {field}", field="x"), "Broken x")

	def test_an_unknown_language_gives_english(self):
		self.assertEqual(i18n.set_language("xx", self.folder), "en")
		self.assertEqual(t("Practice"), "Practice")

	def test_a_text_without_fields_keeps_its_braces(self):
		self.assertEqual(t("int main(void) { return (0); }"), "int main(void) { return (0); }")

class TestLanguages(LocalesTestCase):

	def test_the_languages_are_english_then_each_catalog_by_code(self):
		write_catalog(self.folder, "de", {"_name": "Deutsch"})
		self.assertEqual(i18n.languages(self.folder), {"en": "English", "de": "Deutsch", "fr": "Français"})

	def test_adding_a_language_is_adding_its_file(self):
		"""No code to change: a new catalog is a new language."""
		write_catalog(self.folder, "pt", {"_name": "Português", "Practice": "Prática"})
		self.assertIn("pt", i18n.languages(self.folder))
		i18n.set_language("pt", self.folder)
		self.assertEqual(t("Practice"), "Prática")

	def test_a_broken_catalog_is_no_language(self):
		(self.folder / "zz.json").write_text("{ not json", encoding="utf-8")
		self.assertNotIn("zz", i18n.languages(self.folder))

	def test_the_catalogs_of_42pal_are_found(self):
		"""The real folder: English at least, and every catalog there has a name."""
		found = i18n.languages()
		self.assertEqual(next(iter(found)), "en")
		self.assertTrue(all(found.values()))

class TestSettings(LocalesTestCase):

	def setUp(self):
		super().setUp()
		self.file = self.folder / "settings.json"

	def test_nothing_saved_gives_english(self):
		self.assertEqual(settings.load(self.file), {})
		self.assertEqual(settings.apply_language({}, self.file, self.folder), "en")

	def test_the_language_saved_is_used_at_launch(self):
		settings.save({"language": "fr"}, self.file)
		self.assertEqual(settings.load(self.file), {"language": "fr"})
		self.assertEqual(settings.apply_language({}, self.file, self.folder), "fr")
		self.assertEqual(t("Practice"), "Entraînement")

	def test_pal42_lang_wins_over_the_file(self):
		settings.save({"language": "fr"}, self.file)
		self.assertEqual(settings.apply_language({"PAL42_LANG": "en"}, self.file, self.folder), "en")

	def test_choose_language_applies_and_keeps_it(self):
		self.assertEqual(settings.choose_language("fr", self.file, self.folder), "fr")
		self.assertEqual(i18n.language(), "fr")
		self.assertEqual(json.loads(self.file.read_text())["language"], "fr")

	def test_a_broken_settings_file_is_ignored(self):
		self.file.write_text("[1, 2", encoding="utf-8")
		self.assertEqual(settings.load(self.file), {})

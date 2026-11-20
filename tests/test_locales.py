"""Tests of tools/locales.py: the texts to translate, a new language, what is missing.

The last test runs check on every catalog of pal42/locales: a text added
to the code without its translation fails here.
"""

import json
import tempfile
import unittest
from pathlib import Path
from runpy import run_path

from pal42 import i18n

ROOT = Path(__file__).resolve().parent.parent
TOOL = run_path(str(ROOT / "tools" / "locales.py"))

CODE = '''
from pal42 import i18n
from pal42.i18n import t

def menu(level, name):
	print(t("Practice"))
	print(i18n.t("Level {level} of {count}", level=level, count=4))
	print(t(name))
	print(t("int main(void) { return (0); }"))
'''

class TestLocalesTool(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.code = Path(folder.name) / "code"
		self.code.mkdir()
		(self.code / "menu.py").write_text(CODE, encoding="utf-8")
		self.locales = Path(folder.name) / "locales"
		self.locales.mkdir()

	def write(self, code, data):
		(self.locales / f"{code}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

	def test_extract_finds_the_texts_written_in_t(self):
		"""The strings written as they are; t(name) has no text to translate."""
		self.assertEqual(TOOL["extract"](self.code),
			["Level {level} of {count}", "Practice", "int main(void) { return (0); }"])

	def test_check_says_what_is_missing_wrong_or_unused(self):
		self.write("fr", {
			"_name": "Français",
			"Practice": "Entraînement",
			"Level {level} of {count}": "Niveau {niveau} sur {count}",
			"Old text": "Vieux texte",
		})
		problems = TOOL["check"]("fr", TOOL["extract"](self.code), self.locales)
		self.assertEqual(sorted(problems), [
			("fields", "Level {level} of {count}"),
			("missing", "int main(void) { return (0); }"),
			("unused", "Old text"),
		])

	def test_a_catalog_needs_its_name(self):
		self.write("fr", {"Practice": "Entraînement"})
		self.assertIn(("name", "_name"), TOOL["check"]("fr", ["Practice"], self.locales))

	def test_new_makes_the_skeleton_of_a_language_then_keeps_what_is_done(self):
		texts = TOOL["extract"](self.code)
		TOOL["new"]("pt", "Português", texts, self.locales)
		data = json.loads((self.locales / "pt.json").read_text(encoding="utf-8"))
		self.assertEqual(list(data)[0], "_name")
		self.assertEqual(data["_name"], "Português")
		self.assertEqual({key for key in data if key != "_name"}, set(texts))
		self.assertTrue(all(value == "" for key, value in data.items() if key != "_name"))
		# Translated, then new run: what is done stays.
		data["Practice"] = "Prática"
		(self.locales / "pt.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
		TOOL["new"]("pt", "Português", texts, self.locales)
		self.assertEqual(json.loads((self.locales / "pt.json").read_text(encoding="utf-8"))["Practice"], "Prática")

	def test_the_language_made_by_new_is_in_the_menu(self):
		TOOL["new"]("pt", "Português", ["Practice"], self.locales)
		self.assertEqual(i18n.languages(self.locales)["pt"], "Português")

	def test_main_check_gives_exit_code_1_when_something_is_missing(self):
		self.write("fr", {"_name": "Français"})
		self.assertEqual(TOOL["main"](["check", "fr"], code=self.code, locales=self.locales), 1)
		self.write("fr", {"_name": "Français", "Practice": "a", "Level {level} of {count}": "b {level} {count}",
			"int main(void) { return (0); }": "c"})
		self.assertEqual(TOOL["main"](["check", "fr"], code=self.code, locales=self.locales), 0)

class TestTheCatalogsOf42pal(unittest.TestCase):
	"""Every catalog of pal42/locales has every text of the code, with the right fields."""

	def test_every_catalog_is_complete(self):
		texts = TOOL["extract"]()
		for code in i18n.languages():
			if code == i18n.DEFAULT:
				continue
			with self.subTest(language=code):
				self.assertEqual(TOOL["check"](code, texts), [])

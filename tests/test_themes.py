"""Tests of pal42.themes: the list of themes, in themes.json.

Run all the tests from the project root with: python3 -m unittest -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from pal42.themes import ThemesError, load_themes

class TestRealThemes(unittest.TestCase):
	"""The themes.json of the project itself."""

	def test_char_sets_appears_in_rank02_level_2(self):
		"""Each theme says which skill it trains and where it appears."""
		themes = load_themes()
		self.assertIn(2, themes["char_sets"].exams["rank02"])
		self.assertTrue(themes["char_sets"].skill)

class TestBadThemesFile(unittest.TestCase):
	"""A themes.json written by hand, with mistakes in it."""

	def setUp(self):
		"""Each test gets its own empty folder, removed after the test."""
		self.tmp = tempfile.TemporaryDirectory()
		self.path = Path(self.tmp.name) / "themes.json"

	def tearDown(self):
		self.tmp.cleanup()

	def test_badly_written_theme_raises_an_error_naming_it(self):
		"""No skill, no exam, no level, or a level that is not a number."""
		bad = {
			"no_skill": {"exams": {"rank02": [2]}},
			"no_exam": {"skill": "Do things", "exams": {}},
			"no_level": {"skill": "Do things", "exams": {"rank02": []}},
			"text_level": {"skill": "Do things", "exams": {"rank02": ["2"]}},
		}
		for theme_id, entry in bad.items():
			# subTest: each case is reported on its own if it fails.
			with self.subTest(theme_id):
				self.path.write_text(json.dumps({theme_id: entry}), encoding="utf-8")
				with self.assertRaisesRegex(ThemesError, theme_id):
					load_themes(self.path)

	def test_theme_written_twice_raises_an_error(self):
		"""json would silently keep only the last one: refuse it instead."""
		self.path.write_text(
			'{"words": {"skill": "A", "exams": {"rank02": [1]}},\n'
			' "words": {"skill": "B", "exams": {"rank02": [2]}}}',
			encoding="utf-8",
		)
		with self.assertRaisesRegex(ThemesError, "words.*deux fois"):
			load_themes(self.path)

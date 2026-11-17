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
		"""No skill, no exam, no level, or a level that is not a number from 1."""
		bad = {
			"no_skill": {"exams": {"rank02": [2]}},
			"no_exam": {"skill": "Do things", "exams": {}},
			"no_level": {"skill": "Do things", "exams": {"rank02": []}},
			"text_level": {"skill": "Do things", "exams": {"rank02": ["2"]}},
			"zero_level": {"skill": "Do things", "exams": {"rank02": [0, 1]}},
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
		with self.assertRaisesRegex(ThemesError, "words.*twice"):
			load_themes(self.path)

# The real subjects of each level of each exam, read in the folders of
# 42_EXAM (names only: no real subject is in this repository). piscine_01
# to piscine_final are its exam_01 to exam_04, rank02 its exam_02 of the
# cursus.
REAL_LEVELS = {
	"piscine_01": {
		1: "aff_a ft_countdown ft_print_numbers",
		2: "hello maff_alpha",
		3: "aff_first_param aff_last_param aff_z",
		4: "maff_revalpha only_a only_z",
		5: "ft_strcpy ft_strlen",
		6: "repeat_alpha search_and_replace ulstr",
		7: "first_word ft_putstr ft_swap",
		8: "rev_print rot_13 rotone",
	},
	"piscine_02": {
		1: "ft_strcpy ft_strlen repeat_alpha",
		2: "search_and_replace ulstr",
		3: "first_word ft_putstr ft_swap",
		4: "rev_print rot_13 rotone",
		5: "ft_atoi ft_strdup inter",
		6: "last_word reverse_bits swap_bits union",
		7: "alpha_mirror do_op ft_strcmp ft_strrev",
		8: "is_power_of_2 max print_bits wdmatch",
	},
	"piscine_03": {
		1: "ft_atoi ft_strdup inter last_word reverse_bits swap_bits union",
		2: "alpha_mirror do_op ft_strcmp ft_strrev is_power_of_2 max print_bits wdmatch",
		3: "add_prime_sum epur_str ft_list_size ft_rrange hidenp pgcd print_hex rstr_capitalizer",
		4: "expand_str ft_atoi_base ft_range lcm paramsum str_capitalizer tab_mult",
	},
	"piscine_final": {
		1: "add_prime_sum epur_str ft_list_size ft_rrange hidenp pgcd print_hex rstr_capitalizer",
		2: "expand_str ft_atoi_base ft_range lcm paramsum str_capitalizer tab_mult",
		3: "brainfuck check_mate flood_fill fprime ft_itoa ft_itoa_base ft_list_foreach "
			"ft_list_remove_if ft_split rev_wstr rostring sort_int_tab sort_list",
		4: "biggest_pal brackets cycle_detector options print_memory rpn_calc",
	},
	"rank02": {
		1: "first_word fizzbuzz ft_putstr ft_strcpy ft_strlen ft_swap repeat_alpha rev_print "
			"rot_13 rotone search_and_replace ulstr",
		2: "alpha_mirror camel_to_snake do_op ft_atoi ft_strcmp ft_strcspn ft_strdup inter "
			"is_power_of_2 last_word max print_bits snake_to_camel swap_bits union",
		3: "add_prime_sum epur_str expand_str ft_atoi_base ft_list_size ft_range ft_rrange hidenp "
			"lcm paramsum pgcd print_hex rstr_capitalizer str_capitalizer tab_mult",
		4: "flood_fill fprime ft_itoa ft_split rev_wstr rostring sort_list",
	},
}

# The theme of each real subject. A theme groups real subjects of the same
# skill and about the same difficulty: each of its exercises can be drawn at
# each of its levels.
THEME_OF = {
	"print_basics": "aff_a ft_countdown ft_print_numbers hello maff_alpha aff_z maff_revalpha "
		"only_a only_z",
	"program_args": "aff_first_param aff_last_param paramsum",
	"option_flags": "options",
	"string_basics": "ft_strcpy ft_strlen ft_putstr rev_print ft_strcmp ft_strrev ft_strcspn",
	"pointers": "ft_swap",
	"char_transform": "repeat_alpha search_and_replace ulstr rot_13 rotone alpha_mirror",
	"words": "first_word last_word",
	"clean_words": "epur_str expand_str",
	"reorder_words": "rev_wstr rostring",
	"case_style": "camel_to_snake snake_to_camel rstr_capitalizer str_capitalizer",
	"char_sets": "inter union wdmatch hidenp",
	"number_parse": "ft_atoi",
	"base_parse": "ft_atoi_base",
	"number_print": "fizzbuzz",
	"print_in_base": "print_hex",
	"number_string": "ft_itoa ft_itoa_base",
	"arithmetic": "do_op tab_mult",
	"primes": "add_prime_sum pgcd lcm fprime",
	"bits": "reverse_bits swap_bits print_bits is_power_of_2",
	"allocation": "ft_strdup",
	"int_ranges": "ft_range ft_rrange",
	"split": "ft_split",
	"int_arrays": "max",
	"int_sort": "sort_int_tab",
	"linked_lists": "ft_list_size",
	"list_changes": "ft_list_foreach ft_list_remove_if sort_list cycle_detector",
	"grids": "flood_fill check_mate",
	"stack_parsing": "brackets rpn_calc",
	"interpreters": "brainfuck",
	"memory_dump": "print_memory",
	"string_search": "biggest_pal",
}

class TestRealLevels(unittest.TestCase):
	"""themes.json follows the levels of the real subjects of 42_EXAM."""

	def test_every_real_subject_has_one_theme(self):
		"""No real subject forgotten, none in two themes."""
		themed = [name for names in THEME_OF.values() for name in names.split()]
		self.assertEqual(len(themed), len(set(themed)))
		real = {name for levels in REAL_LEVELS.values() for names in levels.values()
			for name in names.split()}
		self.assertEqual(real, set(themed))

	def test_the_levels_of_each_theme_are_the_levels_of_its_real_subjects(self):
		"""Each theme is at the levels where its real subjects are, and nowhere else."""
		theme_of = {name: theme for theme, names in THEME_OF.items() for name in names.split()}
		expected = {theme: {} for theme in THEME_OF}
		for exam_id, levels in REAL_LEVELS.items():
			for level, names in levels.items():
				for name in names.split():
					expected[theme_of[name]].setdefault(exam_id, set()).add(level)
		themes = load_themes()
		self.assertEqual(set(themes), set(THEME_OF))
		for theme_id, theme in themes.items():
			actual = {exam_id: set(levels) for exam_id, levels in theme.exams.items()}
			self.assertEqual(actual, expected[theme_id], theme_id)

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

	def test_common_chars_appears_in_rank02_level_2(self):
		"""Each theme says which skill it trains and where it appears."""
		themes = load_themes()
		self.assertIn(2, themes["common_chars"].exams["rank02"])
		self.assertTrue(themes["common_chars"].skill)

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

# The theme of each real subject: one theme per real subject, named after its
# style, never after the subject. Each level draws a theme, then one of its
# exercises, like the real exam draws one of the subjects of the level.
THEME_OF = {
	"letter_search": "aff_a",
	"letter_or_fallback": "aff_z",
	"digit_countdown": "ft_countdown",
	"print_digits": "ft_print_numbers",
	"fixed_message": "hello",
	"alternating_alphabet": "maff_alpha",
	"backward_alphabet": "maff_revalpha",
	"one_char": "only_a",
	"one_char_end": "only_z",
	"pick_argument": "aff_first_param",
	"last_argument": "aff_last_param",
	"argument_count": "paramsum",
	"option_flags": "options",
	"string_copy": "ft_strcpy",
	"string_length": "ft_strlen",
	"string_print": "ft_putstr",
	"reverse_print": "rev_print",
	"string_compare": "ft_strcmp",
	"string_reverse": "ft_strrev",
	"char_span": "ft_strcspn",
	"value_swap": "ft_swap",
	"letter_repeat": "repeat_alpha",
	"char_replace": "search_and_replace",
	"case_swap": "ulstr",
	"letter_rotation": "rot_13",
	"letter_step": "rotone",
	"alphabet_mirror": "alpha_mirror",
	"find_word": "first_word",
	"end_word": "last_word",
	"space_cleanup": "epur_str",
	"space_spread": "expand_str",
	"word_reverse": "rev_wstr",
	"word_rotate": "rostring",
	"case_convert": "camel_to_snake",
	"case_convert_back": "snake_to_camel",
	"capitalize_last": "rstr_capitalizer",
	"capitalize_first": "str_capitalizer",
	"common_chars": "inter",
	"merged_chars": "union",
	"hidden_word": "wdmatch",
	"hidden_order": "hidenp",
	"read_number": "ft_atoi",
	"read_base_number": "ft_atoi_base",
	"number_words": "fizzbuzz",
	"print_in_base": "print_hex",
	"number_to_string": "ft_itoa",
	"base_to_string": "ft_itoa_base",
	"calculator": "do_op",
	"number_table": "tab_mult",
	"prime_sum": "add_prime_sum",
	"common_divisor": "pgcd",
	"common_multiple": "lcm",
	"prime_factors": "fprime",
	"bit_reverse": "reverse_bits",
	"bit_rotate": "swap_bits",
	"bit_print": "print_bits",
	"bit_test": "is_power_of_2",
	"string_dup": "ft_strdup",
	"int_range": "ft_range",
	"int_range_back": "ft_rrange",
	"string_split": "ft_split",
	"array_search": "max",
	"array_sort": "sort_int_tab",
	"list_walk": "ft_list_size",
	"list_apply": "ft_list_foreach",
	"list_remove": "ft_list_remove_if",
	"list_sort": "sort_list",
	"list_cycle": "cycle_detector",
	"grid_fill": "flood_fill",
	"grid_attack": "check_mate",
	"bracket_check": "brackets",
	"postfix_calc": "rpn_calc",
	"tiny_interpreter": "brainfuck",
	"memory_dump": "print_memory",
	"longest_part": "biggest_pal",
}

class TestRealLevels(unittest.TestCase):
	"""themes.json follows the levels of the real subjects of 42_EXAM."""

	def test_each_theme_is_the_style_of_one_real_subject(self):
		"""One real subject per theme: a level offers as many styles as real subjects."""
		for theme, names in THEME_OF.items():
			self.assertEqual(len(names.split()), 1, theme)
			self.assertNotIn(theme, names.split())

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

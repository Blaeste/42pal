"""Tests of the second models of the styles of Exam Rank 02, level 1.

Each test calls the oracle of a variant on values chosen by hand; the
expected outputs are worked out by hand, never by the oracle.

Run all the tests from the project root with: python3 -m unittest -v
"""

import unittest
from pathlib import Path
from runpy import run_path

from pal42.model import TestCase
from pal42.subject import render
from pal42.variant import Variant

EXERCISES = Path(__file__).resolve().parent.parent / "exercises/c"
NAMES = ("triple_swap", "len_kinds", "put_shape", "copy_part", "case_zone", "replace_count", "shift_words",
	"step_marks")
LOADED = {name: run_path(str(EXERCISES / name / "exercise.py"))["EXERCISE"] for name in NAMES}

def out(name, params, *args):
	return LOADED[name].oracle(params, TestCase(tuple(args)))

class TestTripleSwap(unittest.TestCase):
	def test_each_way(self):
		self.assertEqual(out("triple_swap", {"how": "turn_left"}, "1", "2", "3"), "2 3 1\n")
		self.assertEqual(out("triple_swap", {"how": "turn_right"}, "1", "2", "3"), "3 1 2\n")
		self.assertEqual(out("triple_swap", {"how": "sort_up"}, "3", "-1", "2"), "-1 2 3\n")
		self.assertEqual(out("triple_swap", {"how": "sort_down"}, "3", "-1", "2"), "3 2 -1\n")
		self.assertEqual(out("triple_swap", {"how": "sort_up"}, "5", "5", "0"), "0 5 5\n")

class TestLenKinds(unittest.TestCase):
	def test_each_length(self):
		text = "  hello big world "
		self.assertEqual(out("len_kinds", {"what": "words"}, text), "3\n")
		self.assertEqual(out("len_kinds", {"what": "longest_word"}, text), "5\n")
		self.assertEqual(out("len_kinds", {"what": "no_spaces"}, text), "13\n")
		self.assertEqual(out("len_kinds", {"what": "until_digit"}, text), "18\n")
		self.assertEqual(out("len_kinds", {"what": "until_digit"}, "ab3cd"), "2\n")
		for what in ("words", "longest_word", "no_spaces", "until_digit"):
			self.assertEqual(out("len_kinds", {"what": what}, ""), "0\n")

class TestPutShape(unittest.TestCase):
	def test_each_shape(self):
		self.assertEqual(out("put_shape", {"how": "spaced"}, "abc"), "a b c\n")
		self.assertEqual(out("put_shape", {"how": "spaced"}, ""), "\n")
		self.assertEqual(out("put_shape", {"how": "framed"}, "abc"), "[abc]\n")
		self.assertEqual(out("put_shape", {"how": "words_lines"}, "  hi \tthere "), "hi\nthere\n")
		self.assertEqual(out("put_shape", {"how": "words_lines"}, "   "), "")

class TestCopyPart(unittest.TestCase):
	def test_each_part(self):
		self.assertEqual(out("copy_part", {"how": "first_n"}, "hello", "2"), "he\n")
		self.assertEqual(out("copy_part", {"how": "last_n"}, "hello", "2"), "lo\n")
		self.assertEqual(out("copy_part", {"how": "from_n"}, "hello", "2"), "llo\n")
		self.assertEqual(out("copy_part", {"how": "first_n"}, "hello", "9"), "hello\n")
		self.assertEqual(out("copy_part", {"how": "last_n"}, "hello", "9"), "hello\n")
		self.assertEqual(out("copy_part", {"how": "from_n"}, "hello", "9"), "\n")
		self.assertEqual(out("copy_part", {"how": "last_n"}, "hello", "0"), "\n")

class TestCaseZone(unittest.TestCase):
	def test_each_zone(self):
		self.assertEqual(out("case_zone", {"zone": "first_half"}, "Hello World"), "hELLO World\n")
		self.assertEqual(out("case_zone", {"zone": "odd_words"}, "one Two three FOUR"), "ONE Two THREE FOUR\n")
		self.assertEqual(out("case_zone", {"zone": "after_digit"}, "a1b2Cd"), "a1B2cd\n")
		self.assertEqual(out("case_zone", {"zone": "in_brackets"}, "ab(cD)Ef(g"), "ab(Cd)Ef(G\n")

class TestReplaceCount(unittest.TestCase):
	def test_each_place(self):
		self.assertEqual(out("replace_count", {"where": "word_start"}, "banana band", "b", "B"), "2 Banana Band\n")
		self.assertEqual(out("replace_count", {"where": "word_end"}, "banana band", "a", "A"), "1 bananA band\n")
		self.assertEqual(out("replace_count", {"where": "in_runs"}, "aabaaa x a", "a", "-"), "5 --b--- x a\n")
		self.assertEqual(out("replace_count", {"where": "inside"}, "aaa", "a", "b"), "1 aba\n")
		self.assertEqual(out("replace_count", {"where": "inside"}, "aXa", "a", "b"), "0 aXa\n")

class TestShiftWords(unittest.TestCase):
	def test_each_shift(self):
		self.assertEqual(out("shift_words", {"by": "word_rank"}, "ab yz Az"), "bc ab Dc\n")
		self.assertEqual(out("shift_words", {"by": "position"}, "abc a"), "bdf e\n")
		self.assertEqual(out("shift_words", {"by": "word_length"}, "hi abc"), "jk def\n")
		self.assertEqual(out("shift_words", {"by": "word_length"}, "a1 Z"), "c1 A\n")

class TestStepMarks(unittest.TestCase):
	def test_each_mark(self):
		self.assertEqual(out("step_marks", {"where": "word_starts"}, "abc zed Yo 1x"), "bbc aed Zo 1x\n")
		self.assertEqual(out("step_marks", {"where": "word_ends"}, "abc zed Yo x1"), "abd zee Yp x1\n")
		self.assertEqual(out("step_marks", {"where": "capitals"}, "Az Zz yY"), "Bz Az yZ\n")

class TestSubjects(unittest.TestCase):
	def test_every_variant_renders_within_80_columns(self):
		for name, exercise in LOADED.items():
			for params in exercise.combinations():
				for line in render(Variant(exercise, 0, params)).splitlines():
					self.assertLessEqual(len(line.expandtabs(4)), 80, f"{name} {params}: {line}")

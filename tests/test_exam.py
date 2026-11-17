"""Tests of pal42.exam: the exams, their levels and the draw of a subject.

Run all the tests from the project root with: python3 -m unittest -v
"""

import json
import tempfile
import unittest
from pathlib import Path
from random import Random

from pal42.catalog import Catalog
from pal42.exam import ExamError, list_exams, load_exam
from pal42.retry import RetryPolicy
from pal42.themes import Theme
from tests.helpers import make_exercise

class TestRealExams(unittest.TestCase):
	"""The exams of the project itself, in exams/."""

	def test_rank02_has_4_levels_and_char_filter_at_level_2(self):
		"""The levels take their themes from themes.json, then their exercises."""
		exam = load_exam("rank02")
		self.assertEqual(exam.title, "Exam Rank 02")
		self.assertEqual(exam.level_count, 4)
		self.assertIn("char_filter", [exo.name for exo in exam.exercises_at(2)])

	def test_the_four_piscine_exams_follow_42_exam(self):
		"""Like 42_EXAM: weeks 01 and 02 have 8 levels, week 03 and the final 4."""
		shape = {exam_id: (load_exam(exam_id).level_count, load_exam(exam_id).duration_minutes)
			for exam_id in ["piscine_01", "piscine_02", "piscine_03", "piscine_final"]}
		self.assertEqual(shape, {
			"piscine_01": (8, 240), "piscine_02": (8, 240),
			"piscine_03": (4, 240), "piscine_final": (4, 480),
		})
		self.assertEqual(load_exam("piscine_01").points_per_level, 12.5)

	def test_each_level_is_worth_100_divided_by_the_number_of_levels(self):
		"""Like 42_EXAM: 4 levels give 25 points each, 8 levels 12.5."""
		self.assertEqual(load_exam("rank02").points_per_level, 25)

	def test_every_level_of_piscine_01_can_be_played(self):
		"""print_range (levels 1 to 4) and arg_pick (level 3) fill piscine 01."""
		self.assertEqual(load_exam("piscine_01").playable_levels, list(range(1, 9)))

	def test_every_level_of_rank02_can_be_played(self):
		"""split_fields fills level 4: the whole exam can be played."""
		self.assertEqual(load_exam("rank02").playable_levels, [1, 2, 3, 4])

	def test_retry_waits_come_from_the_exam_file(self):
		"""soft and hard: the waits after each failed grademe, in minutes."""
		exam = load_exam("rank02")
		self.assertEqual(exam.retry["soft"], RetryPolicy((0, 1, 2, 3, 5)))
		# hard is 42_EXAM's own: a Fibonacci-like list, from half a minute.
		self.assertEqual(exam.retry["hard"], RetryPolicy((0.5, 2.5, 3, 5.5, 8.5, 14, 22.5, 36.5, 59)))

	def test_every_exam_file_loads(self):
		"""Each file of exams/ is a valid exam with at least one playable level."""
		self.assertEqual(list_exams(), ["piscine_01", "piscine_02", "piscine_03", "piscine_final", "rank02"])
		for exam_id in list_exams():
			with self.subTest(exam_id):
				self.assertTrue(load_exam(exam_id).playable_levels)


class TestLevels(unittest.TestCase):
	"""The levels of an exam, with made-up themes and a made-up catalog."""

	def setUp(self):
		"""One exercise, of a theme that appears at rank02 levels 2 and 3 only."""
		self.themes = {
			"char_sets": Theme("char_sets", "Compare characters", {"rank02": (2, 3)}),
			"words": Theme("words", "Find words", {"rank02": (1,)}),
		}
		self.catalog = Catalog({"char_filter": make_exercise()}, [])

	def test_level_without_exercise_gives_a_warning_and_is_not_playable(self):
		"""Level 1 has a theme but no exercise, level 4 has no theme at all."""
		exam = load_exam("rank02", catalog=self.catalog, themes=self.themes)
		self.assertEqual(exam.playable_levels, [2, 3])
		self.assertEqual(len(exam.warnings), 2)
		self.assertRegex(exam.warnings[0], "level 1.*no exercise")
		self.assertRegex(exam.warnings[1], "level 4.*no exercise")

	def test_draw_gives_a_variant_of_an_exercise_of_the_level(self):
		"""A theme of the level, then a model of it, then a seed: reproducible."""
		exam = load_exam("rank02", catalog=self.catalog, themes=self.themes)
		variant = exam.draw(2, Random(42))
		self.assertEqual(variant.exercise.name, "char_filter")
		self.assertEqual(variant.id, exam.draw(2, Random(42)).id)

class TestBadExamFile(unittest.TestCase):
	"""Exam files written by hand, with mistakes in them."""

	def setUp(self):
		"""Each test gets its own exams/ folder, removed after the test."""
		self.tmp = tempfile.TemporaryDirectory()
		self.dir = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def load(self, data):
		"""Write `data` as exams/demo.json, then load the exam "demo"."""
		(self.dir / "demo.json").write_text(json.dumps(data), encoding="utf-8")
		return load_exam("demo", exams_dir=self.dir, catalog=Catalog({}, []), themes={})

	def test_unknown_exam_gives_an_error_listing_the_exams(self):
		"""An exam that has no file: the error gives the ones that exist."""
		(self.dir / "rank02.json").write_text("{}", encoding="utf-8")
		with self.assertRaisesRegex(ExamError, "rank99.*rank02"):
			load_exam("rank99", exams_dir=self.dir, catalog=Catalog({}, []), themes={})

	def test_badly_written_exam_gives_an_error_naming_the_field(self):
		"""A missing field, a count that is not a positive integer, no command."""
		good = {"title": "Demo", "language": "c", "levels": 4,
			"duration_minutes": 180, "compile": ["cc"]}
		cases = {
			"title": {key: value for key, value in good.items() if key != "title"},
			"levels": dict(good, levels=0),
			"duration_minutes": dict(good, duration_minutes="3h"),
			"compile": dict(good, compile=[]),
			"retry_minutes": dict(good, retry_minutes={"soft": [0, -1], "hard": [0]}),
		}
		for field, data in cases.items():
			with self.subTest(field):
				with self.assertRaisesRegex(ExamError, f"demo.json.*{field}"):
					self.load(data)

"""The exams: their settings in exams/<id>.json, and their levels.

The themes of a level come from themes.json, and the exercises of a theme
from the catalog. Like the rest of the core, this module never prints.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from pal42.catalog import load_catalog
from pal42.themes import load_themes
# Renamed here: Exam has its own draw(), for a whole level.
from pal42.variant import draw as draw_variant

# exams/ is at the root of the project, next to exercises/.
EXAMS_DIR = Path(__file__).resolve().parent.parent / "exams"

class ExamError(ValueError):
	"""An exam file is missing or badly written; the message says why."""

@dataclass(frozen=True)
class Exam:
	"""An exam: its settings, and the exercises of each level by theme.

	levels maps a level number to {theme id: exercises of that theme}, with
	only the themes that have exercises. warnings name the levels that have
	none yet; the front-ends show them.
	"""
	id: str
	title: str
	language: str
	level_count: int
	duration_minutes: int
	compile_command: tuple[str, ...]
	levels: dict
	warnings: list

	@property
	def playable_levels(self):
		"""The levels that have at least one exercise, in order."""
		return [level for level, themes in sorted(self.levels.items()) if themes]

	def exercises_at(self, level):
		"""Return the exercises that can be drawn at `level`."""
		return [exo for exercises in self.levels[level].values() for exo in exercises]

	def draw(self, level, rng):
		"""Draw a subject at `level`: a theme, then a model of it, then a seed.

		The theme comes first, so that each theme has the same chance, however
		many models it has. rng is a random.Random: the same one gives the same
		subject.
		"""
		# sorted: the same order on every machine, so the same draws.
		theme = rng.choice(sorted(self.levels[level]))
		exo = rng.choice(self.levels[level][theme])
		return draw_variant(exo, rng.randrange(2**31))

def load_exam(exam_id, exams_dir=EXAMS_DIR, catalog=None, themes=None):
	"""Load exams/<exam_id>.json and find the exercises of each level."""
	if themes is None:
		themes = load_themes()
	if catalog is None:
		catalog = load_catalog(themes=themes)
	path = exams_dir / f"{exam_id}.json"
	if not path.exists():
		raise ExamError(f"exam inconnu « {exam_id} », choix : {', '.join(list_exams(exams_dir))}")
	data = _read_exam_file(path)
	levels = {}
	for level in range(1, data["levels"] + 1):
		levels[level] = {}
		for theme in themes.values():
			if level in theme.exams.get(exam_id, ()):
				exercises = tuple(catalog.find(data["language"], theme.id))
				if exercises:
					levels[level][theme.id] = exercises
	warnings = [
		f"{data['title']}, niveau {level} : aucun exo pour l'instant, niveau pas jouable"
		for level, found in levels.items() if not found
	]
	return Exam(
		exam_id, data["title"], data["language"], data["levels"],
		data["duration_minutes"], tuple(data["compile"]), levels, warnings,
	)

def list_exams(exams_dir=EXAMS_DIR):
	"""Return the ids of the exams that have a file in `exams_dir`, sorted."""
	return sorted(path.stem for path in exams_dir.glob("*.json"))

def _read_exam_file(path):
	"""Read an exam file and check its fields; raise ExamError if one is wrong."""
	def fail(reason):
		raise ExamError(f"{path.name} : {reason}")

	data = json.loads(path.read_text(encoding="utf-8"))
	for field in ("title", "language", "levels", "duration_minutes", "compile"):
		if field not in data:
			fail(f"il manque le champ « {field} »")
	for field in ("levels", "duration_minutes"):
		value = data[field]
		# bool is a kind of int in Python (True == 1): refuse it too.
		if isinstance(value, bool) or not isinstance(value, int) or value < 1:
			fail(f"« {field} » doit être un nombre entier positif, pas {value!r}")
	if not data["compile"]:
		fail("« compile » est vide : il faut au moins le nom du compilateur")
	return data

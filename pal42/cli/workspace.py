"""~/42pal_exam/: the folders the student works in, like at the exam.

subjects/<name>/subject.en.txt holds the subject, rendu/<name>/ is where
the student writes the code, and traces/ gets a trace for each failed
grademe. The student's work is never deleted.
"""

from pathlib import Path

from pal42.subject import render

# Not ~/42pal: that is often where the repository itself was cloned.
DEFAULT_ROOT = Path.home() / "42pal_exam"

class Workspace:
	"""The exam folders, under `root` (~/42pal_exam by default)."""

	def __init__(self, root=DEFAULT_ROOT):
		self.root = Path(root)
		self.subjects = self.root / "subjects"
		self.rendu = self.root / "rendu"
		self.traces = self.root / "traces"

	def give_subject(self, variant):
		"""Write the subject of `variant`, prepare its rendu folder, return the subject.

		exist_ok: folders already there are kept as they are, with the
		student's files in them.
		"""
		for folder in (self.subjects, self.rendu, self.traces):
			folder.mkdir(parents=True, exist_ok=True)
		subject = self.subjects / variant.name / "subject.en.txt"
		subject.parent.mkdir(exist_ok=True)
		subject.write_text(render(variant), encoding="utf-8")
		(self.rendu / variant.name).mkdir(exist_ok=True)
		return subject

	def write_trace(self, attempt, name, text):
		"""Write the log of grademe number `attempt` in traces/ and return its path.

		Named like 01_<name>.trace, so that the logs sort in order.
		"""
		self.traces.mkdir(parents=True, exist_ok=True)
		log = self.traces / f"{attempt:02d}_{name}.trace"
		log.write_text(text, encoding="utf-8")
		return log

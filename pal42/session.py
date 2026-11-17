"""The exam in progress and the history of the finished ones, in ~/.42pal/.

session.json holds what is needed to resume an exam after the terminal was
closed; history.json lists the finished exams, the base of a future score.
Like the rest of the core, this module never prints.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Hidden, apart from ~/42pal_exam/ which holds what the student works on.
STATE_DIR = Path.home() / ".42pal"

@dataclass
class Session:
	"""An exam in progress, as saved in session.json.

	variant is the subject as exo#seed, enough to draw it again. Times are
	seconds since 1970 (time.time()), so that they still make sense after
	the terminal was closed and opened again.
	"""
	exam: str
	level: int
	variant: str
	started_at: float
	retry_mode: str
	attempts: int
	oks: int
	failures: int
	passed_levels: list = field(default_factory=list)
	next_grademe_at: float | None = None
	warned: bool = False

class SessionStore:
	"""session.json and history.json, in `folder` (~/.42pal by default)."""

	def __init__(self, folder=STATE_DIR):
		self.folder = Path(folder)
		self.session_file = self.folder / "session.json"
		self.history_file = self.folder / "history.json"

	def save(self, session):
		"""Write `session`, replacing the one saved before."""
		self.folder.mkdir(parents=True, exist_ok=True)
		self.session_file.write_text(json.dumps(asdict(session), indent="\t"), encoding="utf-8")

	def load(self):
		"""Return the saved session, or None if there is none or it is broken.

		A broken file (cut in the middle, written by hand...) must not stop
		the student from starting a new exam.
		"""
		try:
			return Session(**json.loads(self.session_file.read_text(encoding="utf-8")))
		except (OSError, ValueError, TypeError):
			return None

	def clear(self):
		"""Remove the saved session: there is no exam to resume any more."""
		self.session_file.unlink(missing_ok=True)

	def history(self):
		"""Return the finished exams, oldest first ([] if none, or if broken)."""
		try:
			entries = json.loads(self.history_file.read_text(encoding="utf-8"))
		except (OSError, ValueError):
			return []
		return entries if isinstance(entries, list) else []

	def add_history(self, entry):
		"""Add a finished exam (a dict) at the end of the history."""
		self.folder.mkdir(parents=True, exist_ok=True)
		entries = self.history() + [entry]
		self.history_file.write_text(json.dumps(entries, indent="\t"), encoding="utf-8")

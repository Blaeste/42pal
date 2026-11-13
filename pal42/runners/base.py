"""What all the runners share, whatever the language."""

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class CompileResult:
	"""The result of a compilation.

	ok tells whether it worked, output is what the compiler printed (errors
	and warnings), and binary is the program built, or None if it failed.
	"""
	ok: bool
	output: str
	binary: Path | None

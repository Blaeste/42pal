"""Tests of pal42.cli: the terminal front-end (display, workspace, shell).

Run all the tests from the project root with: python3 -m unittest -v
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class TestVendoredRich(unittest.TestCase):
	"""rich comes from vendor/: nothing to install, no sudo."""

	def test_cli_uses_the_rich_copied_in_vendor(self):
		"""Importing pal42.cli makes the rich of vendor/ importable first."""
		import pal42.cli  # noqa: F401  (imported for its effect on sys.path)
		import rich
		self.assertEqual(Path(rich.__file__).resolve().parent, ROOT / "vendor" / "rich")

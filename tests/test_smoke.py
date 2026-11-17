"""Smoke tests: check that the ./42pal launcher starts and answers.

Run all the tests from the project root with: python3 -m unittest -v
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

# Project root, found from this file's location so the tests work from any directory.
ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "42pal"
# Expected output of --version: the program name, then an X.Y.Z version number.
VERSION_LINE = r"^42pal \d+\.\d+\.\d+$"

def run_script(*args, cwd=ROOT, script=SCRIPT):
	"""Run ./42pal (or `script`, a path to it) with the given arguments.

	Returns the finished process. Fails the calling test with a clear message
	when the launcher is missing or not executable, instead of crashing with
	FileNotFoundError.
	"""
	if not os.access(script, os.X_OK):
		raise AssertionError(f"{script} must exist and be executable (chmod +x)")
	# capture_output + text: stdout and stderr come back as str.
	# timeout: a launcher that hangs fails the test instead of blocking the run.
	return subprocess.run(
		[str(script), *args], cwd=cwd, capture_output=True, text=True, timeout=10
	)

class TestLauncher(unittest.TestCase):
	"""Behavior of the ./42pal launcher script."""

	def test_version_flag_prints_version(self):
		"""`./42pal --version` succeeds and prints `42pal X.Y.Z`."""
		result = run_script("--version")
		# On failure, show stderr so the Python error appears in the report.
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertRegex(result.stdout.strip(), VERSION_LINE)

	def test_works_from_any_directory(self):
		"""The launcher finds the pal42 package when run from another directory."""
		# An empty temporary directory: nothing from the project is in it.
		with tempfile.TemporaryDirectory() as tmp:
			result = run_script("--version", cwd=tmp)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertRegex(result.stdout.strip(), VERSION_LINE)

	def test_works_through_a_symlink(self):
		"""A symlink to the launcher (like ~/bin/42pal) still finds pal42."""
		with tempfile.TemporaryDirectory() as tmp:
			link = Path(tmp) / "42pal"
			link.symlink_to(SCRIPT)
			result = run_script("--version", cwd=tmp, script=link)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertRegex(result.stdout.strip(), VERSION_LINE)

	def test_check_catalog_command_passes_on_the_real_catalog(self):
		"""`./42pal check-catalog` checks every ref.c and exits with 0."""
		result = subprocess.run(
			[str(SCRIPT), "check-catalog"], capture_output=True, text=True, timeout=120,
		)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertIn("Catalog OK", result.stdout)

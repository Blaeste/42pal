"""Tests of pal42.runners.c: compiling a student's C files.

Run all the tests from the project root with: python3 -m unittest -v
"""

import os
import tempfile
import unittest
from pathlib import Path

from pal42.runners.c import CRunner

HELLO = '#include <unistd.h>\n\nint\tmain(void)\n{\n\twrite(1, "hello\\n", 6);\n\treturn (0);\n}\n'
UNUSED = "int\tmain(void)\n{\n\tint\tx;\n\n\treturn (0);\n}\n"

class TestCompile(unittest.TestCase):
	"""CRunner.compile(sources, workdir, name) builds the student's program."""

	def setUp(self):
		"""Each test gets a folder for the student's files and a work folder."""
		self.tmp = tempfile.TemporaryDirectory()
		self.rendu = Path(self.tmp.name) / "rendu"
		self.work = Path(self.tmp.name) / "work"
		self.rendu.mkdir()
		self.work.mkdir()

	def tearDown(self):
		self.tmp.cleanup()

	def write(self, name, code):
		"""Write a student's file in the rendu folder and return its path."""
		path = self.rendu / name
		path.write_text(code, encoding="utf-8")
		return path

	def test_valid_file_compiles(self):
		"""A correct .c gives an executable program in the work folder."""
		result = CRunner().compile([self.write("hello.c", HELLO)], self.work, "hello")
		self.assertTrue(result.ok, result.output)
		self.assertTrue(os.access(result.binary, os.X_OK))
		self.assertEqual(result.binary.parent, self.work)

	def test_unused_variable_fails_and_the_error_is_captured(self):
		"""-Werror turns the warning into an error; its message is kept."""
		result = CRunner().compile([self.write("bad.c", UNUSED)], self.work, "bad")
		self.assertFalse(result.ok)
		self.assertIsNone(result.binary)
		self.assertIn("unused variable", result.output)

	def test_error_names_the_file_without_its_folder(self):
		"""The files are compiled in the work folder: bad.c:3:6, not a long path."""
		result = CRunner().compile([self.write("bad.c", UNUSED)], self.work, "bad")
		self.assertTrue(result.output.startswith("bad.c:"), result.output)
		self.assertNotIn(self.tmp.name, result.output)
		# The student's folder stays as it was: no program, no copy.
		self.assertEqual([path.name for path in self.rendu.iterdir()], ["bad.c"])

	def test_compile_command_can_be_changed(self):
		"""An exam can give its own command: without -Werror, a warning passes."""
		runner = CRunner(("cc", "-Wall"))
		result = runner.compile([self.write("bad.c", UNUSED)], self.work, "bad")
		self.assertTrue(result.ok, result.output)
		self.assertIn("warning: unused variable", result.output)

	def test_missing_compiler_gives_a_clear_error(self):
		"""A compiler that is not installed: a failed compilation, not a crash."""
		runner = CRunner(("no_such_cc_42pal", "-Wall"))
		result = runner.compile([self.write("hello.c", HELLO)], self.work, "hello")
		self.assertFalse(result.ok)
		self.assertIn("introuvable", result.output)
		self.assertIn("no_such_cc_42pal", result.output)

	def test_source_already_in_the_work_folder_compiles(self):
		"""No copy is needed when the file is already in the work folder."""
		source = self.work / "hello.c"
		source.write_text(HELLO, encoding="utf-8")
		result = CRunner().compile([source], self.work, "hello")
		self.assertTrue(result.ok, result.output)

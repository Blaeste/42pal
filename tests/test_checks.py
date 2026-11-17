"""Tests of pal42.checks: the checks made on a compiled program.

Run all the tests from the project root with: python3 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pal42.checks import used_functions
from pal42.runners.c import CRunner

USES_FOUR = r"""#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int	main(int ac, char **av)
{
	char	*s;

	s = malloc(4);
	printf("%s\n", av[ac - 1]);
	write(1, "x", 1);
	free(s);
	return (0);
}
"""

class TestUsedFunctions(unittest.TestCase):
	"""used_functions(program): the library functions a program calls."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.work = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def build(self, code):
		"""Compile `code` and return the program."""
		source = self.work / "prog.c"
		source.write_text(code, encoding="utf-8")
		result = CRunner().compile([source], self.work, "prog")
		self.assertTrue(result.ok, result.output)
		return result.binary

	def test_lists_the_library_functions_without_the_c_runtime(self):
		"""malloc, printf, write, free; not __libc_start_main and the like."""
		self.assertEqual(used_functions(self.build(USES_FOUR)), {"free", "malloc", "printf", "write"})

	def test_without_nm_nothing_is_refused_and_nothing_crashes(self):
		"""nm missing on a machine: the check is skipped, no function listed."""
		self.assertEqual(used_functions(self.build(USES_FOUR), nm="no_such_nm_42pal"), set())

"""Tests of pal42.checks: the checks made on a compiled program.

Run all the tests from the project root with: python3 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pal42.checks import defines_main, used_functions
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

class TestStudentObjects(unittest.TestCase):
	"""The checks on the student's objects (.o), without any test main."""

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.work = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def objects(self, files):
		"""Compile {name: code} and return the objects of these files."""
		sources = []
		for name, code in files.items():
			(self.work / name).write_text(code, encoding="utf-8")
			sources.append(self.work / name)
		result = CRunner().compile(sources, self.work, "prog")
		self.assertTrue(result.ok, result.output)
		return result.objects

	def test_a_function_of_another_student_file_is_not_counted(self):
		"""ft_putchar is in a.c and called in b.c: only write comes from outside."""
		objects = self.objects({
			"a.c": "#include <unistd.h>\n\nvoid\tft_putchar(char c)\n{\n\twrite(1, &c, 1);\n}\n",
			"b.c": "void\tft_putchar(char c);\n\nint\tmain(void)\n{\n\tft_putchar('x');\n\treturn (0);\n}\n",
		})
		self.assertEqual(used_functions(*objects), {"write"})

	def test_defines_main_tells_whether_the_student_wrote_a_main(self):
		"""A function exercise must not have a main in the rendu."""
		with_main = self.objects({"m.c": "int\tmain(void)\n{\n\treturn (0);\n}\n"})
		self.assertTrue(defines_main(*with_main))
		function = self.work / "f.c"
		function.write_text("int\tf(void)\n{\n\treturn (1);\n}\n", encoding="utf-8")
		compiled = CRunner().compile([function], self.work, "f",
			extra=[self.work / "m.c"])
		self.assertFalse(defines_main(*compiled.objects))

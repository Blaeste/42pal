"""Tests of pal42.grader: grading a student's rendu, like the moulinette.

Run all the tests from the project root with: python3 -m unittest -v
"""

import tempfile
import unittest
from pathlib import Path

from pal42.catalog import load_catalog
from pal42.grader import grade
from pal42.runners.c import CRunner
from pal42.variant import Variant
from tests.helpers import ECHO, ECHO_OK

class TestGrade(unittest.TestCase):
	"""grade(variant, rendu, runner) on a made-up exercise."""

	def setUp(self):
		"""rendu/ stands for ~/42pal_exam/rendu/<name>/ in each test."""
		self.tmp = tempfile.TemporaryDirectory()
		self.rendu = Path(self.tmp.name)

	def tearDown(self):
		self.tmp.cleanup()

	def hand_in(self, code, name="echo_first.c"):
		"""Write the student's file in the rendu folder."""
		(self.rendu / name).write_text(code, encoding="utf-8")

	def test_right_solution_passes(self):
		"""Every test gives the oracle's output: passed, no trace."""
		self.hand_in(ECHO_OK)
		result = grade(ECHO, self.rendu, CRunner())
		self.assertTrue(result.passed, result.trace)
		self.assertEqual(result.trace, "")
		self.assertEqual((result.tests_passed, result.tests_total), (3, 3))

	def test_progress_is_called_before_each_test(self):
		"""progress(number, total) lets the shell show "test 2/3" while grading."""
		self.hand_in(ECHO_OK)
		calls = []
		grade(ECHO, self.rendu, CRunner(), progress=lambda number, total: calls.append((number, total)))
		self.assertEqual(calls, [(1, 3), (2, 3), (3, 3)])

	def test_missing_newline_fails_with_a_diff_trace(self):
		"""No \\n at the end: stopped at test 1, student in -, moulinette in +."""
		self.hand_in(ECHO_OK.replace('\twrite(1, "\\n", 1);\n', ""))
		result = grade(ECHO, self.rendu, CRunner())
		self.assertFalse(result.passed)
		self.assertEqual(result.tests_passed, 0)
		self.assertEqual(result.trace, (
			"= Test 1 " + "=" * 71 + "\n"
			"$> ./echo_first hello | cat -e\n"
			"--- student\n"
			"+++ moulinette\n"
			"-hello\n"
			"+hello$\n"
			"\n"
			"Diff KO\n"
		))

	def test_crash_gives_its_own_message_instead_of_a_diff(self):
		"""A segfault: the command of the test, then "Segmentation fault"."""
		self.hand_in(ECHO_OK.replace("\tint\tn;\n", "\tint\tn;\n\n\t*(volatile int *)0 = 0;\n"))
		result = grade(ECHO, self.rendu, CRunner())
		self.assertFalse(result.passed)
		self.assertEqual(result.trace, (
			"= Test 1 " + "=" * 71 + "\n"
			"$> ./echo_first hello | cat -e\n"
			"\n"
			"Segmentation fault\n"
		))

	def test_endless_program_gives_a_timeout_message(self):
		"""A program that never ends: "Timeout" instead of a diff."""
		self.hand_in(ECHO_OK.replace("\tint\tn;\n", "\tint\tn;\n\n\twhile (1)\n\t\t;\n"))
		result = grade(ECHO, self.rendu, CRunner(timeout=0.5))
		self.assertFalse(result.passed)
		self.assertTrue(result.trace.endswith("\nTimeout\n"), result.trace)

	def test_compilation_error_gives_the_compiler_output(self):
		"""-Werror refuses an unused variable: the compiler's words, no test run."""
		self.hand_in(ECHO_OK.replace("\tint\tn;\n", "\tint\tn;\n\tint\tunused;\n"))
		result = grade(ECHO, self.rendu, CRunner())
		self.assertFalse(result.passed)
		self.assertEqual(result.tests_passed, 0)
		self.assertTrue(result.trace.startswith("= Compilation ="), result.trace)
		self.assertIn("$> cc -Wall -Wextra -Werror echo_first.c -o echo_first\n", result.trace)
		self.assertIn("unused variable", result.trace)
		self.assertTrue(result.trace.endswith("\nCompilation KO\n"), result.trace)

	def test_missing_file_is_named_in_the_trace(self):
		"""A wrong file name (echo.c): the expected one is named, nothing compiled."""
		self.hand_in(ECHO_OK, name="echo.c")
		result = grade(ECHO, self.rendu, CRunner())
		self.assertFalse(result.passed)
		self.assertEqual(result.trace, (
			"= Rendu " + "=" * 72 + "\n"
			"Fichier manquant : echo_first.c\n"
			"\n"
			"Rendu KO\n"
		))

	def test_forbidden_function_fails_even_with_the_right_output(self):
		"""printf when only write is allowed: refused before any test is run."""
		self.hand_in(
			'#include <stdio.h>\n\nint\tmain(int ac, char **av)\n{\n'
			'\tif (ac == 2)\n\t\tprintf("%s", av[1]);\n\tprintf("%c", 10);\n\treturn (0);\n}\n'
		)
		result = grade(ECHO, self.rendu, CRunner())
		self.assertFalse(result.passed)
		self.assertEqual(result.trace, (
			"= Fonctions interdites " + "=" * 57 + "\n"
			"Fonction interdite : printf\n"
			"Fonctions autorisées : write\n"
			"\n"
			"Fonctions KO\n"
		))

SHIFT_FORWARD_2 = r"""#include <unistd.h>

int	main(int ac, char **av)
{
	char	c;
	int		i;

	if (ac == 2)
	{
		i = 0;
		while (av[1][i])
		{
			c = av[1][i];
			if (c >= 'a' && c <= 'z')
				c = (c - 'a' + 2) % 26 + 'a';
			else if (c >= 'A' && c <= 'Z')
				c = (c - 'A' + 2) % 26 + 'A';
			write(1, &c, 1);
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
"""

class TestRealExercise(unittest.TestCase):
	"""A real C solution, graded on all the tests of a real exercise."""

	def test_c_solution_of_shift_letters_passes_every_test(self):
		"""forward_shift_2 (every letter): our C solution agrees with the oracle."""
		exo = load_catalog().exercises["shift_letters"]
		variant = Variant(exo, 0, {"shift": "2", "direction": "forward", "letters": "all"})
		with tempfile.TemporaryDirectory() as rendu:
			(Path(rendu) / "forward_shift_2.c").write_text(SHIFT_FORWARD_2, encoding="utf-8")
			result = grade(variant, rendu, CRunner())
		self.assertTrue(result.passed, result.trace)
		self.assertEqual(result.tests_passed, result.tests_total)

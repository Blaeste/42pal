"""Helpers for the Python exercises: the test main, the tests and the calls.

A Python function is graded like a C one: a test main calls it and prints
what it returns, and the grader compares that with the oracle. The values
of a test travel as Python literals in argv (repr in, ast.literal_eval
out), and the result comes back as its repr. So an exercise writes its
tests with case(), its oracle with values() and shown(), and its calls
with call():

	def oracle(params, test):
		items, steps = values(test)
		return shown(items[-steps:] + items[:-steps])

	tests = [case([1, 2, 3], 1), case([], 0)]
"""

import ast

from pal42.model import TestCase

# The test main of a function: MODULE and FUNCTION are replaced by harness().
# It never lets an exception out: what went wrong is printed instead, so
# that the trace shows it in place of the expected output.
HARNESS = '''"""The test main of 42pal: it calls your function and prints what it returns."""

import ast
import sys

def main():
	try:
		from MODULE import FUNCTION
	except Exception as error:
		print(f"Cannot import FUNCTION from MODULE.py: {type(error).__name__}: {error}")
		return
	args = [ast.literal_eval(arg) for arg in sys.argv[1:]]
	try:
		result = FUNCTION(*args)
	except Exception as error:
		print(f"Your function raised {type(error).__name__}: {error}")
		return
	print(repr(result))

main()
'''

def harness(module, function=None):
	"""The test main that imports `function` (by default, `module`) from module.py.

	Both may hold holes like the name of the exercise ("rotate_${side}"):
	the variant fills them in, like in a C test main.
	"""
	return HARNESS.replace("MODULE", module).replace("FUNCTION", function or module)

def case(*values):
	"""A test that calls the function with `values`, written as Python literals."""
	return TestCase(tuple(repr(value) for value in values))

def values(test):
	"""The values of a test, read back from its literals."""
	return [ast.literal_eval(arg) for arg in test.args]

def call(name, test):
	"""The call of the function `name` on `test`, as the examples and traces show it."""
	return f"{name}({', '.join(test.args)})"

def shown(result):
	"""What the test main prints for `result`: its repr, then a newline."""
	return f"{result!r}\n"

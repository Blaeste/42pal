"""Writing the subject of a variant in the 42 format.

Like the rest of the core, this module never prints: it returns the text,
and the front-ends write it (subject.en.txt in the terminal, a page on the web).
"""

import re
from string import Template

# An argument made only of these characters needs no quotes in a shell.
PLAIN_ARG = re.compile(r"[A-Za-z0-9_./=:,+-]+")

def render(variant):
	"""Return the subject of `variant`, in the 42 format.

	The header, a line of dashes, the statement, then the examples if the
	exercise has some.
	"""
	exo = variant.exercise
	# The labels are padded so that the colons line up, like in the 42 subjects.
	lines = [
		f"Assignment name  : {variant.name}",
		f"Expected files   : {', '.join(variant.expected_files)}",
		f"Allowed functions: {', '.join(exo.allowed_functions)}",
		"-" * 80,
		"",
		statement(variant),
	]
	if exo.examples:
		lines += ["", "Examples:", ""] + _examples(variant)
	return "\n".join(lines) + "\n"

def statement(variant):
	"""Return the statement of `variant`: each `$param` becomes its text.

	The name and the files use the drawn values (repeat_twice), but the
	statement uses their texts ("2 times"), see Param.texts.
	"""
	texts = {
		param.name: param.text(variant.params[param.name])
		for param in variant.exercise.params
	}
	return Template(variant.exercise.subject).substitute(texts)

def _examples(variant):
	"""Return the lines of the examples: each command, then what it prints.

	The outputs are computed by the oracle for this variant, never by hand.
	"""
	exo = variant.exercise
	lines = []
	for test in exo.examples:
		lines.append(f"$>{example_command(variant.name, test)} | cat -e")
		# render() joins the lines with \n, so the last one of the output
		# is removed here; an output without \n ends without $, as in cat -e.
		lines.append(cat_e(exo.oracle(variant.params, test)).removesuffix("\n"))
	return lines

def example_command(name, test):
	"""Return the command that runs the program `name` on `test`: ./name args."""
	return " ".join([f"./{name}", *map(shell_quote, test.args)])

def shell_quote(arg):
	"""Return `arg` written the way an example shows it in a shell command.

	A plain word stays as it is (hello); anything else gets double quotes,
	like in the 42 subjects ("ab c"). Copied into a shell, the example gives
	the program exactly the same argument.
	"""
	if PLAIN_ARG.fullmatch(arg):
		return arg
	# Inside double quotes, the shell still reads \ " $ and `: a \ in front
	# of each makes it a plain character.
	escaped = re.sub(r'([\\"$`])', r"\\\1", arg)
	return f'"{escaped}"'

def cat_e(text):
	"""Return `text` shown the way `cat -e` does.

	text is a str (an oracle's output) or bytes (a program's output).
	A `$` marks each end of line, so a missing \\n can be seen, and the
	invisible bytes are shown too: ^A for a control character, ^? for DEL,
	and M- in front of a byte above 127.
	"""
	if isinstance(text, str):
		text = text.encode()
	return "".join(_show_byte(byte) for byte in text)

def _show_byte(byte):
	"""One byte (0 to 255) shown the way `cat -e` does."""
	if byte == ord("\n"):
		return "$\n"
	if byte == ord("\t"):
		return "\t"
	# Above 127: "M-", then the byte minus 128 with the same rules,
	# so 128 + 1 gives M-^A and 128 + ord("a") gives M-a.
	if byte >= 128:
		return "M-" + _show_ascii(byte - 128)
	return _show_ascii(byte)

def _show_ascii(byte):
	"""One byte from 0 to 127: control characters get the ^ notation."""
	# Control characters 0 to 31 are shown as ^ and the letter 64 further:
	# 1 gives ^A, 27 (escape) gives ^[.
	if byte < 32:
		return "^" + chr(byte + 64)
	if byte == 127:
		return "^?"
	return chr(byte)

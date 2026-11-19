"""grid_seek: an original Python model in the style of "find words in a grid
in every direction".

The student writes a function that looks for a word in a grid of letters:
its first place in a straight line, whether it can be spelled by a path of
neighbouring cells, or how many times it is written straight in four
directions. Every place in the 8 directions with their codes, the real
subject, is not one of the rules.
"""

from pal42.model import Exercise, Param
from pal42.python_exercise import call, case, harness, shown, values

DIRECTIONS = [("R", 0, 1), ("D", 1, 0), ("L", 0, -1), ("U", -1, 0),
	("DR", 1, 1), ("DL", 1, -1), ("UL", -1, -1), ("UR", -1, 1)]

def written(grid, word, row, col, dr, dc):
	for index, char in enumerate(word):
		r, c = row + index * dr, col + index * dc
		if not (0 <= r < len(grid) and 0 <= c < len(grid[r])) or grid[r][c] != char:
			return False
	return True

def spelled(grid, word, row, col, used):
	if grid[row][col] != word[0]:
		return False
	if len(word) == 1:
		return True
	used = used | {(row, col)}
	for _, dr, dc in DIRECTIONS[:4]:
		r, c = row + dr, col + dc
		if 0 <= r < len(grid) and 0 <= c < len(grid[0]) and (r, c) not in used \
				and spelled(grid, word[1:], r, c, used):
			return True
	return False

def oracle(params, test):
	grid, word = values(test)
	cells = [(row, col) for row in range(len(grid)) for col in range(len(grid[0]) if grid else 0)]
	rule = params["rule"]
	if rule == "first":
		return shown(next(((row, col, name) for row, col in cells for name, dr, dc in DIRECTIONS
			if written(grid, word, row, col, dr, dc)), None))
	if rule == "straight":
		return shown(sum(1 for row, col in cells for _, dr, dc in DIRECTIONS[:4]
			if written(grid, word, row, col, dr, dc)))
	return shown(any(spelled(grid, word, row, col, set()) for row, col in cells))

def generate_tests(params, rng):
	pairs = [(["cat", "aox", "tac"], "cat"), (["cat", "aox", "tac"], "tac"), (["cat", "aox", "tac"], "xyz"),
		(["cat", "aox", "tac"], "cao"), (["cat", "aox", "tac"], "cac"), (["abc", "def", "ghi"], "aei"),
		(["abc", "def", "ghi"], "fed"), (["aa", "aa"], "aaa"), (["ab", "cd"], "abdc"), (["xyz"], "zy")]
	for _ in range(10):
		width = rng.randint(2, 5)
		grid = ["".join(rng.choice("abo") for _ in range(width)) for _ in range(rng.randint(2, 5))]
		pairs.append((grid, "".join(rng.choice("abo") for _ in range(rng.randint(2, 4)))))
	return [case(grid, word) for grid, word in pairs]

RULES = {
	"first": ("tuple[int, int, str] | None", "the first place where the word is written in a\n"
		"straight line, from its first letter, in one of 8 directions: right (R),\n"
		"down (D), left (L), up (U), down-right (DR), down-left (DL), up-left (UL)\n"
		"and up-right (UR). The cells of the first letter are tried row by row\n"
		"from the top, each row from the left, and for each cell the directions in\n"
		"that order. It returns a (row, col, direction) tuple, or None if the\n"
		"word is nowhere"),
	"path": ("bool", "True if the word can be spelled by a path of cells, each one next to\n"
		"the one before by a side (up, down, left or right), no cell used twice;\n"
		"False otherwise"),
	"straight": ("int", "how many times the word is written in a straight line in one of 4\n"
		"directions: right, down, left or up. Each first cell and direction that\n"
		"spell it count once"),
}

EXERCISE = Exercise(
	name="grid_seek",
	language="python",
	kind="function",
	assignment_name="seek_${rule}",
	expected_files=("seek_${rule}.py",),
	allowed_functions=(),
	themes=("grid_word_search",),
	params=(Param("rule", tuple(RULES), {rule: text for rule, (_, text) in RULES.items()}),),
	subject=(
		"Write a function that takes a grid of letters, a list of strings of the\n"
		"same length (row 0 is the first string, column 0 its first character),\n"
		"and a word of 2 letters or more. It returns\n"
		"$rule.\n"
		"\n"
		"The function returns its result and prints nothing.\n"
		"\n"
		"Your function must be declared as follows:\n"
		"\n"
		"$prototype"
	),
	oracle=oracle,
	generate_tests=generate_tests,
	harness=harness("seek_${rule}"),
	call=call,
	prototype=lambda name, params: f"def {name}(grid: list[str], word: str) -> {RULES[params['rule']][0]}:",
	examples=lambda params: {
		"first": (case(["cat", "aox", "tac"], "tac"), case(["cat", "aox", "tac"], "xyz")),
		"path": (case(["cat", "aox", "tac"], "cao"), case(["cat", "aox", "tac"], "cac")),
		"straight": (case(["cat", "aox", "tac"], "cat"),),
	}[params["rule"]],
)

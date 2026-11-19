"""path_fill: an original Python model in the style of "fill a matrix along
a path".

The student writes a function that fills a matrix with 1, 2, 3... along a
path: a spiral that turns the other way, rows that go back and forth, or a
spiral in a rectangle. The clockwise spiral in a square, the real subject,
is not one of the rules.
"""

from pal42.model import Exercise, Param
from pal42.python_exercise import call, case, harness, shown, values

def spiral(rows, cols, moves):
	"""Fill rows x cols along a spiral that tries the moves in turn, from the top left."""
	grid = [[0] * cols for _ in range(rows)]
	row = col = way = 0
	for number in range(1, rows * cols + 1):
		grid[row][col] = number
		for _ in range(4):
			step_row, step_col = moves[way]
			next_row, next_col = row + step_row, col + step_col
			if 0 <= next_row < rows and 0 <= next_col < cols and not grid[next_row][next_col]:
				row, col = next_row, next_col
				break
			way = (way + 1) % 4
	return grid

def oracle(params, test):
	rule = params["rule"]
	if rule == "counter":
		(size,) = values(test)
		return shown(spiral(size, size, [(1, 0), (0, 1), (-1, 0), (0, -1)]))
	rows, cols = values(test)
	if rows == 0 or cols == 0:
		return shown([])
	if rule == "rect_spiral":
		return shown(spiral(rows, cols, [(0, 1), (1, 0), (0, -1), (-1, 0)]))
	lines = [list(range(row * cols + 1, row * cols + cols + 1)) for row in range(rows)]
	return shown([line if row % 2 == 0 else line[::-1] for row, line in enumerate(lines)])

def generate_tests(params, rng):
	if params["rule"] == "counter":
		return [case(size) for size in (0, 1, 2, 3, 4, 5, 6)]
	pairs = [(2, 3), (3, 4), (0, 3), (3, 0), (1, 1), (1, 5), (5, 1), (4, 4), (2, 2)]
	pairs += [(rng.randint(1, 6), rng.randint(1, 6)) for _ in range(6)]
	return [case(rows, cols) for rows, cols in pairs]

RULES = {
	"counter": ("n: int", "an n x n matrix (n from 0) filled along a spiral that turns\n"
		"counterclockwise: from the top left corner, down the first column, then\n"
		"right along the bottom row, then up the last column, then left along the\n"
		"top row, and so on inward, each time up to a cell already filled or the\n"
		"edge"),
	"snake": ("rows: int, cols: int", "a matrix of rows rows of cols ints filled row after\n"
		"row: the first row from left to right, the second from right to left,\n"
		"the third from left to right again, and so on"),
	"rect_spiral": ("rows: int, cols: int", "a matrix of rows rows of cols ints filled along a\n"
		"spiral that turns clockwise: from the top left corner, right along the\n"
		"top row, then down the last column, then left along the bottom row,\n"
		"then up the first column, and so on inward, each time up to a cell\n"
		"already filled or the edge"),
}

EXERCISE = Exercise(
	name="path_fill",
	language="python",
	kind="function",
	assignment_name="fill_${rule}",
	expected_files=("fill_${rule}.py",),
	allowed_functions=(),
	themes=("spiral_fill",),
	params=(Param("rule", tuple(RULES), {rule: text for rule, (_, text) in RULES.items()}),),
	subject=(
		"Write a function that returns a matrix (a list of rows, each a list of\n"
		"ints) holding the numbers from 1 up to its number of cells, put one after\n"
		"the other in the cells:\n"
		"$rule.\n"
		"\n"
		"A matrix with no cell is an empty list.\n"
		"\n"
		"The function returns its result and prints nothing.\n"
		"\n"
		"Your function must be declared as follows:\n"
		"\n"
		"$prototype"
	),
	oracle=oracle,
	generate_tests=generate_tests,
	harness=harness("fill_${rule}"),
	call=call,
	prototype=lambda name, params: f"def {name}({RULES[params['rule']][0]}) -> list[list[int]]:",
	examples=lambda params: {
		"counter": (case(3), case(1)),
		"snake": (case(2, 3), case(3, 1)),
		"rect_spiral": (case(3, 4), case(0, 3)),
	}[params["rule"]],
)

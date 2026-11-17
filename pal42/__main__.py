"""Command-line entry point, run by `python3 -m pal42` (see the ./42pal launcher)."""

import argparse

from pal42 import __version__

def main(argv=None):
	"""Parse the command-line arguments and return the process exit code.

	argv defaults to sys.argv[1:]; tests can pass their own list instead.
	With no command, the examshell starts.
	"""
	parser = argparse.ArgumentParser(prog="42pal")
	# The "version" action prints the string, then exits with code 0.
	# %(prog)s is replaced by the program name given above.
	parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
	parser.add_argument(
		"--hard", action="store_true",
		help="hard retry timer: longer waits after each failed grademe (soft by default)",
	)
	commands = parser.add_subparsers(dest="command")
	commands.add_parser(
		"check-catalog", help="check that every ref.c passes its own exercise",
	)
	arguments = parser.parse_args(argv)
	# Imported here: --version must work even if the terminal front-end breaks.
	if arguments.command == "check-catalog":
		from pal42.cli.check import check_catalog
		return check_catalog()
	from pal42.cli.shell import main as shell_main
	return shell_main("hard" if arguments.hard else "soft")

if __name__ == "__main__":
	# SystemExit turns the value returned by main() into the process exit code.
	raise SystemExit(main())

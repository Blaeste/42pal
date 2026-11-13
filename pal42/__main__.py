"""Command-line entry point, run by `python3 -m pal42` (see the ./42pal launcher)."""

import argparse

from pal42 import __version__

def main(argv=None):
	""" Parse the command-line arguments and return the process exit code.

	argv defaults to sys,argv[1:]; tests can pass their own lis tinstead.
	"""
	parser = argparse.ArgumentParser(prog="42pal")
	# The "version" action prints the string, then exits with code 0.
	# %(prog)s is replaced by the program name given above.
	parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
	parser.parse_args(argv)
	return 0

if __name__ == "__main__":
	# SystemExit turns the value returned by main() into the process exit code.
	raise SystemExit(main())

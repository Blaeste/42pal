"""./42pal check-catalog: is every exercise of the catalog graded right?

For each exercise, its ref.c is graded like a student's rendu on every
variant (see pal42.reference). A variant where ref.c fails means that the
oracle or ref.c is wrong: the command names it (exo#seed) with its trace.
"""

from rich.console import Console
from rich.markup import escape
from rich.text import Text

from pal42.catalog import load_catalog
from pal42.reference import check_variant, variants_to_check

def check_catalog(console=None, catalog=None):
	"""Check every exercise of `catalog`; print the result; return the exit code.

	0 when everything is right, 1 when something is wrong: a ref.c that fails
	a variant, a missing ref.c, or a folder the catalog had to skip.
	"""
	console = console or Console()
	catalog = catalog or load_catalog()
	ok = True
	for warning in catalog.warnings:
		console.print(f"[bold red]✗[/] {escape(warning)}")
		ok = False
	variants_checked = 0
	for name in sorted(catalog.exercises):
		ref = catalog.folders[name] / "ref.c"
		if not ref.is_file():
			console.print(f"[bold red]✗[/] {escape(name)}: no ref.c")
			ok = False
			continue
		failures, total = _check_exercise(console, catalog.exercises[name], name, ref)
		variants_checked += total
		mark = "[bold red]✗[/]" if failures else "[bold green]✓[/]"
		console.print(f"{mark} {escape(name):16} {total - len(failures)}/{total} variants OK")
		for variant, result in failures:
			params = ", ".join(f"{key}={value}" for key, value in variant.params.items())
			console.print(f"  {escape(variant.id)} ({escape(params)})")
			# Text: the trace is shown as it is, with no rich markup read in it.
			console.print(Text(result.trace))
		ok = ok and not failures
	if ok:
		console.print(f"[bold green]Catalog OK[/]: {len(catalog.exercises)} exercises, "
			f"{variants_checked} variants")
	else:
		console.print("[bold red]Catalog KO[/]: see the errors above")
	return 0 if ok else 1

def _check_exercise(console, exo, name, ref):
	"""Grade ref.c on each variant to check; return the failures and the count."""
	variants = variants_to_check(exo)
	failures = []
	# A spinner while checking; rich shows it only in a real terminal.
	with console.status(f"Checking {name}…") as status:
		for number, variant in enumerate(variants, start=1):
			status.update(f"Checking {name}… variant {number}/{len(variants)}")
			result = check_variant(variant, ref)
			if not result.passed:
				failures.append((variant, result))
	return failures, len(variants)

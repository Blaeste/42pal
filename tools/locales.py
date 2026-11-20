"""The catalogs of the languages: the texts to translate, a new language, what is missing.

	python3 tools/locales.py extract              the texts of the code, one per line
	python3 tools/locales.py new <code> "<Name>"   pal42/locales/<code>.json with every text to fill
	python3 tools/locales.py check [<code>...]     what each catalog lacks; exit code 1 if anything

A text to translate is the first argument of t() in pal42/, written as a
string. To add a language (docs/plans/languages.md): new, fill each empty
value, then check until it says nothing. An empty value stays in English.
"""

import ast
import json
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = ROOT / "pal42"
LOCALES_DIR = CODE_DIR / "locales"

def extract(folder=CODE_DIR):
	"""The texts given to t() in the code of `folder`, sorted, each once."""
	texts = set()
	for path in sorted(Path(folder).rglob("*.py")):
		tree = ast.parse(path.read_text(encoding="utf-8"))
		for node in ast.walk(tree):
			if (isinstance(node, ast.Call) and _is_t(node.func) and node.args
					and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
				texts.add(node.args[0].value)
	return sorted(texts)

def _is_t(func):
	"""t(...) or i18n.t(...)."""
	return (isinstance(func, ast.Name) and func.id == "t") or (isinstance(func, ast.Attribute) and func.attr == "t")

def fields(text):
	"""The {fields} of `text`, or None when its braces are not fields but code."""
	try:
		names = {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}
	except ValueError:
		return None
	if any(not name.isidentifier() for name in names):
		return None
	return sorted(names)

def _read(code, folder):
	return json.loads((Path(folder) / f"{code}.json").read_text(encoding="utf-8"))

def check(code, texts, folder=LOCALES_DIR):
	"""The problems of the catalog `code`, as (kind, text): missing, fields, unused, name."""
	data = _read(code, folder)
	problems = []
	if not data.get("_name"):
		problems.append(("name", "_name"))
	for text in texts:
		value = data.get(text)
		if not value:
			problems.append(("missing", text))
		elif fields(text) is not None and fields(value) != fields(text):
			problems.append(("fields", text))
	known = set(texts)
	problems += [("unused", key) for key in data if not key.startswith("_") and key not in known]
	return problems

def new(code, name, texts, folder=LOCALES_DIR):
	"""Make (or complete) the catalog `code`: every text, empty when not translated yet."""
	path = Path(folder) / f"{code}.json"
	data = _read(code, folder) if path.exists() else {}
	skeleton = {"_name": data.get("_name") or name}
	for text in texts:
		skeleton[text] = data.get(text, "")
	# The translations of texts the code no longer has stay, for check to say so.
	skeleton.update({key: value for key, value in data.items() if key not in skeleton})
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(skeleton, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")
	return path

def main(args, code=CODE_DIR, locales=LOCALES_DIR):
	command = args[0] if args else ""
	texts = extract(code)
	if command == "extract":
		print("\n".join(texts))
		return 0
	if command == "new" and len(args) == 3:
		print(f"{new(args[1], args[2], texts, locales)}: {len(texts)} texts to fill")
		return 0
	if command == "check":
		codes = args[1:] or sorted(path.stem for path in Path(locales).glob("*.json"))
		problems = 0
		for language in codes:
			found = check(language, texts, locales)
			problems += len(found)
			print(f"{language}: {'complete' if not found else f'{len(found)} problems'}")
			for kind, text in found:
				print(f"  {kind:8} {text!r}")
		return 1 if problems else 0
	print(__doc__)
	return 2

if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))

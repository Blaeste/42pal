"""The catalogs of the languages: the texts to translate, a new language, what is missing.

	python3 tools/locales.py extract              the texts of the code, one per line
	python3 tools/locales.py new <code> "<Name>"   the catalog and the subjects of a language, to fill
	python3 tools/locales.py check [<code>...]     what each language lacks; exit code 1 if anything

A text to translate is the first argument of t() or N_() in pal42/,
written as a string, or the skill of a theme in themes.json. The subject
of an exercise is translated in exercises/<language>/<name>/locales/
<code>.json: {"subject": the statement with the same $fields, "texts":
{param: {value: words}}}. To add a language (docs/plans/languages.md):
new, fill each empty value, then check until it says nothing. An empty
value stays in English.
"""

import ast
import json
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = ROOT / "pal42"
LOCALES_DIR = CODE_DIR / "locales"
# The skill of each theme is shown in the menus of practice: translated too.
THEMES_FILE = ROOT / "themes.json"
EXERCISES_DIR = ROOT / "exercises"
# A $field of a subject: $name or ${name} ($$ is a dollar).
SUBJECT_FIELD = re.compile(r"\$(?:\{(\w+)\}|(\w+))")

def extract(folder=CODE_DIR, themes=None):
	"""The texts to translate, sorted, each once: those given to t() or N_() in
	the code of `folder`, and the skills of the themes (themes.json of 42pal,
	when `folder` is its code)."""
	texts = set()
	themes = themes or (THEMES_FILE if Path(folder) == CODE_DIR else None)
	if themes is not None and Path(themes).is_file():
		texts |= {theme["skill"] for theme in json.loads(Path(themes).read_text(encoding="utf-8")).values()
			if theme.get("skill")}
	for path in sorted(Path(folder).rglob("*.py")):
		tree = ast.parse(path.read_text(encoding="utf-8"))
		for node in ast.walk(tree):
			if (isinstance(node, ast.Call) and _is_t(node.func) and node.args
					and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
				texts.add(node.args[0].value)
	return sorted(texts)

# t() translates; N_() marks a text that t() translates later (a constant).
MARKERS = ("t", "N_")

def _is_t(func):
	"""t(...), N_(...), or the same as i18n.t(...)."""
	return ((isinstance(func, ast.Name) and func.id in MARKERS)
		or (isinstance(func, ast.Attribute) and func.attr in MARKERS))

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

def subject_fields(template):
	"""The $fields of a subject, sorted, each once."""
	return sorted({match.group(1) or match.group(2) for match in SUBJECT_FIELD.finditer(template.replace("$$", ""))})

def _catalog(root):
	"""The exercises of 42pal (they import pal42: the project goes on the path)."""
	if str(ROOT) not in sys.path:
		sys.path.insert(0, str(ROOT))
	from pal42.catalog import load_catalog
	return load_catalog(Path(root))

def check_subjects(code, root=EXERCISES_DIR):
	"""The problems of the subjects in the language `code`, as (kind, where): subject
	(missing), subject-fields ($fields not those of the English one), subject-text
	(the words of a value of the variants missing)."""
	catalog = _catalog(root)
	problems = []
	for name, exo in sorted(catalog.exercises.items()):
		path = catalog.folders[name] / "locales" / f"{code}.json"
		try:
			data = json.loads(path.read_text(encoding="utf-8"))
		except (OSError, ValueError):
			data = {}
		if not data.get("subject"):
			problems.append(("subject", name))
			continue
		if subject_fields(data["subject"]) != subject_fields(exo.subject):
			problems.append(("subject-fields", name))
		texts = data.get("texts") or {}
		for param in exo.params:
			for value in param.values if param.texts else ():
				if not (texts.get(param.name) or {}).get(value):
					problems.append(("subject-text", f"{name}: {param.name}={value}"))
	return problems

def new_subjects(code, root=EXERCISES_DIR):
	"""The subject of each exercise in `code`, to fill: the files not there yet, empty."""
	catalog = _catalog(root)
	made = 0
	for name, exo in sorted(catalog.exercises.items()):
		path = catalog.folders[name] / "locales" / f"{code}.json"
		if path.exists():
			continue
		texts = {param.name: {value: "" for value in param.values} for param in exo.params if param.texts}
		path.parent.mkdir(exist_ok=True)
		path.write_text(json.dumps({"subject": "", "texts": texts}, indent="\t", ensure_ascii=False) + "\n",
			encoding="utf-8")
		made += 1
	return made

def main(args, code=CODE_DIR, locales=LOCALES_DIR, exercises=None):
	command = args[0] if args else ""
	texts = extract(code)
	if command == "extract":
		print("\n".join(texts))
		return 0
	if command == "new" and len(args) == 3:
		print(f"{new(args[1], args[2], texts, locales)}: {len(texts)} texts to fill")
		if exercises is not None or code == CODE_DIR:
			print(f"subjects: {new_subjects(args[1], exercises or EXERCISES_DIR)} to fill")
		return 0
	if command == "check":
		codes = args[1:] or sorted(path.stem for path in Path(locales).glob("*.json"))
		problems = 0
		for language in codes:
			found = check(language, texts, locales)
			# The subjects of 42pal (or of the exercises given).
			if exercises is not None or code == CODE_DIR:
				found += check_subjects(language, exercises or EXERCISES_DIR)
			problems += len(found)
			print(f"{language}: {'complete' if not found else f'{len(found)} problems'}")
			for kind, text in found:
				print(f"  {kind:8} {text!r}")
		return 1 if problems else 0
	print(__doc__)
	return 2

if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))

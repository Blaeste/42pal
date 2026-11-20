"""The settings of 42pal, kept in ~/.42pal/settings.json: for now, the language.

PAL42_LANG, when set, wins over the file (scripts, the tests). Like the
rest of the core, this module never prints.
"""

import json
import os

from pal42 import i18n
from pal42.session import STATE_DIR

SETTINGS_FILE = STATE_DIR / "settings.json"
LANGUAGE_VARIABLE = "PAL42_LANG"

def load(path=None):
	"""The settings saved, as a dict ({} when there are none or they cannot be read)."""
	path = path or SETTINGS_FILE
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return {}
	return data if isinstance(data, dict) else {}

def save(values, path=None):
	"""Keep `values` in the settings file, with the settings already there."""
	path = path or SETTINGS_FILE
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps({**load(path), **values}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def apply_language(environ=None, path=None, folder=None):
	"""At launch: the language of PAL42_LANG, else the one saved, else English; return its code."""
	environ = os.environ if environ is None else environ
	code = environ.get(LANGUAGE_VARIABLE) or load(path).get("language") or i18n.DEFAULT
	return i18n.set_language(code, folder)

def choose_language(code, path=None, folder=None):
	"""The language chosen in Settings: used at once, and kept; return its code."""
	code = i18n.set_language(code, folder)
	save({"language": code}, path)
	return code

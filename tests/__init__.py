
import os

# No test looks for a newer 42pal (see pal42/update.py): no network, and no
# unexpected question. The subprocesses the tests start inherit it.
os.environ["PAL42_NO_UPDATE"] = "1"

# The tests read 42pal in English, whatever the language saved in
# ~/.42pal/settings.json (see pal42/settings.py).
os.environ["PAL42_LANG"] = "en"

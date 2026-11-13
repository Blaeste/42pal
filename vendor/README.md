# vendor/

Third-party libraries copied into the repository, so that 42pal runs on the
campus machines with nothing to install and no sudo.

| Library | Version | License | Why |
|---|---|---|---|
| [rich](https://github.com/Textualize/rich) | 13.9.4 | MIT (`LICENSES/rich.txt`) | terminal display: colors, tables, panels, live timer |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.12.2 | PSF (`LICENSES/typing_extensions.txt`) | needed by `rich.progress` on Python 3.10 |

Not copied, on purpose: `pygments` (5 MB, only for code highlighting) and
`markdown-it-py` (only for Markdown). `rich.syntax` and `rich.markdown` do not
work without them, and 42pal does not use them.

Only `pal42/cli/` uses these libraries: `pal42/cli/__init__.py` puts this
folder first in Python's path. The core (`pal42/` outside `cli/`) stays
standard library only.

## Updating

```sh
python3 -m pip download "rich==<version>" --no-deps -d /tmp/wheels
python3 -m pip download "typing_extensions==<version>" --no-deps -d /tmp/wheels
```

Extract each wheel (`python3 -m zipfile -e <wheel> <folder>`), replace
`vendor/rich/` and `vendor/typing_extensions.py`, copy the `LICENSE` of each
`.dist-info` into `LICENSES/`, update the table above, then run the tests.

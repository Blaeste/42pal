"""The full-screen interface of 42pal, built with textual (copied into vendor/).

The shells of the text interface do all the work (pal42.cli.shell and
pal42.cli.practice): this module shows their menus as screens, sends them
the commands typed, and shows what they print. Its look is in tui.tcss.

The flow: a fake login, the saved exam to resume if any, then the menus
(who, which exam, which mode, which level), each with a last choice to go
back; then the session screen, until the exam ends.
"""

import asyncio
import getpass
import io
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from rich.console import Console
from rich.markup import escape
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.css.scalar import ScalarOffset
from textual.screen import Screen
from textual.strip import Strip
from textual.suggester import SuggestFromList, Suggester
from textual.widgets import Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from pal42 import cheat, i18n, settings
from pal42 import testers as testers_core
from pal42.i18n import N_, t
from pal42.cli import display
from pal42.cli.practice import PRACTICE_COMMANDS, PRACTICE_SHORTCUTS, PracticeShell
from pal42.cli.shell import (BACK, COMMANDS, PRACTICE, PROGRESS, SETTINGS, SHORTCUTS, SIDE_CHOICES, TESTERS,
	Shell, suggest_folder)
from pal42.exam import AUDIENCES
from pal42.progress import exam_rows, summary, weak_themes
from pal42.session import SessionStore
from pal42.update import apply_update, restart

LETTERS = [
	"██╗  ██╗██████╗ ██████╗  █████╗ ██╗     ",
	"██║  ██║╚════██╗██╔══██╗██╔══██╗██║     ",
	"███████║ █████╔╝██████╔╝███████║██║     ",
	"╚════██║██╔═══╝ ██╔═══╝ ██╔══██║██║     ",
	"     ██║███████╗██║     ██║  ██║███████╗",
	"     ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚══════╝",
]
# The left half of a handlebar moustache, its curl outside; the right half
# is its mirror. With the letters: 64 columns, the width of the cards.
MOUSTACHE = [
	"           ",
	" ▄▀▀▄      ",
	"▐▌  ▀      ",
	" ▀▀▄▄▄▄▄▄▄▄",
	"   ▀▀█████▀",
	"           ",
]
MIRRORED = str.maketrans("▌▐", "▐▌")
LOGO = [
	f"{left} {letters.ljust(40)} {left[::-1].translate(MIRRORED)}"
	for left, letters in zip(MOUSTACHE, LETTERS)
]

# The colors the logo goes through, cyan to violet; they move slowly.
GRADIENT = ["#5eead4", "#67e8f9", "#7dd3fc", "#93c5fd", "#a5b4fc", "#c4b5fd", "#d8b4fe"]

TAGLINE = N_("exam trainer · random variants · local moulinette")

# What the app exits with once a newer 42pal is pulled: it must start again.
RESTART = object()

# Under this many lines, the screens get the "-compact" class (see tui.tcss).
COMPACT_HEIGHT = 30

# From this many columns, the subject and the log stand side by side.
WIDE_WIDTH = 150

def hints(pairs):
	"""The line of keys at the bottom of a screen: [("⏎", "choose"), ...]."""
	text = Text()
	for key, what in pairs:
		if text:
			text.append("   ")
		text.append(key, style="bold #a5b4fc")
		text.append(f" {t(what)}")
	return text

def option_label(title, meta):
	"""A menu choice: its title in bold, a grey line under it."""
	label = Text(title, style="bold")
	if meta:
		label.append(f"\n{meta}", style="dim")
	return label

# A web address in a text: up to a space, a quote or a closing bracket.
WEB_ADDRESS = re.compile(r"https?://[^\s'\")\]>]+")

def open_on_click(target):
	"""The style of a text that opens `target` (a path or a web address) when clicked."""
	return Style(underline=True, meta={"@click": f"app.open_link({target!r})"})

def link_target(link):
	"""What to open for a rich link: the path of a file:// link, or the address."""
	parts = urlparse(link)
	return unquote(parts.path) if parts.scheme == "file" else link

def clickable(text):
	"""Make the links of `text` open with a click: rich links and web addresses.

	Textual does not open the links of rich (the terminal would, but textual
	keeps the mouse): each one gets a click action instead (see open_link).
	"""
	for span in list(text.spans):
		style = Style.parse(span.style) if isinstance(span.style, str) else span.style
		if style.link:
			text.stylize(open_on_click(link_target(style.link)), span.start, span.end)
	for match in WEB_ADDRESS.finditer(text.plain):
		text.stylize(open_on_click(match.group()), match.start(), match.end())
	return text

def launch(command):
	"""Start `command` apart from 42pal: it goes on if 42pal stops, and says nothing."""
	subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL, start_new_session=True)

# The programs that put a text in the clipboard, the first one found is used:
# many terminals (GNOME Terminal among them) ignore the clipboard sequence
# that textual sends.
CLIPBOARD_COMMANDS = [
	["wl-copy"],
	["xclip", "-selection", "clipboard"],
	["xsel", "--clipboard", "--input"],
	["pbcopy"],
]

def capture_console():
	"""The console the shells print to: kept as text with colors, for the screens."""
	return Console(file=io.StringIO(), force_terminal=True, color_system="truecolor", width=100)

class Logo(Static):
	"""The 42pal logo; its gradient moves slowly. One line on a small terminal."""

	def on_mount(self):
		self.shift = 0
		self.paint()
		self.set_interval(0.12, self.paint)

	def paint(self):
		self.shift += 1
		lines = ["4 2 p a l"] if self.screen.has_class("-compact") else LOGO
		text = Text()
		for row, line in enumerate(lines):
			for col, char in enumerate(line):
				text.append(char, style=GRADIENT[((col + row * 2 - self.shift) // 4) % len(GRADIENT)])
			if row < len(lines) - 1:
				text.append("\n")
		self.update(text)

class IntroScreen(Screen):
	"""A screen with the logo and a card: they come in with a short animation."""

	def on_resize(self, event):
		self.set_class(event.size.height < COMPACT_HEIGHT, "-compact")

	def animate_in(self):
		"""The logo drops in, the card rises, the texts appear one after the other.

		Not when the animations are off (TEXTUAL_ANIMATIONS=none, or the tests).
		"""
		if self.app.animation_level == "none":
			return
		logo = self.query_one(".logo")
		logo.styles.offset = (0, -4)
		logo.styles.opacity = 0.0
		logo.styles.animate("offset", ScalarOffset.from_offset((0, 0)), duration=0.6, easing="out_back")
		logo.styles.animate("opacity", 1.0, duration=0.5)
		# The card rises from below; no fading: the opacity would break its background.
		card = self.query_one(".card")
		card.styles.offset = (0, 3)
		card.styles.animate("offset", ScalarOffset.from_offset((0, 0)), duration=0.5,
			easing="out_cubic", delay=0.15)
		for delay, widget in zip((0.15, 0.45, 0.6), self.query(".tagline, .details, .hints")):
			widget.styles.opacity = 0.0
			self.set_timer(delay, lambda w=widget: w.styles.animate("opacity", 1.0, duration=0.4))

class LoginScreen(IntroScreen):
	"""The fake login, like at the exam: any password, never checked nor kept.

	It is dismissed with the login typed (the user name by default).
	"""

	BINDINGS = [("escape", "app.quit", "Quit")]

	def __init__(self, user):
		super().__init__()
		self.user = user

	def compose(self) -> ComposeResult:
		with Vertical(classes="root"):
			yield Static(classes="logo")
			yield Static("examshell", classes="tagline")
			with Vertical(classes="card"):
				yield Static(t("login"), classes="field-label")
				yield Input(value=self.user, id="login")
				yield Static(t("password"), classes="field-label")
				yield Input(password=True, id="password")
			yield Static(hints([("⏎", N_("next")), ("esc", N_("quit"))]), classes="hints")

	def on_mount(self):
		# A Logo widget for the logo: the placeholder was only for the layout.
		self.query_one(".logo").remove()
		self.query_one(".root").mount(Logo(classes="logo"), before=0)
		self.query_one(".card").border_title = f" {t('Log in')} "
		self.query_one("#login", Input).focus()
		self.call_after_refresh(self.animate_in)

	def on_input_submitted(self, event):
		if event.input.id == "login":
			self.query_one("#password", Input).focus()
			return
		# The password is dropped at once: not checked, not stored.
		event.input.value = ""
		self.dismiss(self.query_one("#login", Input).value.strip() or self.user)

class PassphraseScreen(Screen):
	"""The passphrase of the cheat menu, hidden as it is typed; dismissed with it ("" for Esc)."""

	BINDINGS = [("escape", "cancel", "Back")]

	def compose(self) -> ComposeResult:
		with Vertical(classes="root"):
			with Vertical(classes="card"):
				yield Static("passphrase", classes="field-label")
				yield Input(password=True, id="passphrase")
			yield Static(hints([("⏎", "unlock"), ("esc", "back")]), classes="hints")

	def on_mount(self):
		self.query_one(".card").border_title = " Cheat "
		self.query_one("#passphrase", Input).focus()

	def on_input_submitted(self, event):
		passphrase = event.value
		event.input.value = ""
		self.dismiss(passphrase)

	def action_cancel(self):
		self.dismiss("")

class MenuScreen(IntroScreen):
	"""A menu: a choice per item, then Back (or Quit in the first menu).

	items are (value, title, meta, details): meta is the grey line under the
	title, details the text shown under the card while the item is
	highlighted. The screen is dismissed with the value of the item chosen,
	or BACK.
	"""

	BINDINGS = [
		("escape", "back", "Back"),
		("q", "app.quit", "Quit"),
		("j", "move(1)", "Down"),
		("k", "move(-1)", "Up"),
	]

	def __init__(self, title, items, first, highlight=0, last=None, subtitle=TAGLINE):
		super().__init__()
		self.title = title
		self.subtitle = subtitle
		self.items = list(items)
		self.first = first
		self.highlight = highlight
		# last: (label, details) of the last choice, instead of Quit or Back.
		self.last_label, self.last_details = last or (
			(N_("Quit"), N_("Quit 42pal.")) if first else (N_("Back"), N_("Back to the menu before.")))

	def compose(self) -> ComposeResult:
		with Vertical(classes="root"):
			yield Logo(classes="logo")
			yield Static(t(self.subtitle), classes="tagline")
			with Vertical(classes="card"):
				options = [Option(option_label(title, meta), id=str(index))
					for index, (_, title, meta, _) in enumerate(self.items)]
				options.append(None)
				options.append(Option(Text(t(self.last_label), style="dim"), id="back"))
				yield OptionList(*options)
			yield Static(classes="details")
			# Esc chooses the last choice: it quits only when that choice is Quit.
			yield Static(hints([("↑↓ jk", N_("move")), ("⏎", N_("choose")),
				("esc", N_("quit") if self.last_label == "Quit" else N_("back")), ("q", N_("quit"))]), classes="hints")

	def on_mount(self):
		self.query_one(".card").border_title = f" {self.title} "
		menu = self.query_one(OptionList)
		menu.highlighted = self.highlight
		menu.focus()
		self.call_after_refresh(self.animate_in)

	def action_move(self, step):
		menu = self.query_one(OptionList)
		menu.action_cursor_down() if step > 0 else menu.action_cursor_up()

	def action_back(self):
		self.dismiss(BACK)

	def on_option_list_option_highlighted(self, event):
		details = self.query_one(".details", Static)
		if event.option.id == "back":
			details.update(self.last_details)
		else:
			details.update(self.items[int(event.option.id)][3])
		details.styles.opacity = 0.3
		details.styles.animate("opacity", 1.0, duration=0.25)

	def on_option_list_option_selected(self, event):
		if event.option.id == "back":
			self.dismiss(BACK)
		else:
			self.dismiss(self.items[int(event.option.id)][0])

class Activity:
	"""The spinner of a grading, for the session screen: update(text) shows a text.

	`show` is called with the text, then with None at the end; the shells
	use it from the thread that grades.
	"""

	def __init__(self, show, text):
		self.show = show
		self.text = text

	def __enter__(self):
		self.show(self.text)
		return self

	def update(self, text):
		self.show(text)

	def __exit__(self, *error):
		self.show(None)

class SelectableLog(RichLog):
	"""The log of a session, whose text can be selected with the mouse.

	RichLog keeps its lines already drawn, with their colors: the selection
	is taken from their text, and drawn over them.
	"""

	def get_selection(self, selection):
		text = "\n".join(line.text.rstrip() for line in self.lines)
		return selection.extract(text), "\n"

	def selection_updated(self, selection):
		self.refresh()

	def render_line(self, y):
		strip = super().render_line(y)
		line = self.scroll_offset.y + y
		if line >= len(self.lines):
			return strip
		# Where the line is in the text: textual needs it to know what the mouse selects.
		strip = strip.apply_offsets(self.scroll_offset.x, line)
		selection = self.text_selection
		span = selection.get_span(line) if selection is not None else None
		if span is None:
			return strip
		start, end = span
		if end == -1:
			end = len(self.lines[line].text.rstrip())
		start = max(0, start - self.scroll_offset.x)
		end = min(strip.cell_length, end - self.scroll_offset.x)
		if start >= end:
			return strip
		before, selected, after = strip.divide([start, end, strip.cell_length])
		# Only the background of the selection, over each piece: its own
		# background would hide it below, and its text keeps its color.
		style = Style(bgcolor=self.screen.get_component_rich_style("screen--selection").bgcolor)
		selected = Strip([Segment(piece, (piece_style or Style()) + style, control)
			for piece, piece_style, control in selected], selected.cell_length)
		return Strip.join([before, selected, after])

class ScreenShellMixin:
	"""What the shells change on a screen: the subject goes to its own pane.

	activity is set by the session screen: a function that shows the text of
	the spinner while grading, or hides it with None.
	"""

	activity = None

	def show_subject(self):
		# Only written: the session screen shows it in its pane.
		self.workspace.give_subject(self.variant)

	def _status(self, text):
		return Activity(self.activity or (lambda text: None), text)

class ScreenShell(ScreenShellMixin, Shell):
	"""The examshell, for the full-screen interface."""

class ScreenPracticeShell(ScreenShellMixin, PracticeShell):
	"""The practice shell, for the full-screen interface."""

class CommandLine(Input):
	"""The command line of a session: one line at a time, even when pasting.

	Ctrl+V pastes the clipboard of the app, which holds the whole report
	after r: only its first line, like a paste from the terminal.
	"""

	def action_paste(self):
		lines = self.app.clipboard.splitlines()
		if lines:
			start, end = self.selection
			self.replace(lines[0], start, end)

# What the session screen ends with when the student goes back to the menus.
BACK_TO_MENUS = object()

class FolderSuggester(Suggester):
	"""Completes a folder as it is typed (→ takes it), like Tab in a shell."""

	def __init__(self):
		super().__init__(use_cache=False, case_sensitive=True)

	async def get_suggestion(self, value):
		return suggest_folder(value)

class FolderScreen(Screen):
	"""The folder of the project to test: typed, or chosen in the list below, which follows what is typed.

	With nothing typed, the list gives the folders of the project found in
	`root` (the home folder), as they are found, the last one tested first.
	With a path, it gives the folders in it that start with what is typed
	(★ for those of the project, .. to go up). ↑↓ move in the list; Enter
	opens the folder highlighted, or tests it when it is one of the project;
	Enter after typing tests the folder typed. Tab (or →) completes.
	Dismissed with the folder (a Path that exists), or None with Esc.
	"""

	BINDINGS = [
		("escape", "cancel", "Back"),
		("up", "move(-1)", "Up"),
		("down", "move(1)", "Down"),
		("tab", "open", "Open"),
	]
	# The folders shown at most below the path.
	SHOWN = 200

	def __init__(self, tester, default=None, root=None, last=None):
		super().__init__()
		self.tester = tester
		self.default = default or ""
		self.root = root
		self.last = Path(last) if last else None
		# (label, path, is the project) of each line of the list, and the projects found so far.
		self.entries = []
		self.found = [self.last] if self.last and self.last.is_dir() else []
		self.searching = True
		# True once ↑↓ moved in the list: Enter takes the line highlighted, not what is typed.
		self.in_list = False

	def compose(self) -> ComposeResult:
		with Vertical(classes="root"):
			yield Static(t(self.tester.summary), classes="tagline")
			with Vertical(classes="card"):
				yield Static(t("Folder of your {project}", project=self.tester.project), classes="field-label")
				yield Input(value=self.default, id="folder", suggester=FolderSuggester())
				yield Static("", id="folder-status")
				yield OptionList(id="folders")
			yield Static(hints([("↑↓", N_("choose")), ("⏎", N_("open or test")), ("tab", N_("complete")),
				("esc", N_("back"))]), classes="hints")

	def on_mount(self):
		self.query_one(".card").border_title = f" {self.tester.name} "
		folder = self.query_one("#folder", Input)
		folder.focus()
		folder.cursor_position = len(folder.value)
		self.refresh_list()
		self.search()

	@work(thread=True, exclusive=True, group="search")
	def search(self):
		"""Look for the folders of the project; each one shows as soon as it is found."""
		for path in testers_core.iter_projects(self.tester, self.root):
			self.app.call_from_thread(self.add_found, path)
		self.app.call_from_thread(self.search_done)

	def add_found(self, path):
		if path not in self.found:
			self.found.append(path)
			if not self.query_one("#folder", Input).value.strip():
				self.refresh_list()

	def search_done(self):
		self.searching = False
		if not self.query_one("#folder", Input).value.strip():
			self.refresh_list()

	def entry_labels(self):
		"""(label, path) of each line of the list, for the tests."""
		return [(label, path) for label, path, _ in self.entries]

	def has_marker(self, path):
		return bool(self.tester.marker) and (path / self.tester.marker).is_file()

	def refresh_list(self):
		"""The list below the path, and the line that says what Enter does."""
		typed = self.query_one("#folder", Input).value
		status = ""
		if not typed.strip():
			self.entries = [(display.short_path(path), path, True) for path in self.found]
			self.entries.append(("~/", Path.home(), False))
			count = len(self.found)
			if self.searching:
				status = t("Looking for your {project}… {count} found", project=self.tester.project, count=count)
			elif not count:
				status = t("No {project} found: type its path, or browse from ~/.", project=self.tester.project)
		else:
			path = Path(typed).expanduser()
			if typed.endswith("/") and path.is_dir():
				parent, start = path, ""
				self.entries = [("..", path.parent, False)] if path.parent != path else []
			else:
				parent, start = path.parent, path.name
				self.entries = []
			self.entries += [(("★ " if self.has_marker(child) else "") + child.name + "/", child,
				self.has_marker(child)) for child in self.subfolders(parent, start)]
			if path.is_dir() and self.has_marker(path):
				status = t("✓ {marker} here: Enter tests this folder", marker=self.tester.marker)
		menu = self.query_one("#folders", OptionList)
		menu.clear_options()
		menu.add_options([Option(Text(label, style="bold #a5b4fc" if project else ""), id=str(index))
			for index, (label, _, project) in enumerate(self.entries)])
		menu.highlighted = None
		self.in_list = False
		self.query_one("#folder-status", Static).update(Text(status, style="#86efac" if status.startswith("✓")
			else "#9ca3af"))

	def subfolders(self, parent, start):
		"""The folders in `parent` whose name starts with `start` (hidden ones only when a dot is typed)."""
		try:
			names = sorted(os.listdir(parent))
		except OSError:
			return []
		folders = [parent / name for name in names if name.startswith(start)
			and (start.startswith(".") or not name.startswith(".")) and (parent / name).is_dir()]
		return folders[:self.SHOWN]

	def on_input_changed(self, event):
		self.refresh_list()

	def action_move(self, step):
		menu = self.query_one("#folders", OptionList)
		if not self.entries:
			return
		if menu.highlighted is None:
			menu.highlighted = 0 if step > 0 else len(self.entries) - 1
		else:
			menu.highlighted = max(0, min(len(self.entries) - 1, menu.highlighted + step))
		self.in_list = True

	def highlighted_entry(self):
		index = self.query_one("#folders", OptionList).highlighted
		return self.entries[index] if index is not None and index < len(self.entries) else None

	def action_open(self):
		"""Tab: the folder highlighted (or the first one) goes in the path, to look into it."""
		entry = self.highlighted_entry() or (self.entries[0] if self.entries and self.entries[0][0] != ".." else None)
		if entry is not None:
			self.open(entry[1])

	def open(self, path):
		folder = self.query_one("#folder", Input)
		folder.value = display.short_path(path).rstrip("/") + "/" if str(path) != "/" else "/"
		folder.cursor_position = len(folder.value)

	def choose(self, entry):
		"""A line of the list: tested when it is a folder of the project, else opened."""
		_, path, project = entry
		if project:
			self.dismiss(path)
		else:
			self.open(path)

	def on_option_list_option_selected(self, event):
		self.choose(self.entries[int(event.option.id)])

	def on_input_submitted(self, event):
		entry = self.highlighted_entry()
		if self.in_list and entry is not None:
			self.choose(entry)
			return
		typed = event.value.strip()
		if not typed:
			return
		path = Path(typed).expanduser()
		path = (path if path.is_absolute() else Path.cwd() / path).resolve()
		if not path.is_dir():
			self.query_one("#folder-status", Static).update(Text(t("No folder here: {path}",
				path=display.short_path(path)), style="#f87171"))
			return
		self.dismiss(path)

	def action_cancel(self):
		self.dismiss(None)

class TesterScreen(Screen):
	"""A tester at work on a project, then its results in the log.

	run(tester, project, on_progress) runs it and returns its report, in a
	thread: the screen stays alive, and shows what the tester finds as it
	comes (on_progress). r runs it again, f asks another folder (dismissed
	with "folder"), Esc goes back (dismissed with None).
	"""

	# The counter changes at most this often (seconds); a check or a failure shows at once.
	PROGRESS_EVERY = 0.1

	BINDINGS = [
		("escape", "back", "Back"),
		("r", "again", "Run again"),
		("f", "folder", "Another folder"),
		("ctrl+shift+c", "screen.copy_text", "Copy"),
	]

	def __init__(self, tester, project, run):
		super().__init__()
		self.tester = tester
		self.project = project
		self.run = run
		self.busy = False
		self.report = None
		self.shown_at = 0.0
		# The group of the last check shown live, and whether the failures have their title yet.
		self.live_group = None
		self.live_failures = False

	def compose(self) -> ComposeResult:
		yield Static(id="header")
		# The long lines wrap: no horizontal scroll bar.
		yield SelectableLog(id="log", wrap=True, min_width=0, markup=False, highlight=False)
		yield Static(id="activity")
		yield Static(hints([("r", N_("run again")), ("f", N_("another folder")), ("esc", N_("back")),
			("ctrl+q", N_("leave"))]), id="session-hints")

	def on_mount(self):
		self.query_one("#header", Static).border_title = f" 42pal · {t('Testers')} "
		self.refresh_header()
		self.query_one("#log").border_title = " log "
		self.action_again()

	def refresh_header(self):
		"""The tester, the folder, and the verdict once there is one: the log opens at its top."""
		text = Text(self.tester.name, style="bold #e0e7ff")
		text.append("   " + display.short_path(self.project), style="#9ca3af")
		if self.report is not None and not self.busy:
			text.append("   ")
			text.append_text(display.tester_verdict(self.report))
		self.query_one("#header", Static).update(text)

	def action_again(self):
		if self.busy:
			return
		self.busy = True
		self.refresh_header()
		self.query_one("#log", RichLog).clear()
		self.live_group = None
		self.live_failures = False
		activity = self.query_one("#activity", Static)
		activity.set_class(True, "-busy")
		activity.update("⠿ " + t("{tester} is testing {project}…", tester=self.tester.name,
			project=display.short_path(self.project)))
		self.run_in_background()

	@work(thread=True, exclusive=True)
	def run_in_background(self):
		report = self.run(self.tester, self.project, self.progress_from_thread)
		self.app.call_from_thread(self.show_report, report)

	def progress_from_thread(self, progress, item):
		"""From the thread of the tester: a check or a failure at once, the counter now and then."""
		now = time.monotonic()
		shows_lines = item is not None and (isinstance(item, testers_core.Check) or item.bad)
		last = progress.tests_total and progress.tests_done == progress.tests_total
		if not shows_lines and not last and now - self.shown_at < self.PROGRESS_EVERY:
			return
		self.shown_at = now
		text = display.tester_progress(self.tester, progress)
		self.app.call_from_thread(self.show_progress, text, item)

	def show_progress(self, text, item):
		"""The counter in the activity line; the check or the failed test in the log."""
		self.query_one("#activity", Static).update("⠿ " + text)
		if item is None:
			return
		log = self.query_one("#log", RichLog)
		if isinstance(item, testers_core.Check) and self.live_group is None:
			log.write(Text(t("The subject"), style="bold"))
		if isinstance(item, testers_core.TestCase) and not self.live_failures:
			self.live_failures = True
			log.write(Text("\n" + t("Failed so far"), style="bold"))
		lines, self.live_group = display.tester_live_lines(self.tester, item, self.live_group)
		for line in lines:
			log.write(line)

	def show_report(self, report):
		self.report = report
		self.query_one("#activity", Static).set_class(False, "-busy")
		log = self.query_one("#log", RichLog)
		for line in display.tester_report(report, self.tester, self.project):
			log.write(clickable(line) if isinstance(line, Text) else line)
		log.scroll_home(animate=False)
		self.busy = False
		self.refresh_header()

	def action_folder(self):
		if not self.busy:
			self.dismiss("folder")

	def action_back(self):
		# Not while the tester runs: its thread writes to this screen at the end.
		if not self.busy:
			self.dismiss(None)

class SessionScreen(Screen):
	"""An exam (or a practice): the header, the subject, the log, the command line.

	The commands are typed like in the examshell; the shell runs them and
	what it prints goes to the log. A grading runs in a thread, so that the
	screen stays alive. When the exam is over, Enter leaves; the screen is
	dismissed with the last thing printed (the summary). PgUp and PgDn
	scroll the subject while typing; up and down bring back the commands
	typed before, like in a shell.
	"""

	BINDINGS = [
		("pageup", "scroll_subject(-1)", "Subject up"),
		("pagedown", "scroll_subject(1)", "Subject down"),
		("up", "history(-1)", "Previous command"),
		("down", "history(1)", "Next command"),
		# Copies the selection like Ctrl+C, in the terminals that let it through;
		# with nothing selected, it does nothing (Ctrl+C would leave).
		("ctrl+shift+c", "screen.copy_text", "Copy"),
		# Back to the menus, after a wrong click in them (asks first).
		("escape", "back", "Back to the menus"),
	]

	def __init__(self, shell, practice=False):
		super().__init__()
		self.shell = shell
		self.practice = practice
		self.commands = PRACTICE_COMMANDS if practice else COMMANDS
		self.shortcuts = PRACTICE_SHORTCUTS if practice else SHORTCUTS
		self.prompt = "practice>" if practice else "examshell>"
		self.shown_variant = None
		self.busy = False
		self.over = False
		self.final = ""
		# The commands typed, the oldest first; while going through them, the
		# place shown (None: not going through) and what was being typed.
		self.history = []
		self.history_place = None
		self.draft = ""

	def compose(self) -> ComposeResult:
		yield Static(id="header")
		with Container(id="body"):
			with VerticalScroll(id="subject-pane"):
				yield Static(id="subject")
			# The shell already prints at the width of the log (see fit_console):
			# only what is wider (a long command typed) wraps. No minimum width:
			# no horizontal scroll bar when the log is narrow.
			yield SelectableLog(id="log", wrap=True, min_width=0, markup=False, highlight=False)
		yield Static(id="activity")
		letters = ", ".join(f"{letter} {command}" for letter, command in self.shortcuts.items())
		# max_length: a command is short, whatever is typed or pasted.
		yield CommandLine(id="command", max_length=200,
			placeholder=t("{prompt} type a command ({letters})", prompt=self.prompt, letters=letters),
			suggester=SuggestFromList(list(self.commands), case_sensitive=False))
		# The one-letter commands are in the placeholder of the command line.
		yield Static(hints([("↑↓", N_("history")), ("→", N_("complete")), ("pgup pgdn", N_("subject")),
			("ctrl+c ctrl+shift+c", N_("copy")), ("r", N_("report")), ("esc", N_("back")), ("ctrl+q", N_("leave"))]),
			id="session-hints")

	def on_mount(self):
		self.query_one("#log").border_title = " log "
		# The shell shows the spinner of a grading on this screen.
		self.shell.activity = lambda text: self.app.call_from_thread(self.show_activity, text)
		self.refresh_subject()
		self.refresh_header()
		self.set_interval(1, self.tick)
		self.query_one("#command", Input).focus()

	def on_resize(self, event):
		self.set_class(event.size.width >= WIDE_WIDTH, "-wide")

	def action_history(self, step):
		"""Up (-1) and down (1): the commands typed before; below the last, the draft."""
		if not self.history or self.busy or self.over:
			return
		command = self.query_one("#command", Input)
		if self.history_place is None:
			if step > 0:
				return
			self.draft = command.value
			self.history_place = len(self.history)
		self.history_place = max(0, self.history_place + step)
		if self.history_place >= len(self.history):
			self.history_place = None
			value = self.draft
		else:
			value = self.history[self.history_place]
		command.value = value
		command.cursor_position = len(value)

	def action_scroll_subject(self, step):
		pane = self.query_one("#subject-pane")
		pane.scroll_page_down() if step > 0 else pane.scroll_page_up()

	def fit_console(self):
		"""What the shell prints is as wide as the log."""
		width = self.query_one("#log").scrollable_content_region.width
		self.shell.console.width = max(40, width - 1)

	def refresh_subject(self):
		"""Show the current subject in its pane, when it is a new one."""
		variant = self.shell.variant
		if variant is None or variant.id == self.shown_variant:
			return
		self.shown_variant = variant.id
		workspace = self.shell.workspace
		subject = workspace.subject_file(variant)
		if not subject.is_file():
			subject = workspace.subjects / variant.name / "subject.en.txt"
		rendu = workspace.rendu / variant.name
		# The paths open with a click: the subject in an editor, the rendu in
		# the file manager. One Text: textual can only select in a single text,
		# for the prototypes and headers to be copied.
		content = Text()
		content.append(t("Read it") + "  ", style="dim")
		content.append(display.short_path(subject), style=open_on_click(str(subject)))
		content.append("\n" + t("Hand in") + "  ", style="dim")
		content.append(f"{display.short_path(rendu)}/", style=open_on_click(str(rendu)))
		content.append("\n\n")
		# The words of the variant stand out (see display.subject_text).
		content.append_text(display.subject_text(variant, subject.read_text(encoding="utf-8")))
		self.query_one("#subject", Static).update(content)
		pane = self.query_one("#subject-pane")
		pane.border_title = f" {variant.name} "
		pane.scroll_home(animate=False)

	def refresh_header(self):
		"""The exam, the level, the time and the grade, or how the practice goes."""
		shell = self.shell
		header = self.query_one("#header", Static)
		text = Text()
		if self.practice:
			header.border_title = f" 42pal · {t('practice')} "
			text.append(shell.theme, style="bold #e0e7ff")
			text.append("   " + t("{passed} passed · {attempts} grademe", passed=shell.passed, attempts=shell.attempts),
				style="#9ca3af")
			header.update(text)
			return
		exam = shell.exam
		header.border_title = f" 42pal · {exam.title} "
		text.append(t("level {level} of {count}", level=shell.level, count=exam.level_count), style="bold #e0e7ff")
		text.append("   " + (t("exam mode") if shell.mode == "exam" else t("revision mode")), style="#9ca3af")
		text.append("   " + t("grade {grade}/100", grade=display.points(shell.grade)), style="bold #a5b4fc")
		if shell.started_at is not None:
			left = shell._time_left()
			if shell.mode == "exam":
				style = "bold #fbbf24" if left < 10 * 60 else "#e0e7ff"
				text.append("   " + t("time left {duration}", duration=display.duration(max(0, left))), style=style)
			else:
				elapsed = shell.clock() - shell.started_at
				text.append("   " + t("time spent {duration}", duration=display.duration(elapsed)), style="#9ca3af")
		wait = shell._wait_left()
		if wait > 0:
			text.append("   " + t("next grademe in {duration}", duration=display.duration(wait)), style="#fbbf24")
		header.update(text)

	def tick(self):
		"""Each second: the header; in exam mode, the end when the time is up."""
		if self.over:
			return
		self.refresh_header()
		if not self.practice and not self.busy and self.shell._time_left() <= 0:
			self.fit_console()
			self.finish_command(*self.capture(""))

	def show_activity(self, text):
		"""Show the text of the spinner while grading, or hide it (None)."""
		activity = self.query_one("#activity", Static)
		activity.set_class(text is not None, "-busy")
		if text is not None:
			activity.update(f"⠿ {text}")

	def capture(self, command):
		"""Run `command` in the shell; return (over, what it printed, with colors)."""
		console = self.shell.console
		console.begin_capture()
		try:
			over = self.shell.handle(command)
		finally:
			printed = console.end_capture()
		return over, printed

	def on_input_submitted(self, event):
		command = event.value.strip()
		event.input.value = ""
		if self.over:
			self.dismiss(self.final)
			return
		if self.busy:
			return
		# Kept for up and down; the same command twice in a row, once.
		if command and (not self.history or self.history[-1] != command):
			self.history.append(command)
		self.history_place = None
		log = self.query_one("#log", RichLog)
		log.write(Text(f"{self.prompt} {command}", style="bold #a5b4fc"))
		# Here, not in the grading thread: the widgets belong to the screen.
		self.fit_console()
		if self.shortcuts.get(command, command) == "grademe":
			self.busy = True
			event.input.disabled = True
			self.grade_in_background(command)
		elif self.shortcuts.get(command, command) == "back":
			self.action_back()
		elif command == "cheat" and not self.practice:
			# Hidden: the menus of the cheat menu are screens of the app.
			self.app.cheat_flow(self)
		else:
			before = self.shell.last_report
			self.finish_command(*self.capture(command))
			# A new report goes to the clipboard too, ready to paste in an issue.
			if self.shell.last_report is not None and self.shell.last_report != before:
				self.app.copy_to_clipboard(self.shell.last_report.read_text(encoding="utf-8"))

	def action_back(self):
		"""Escape (or back): back to the menus once the student says so; Escape again stays."""
		if self.busy or self.over:
			return

		def answer(value):
			if value == "menus":
				self.dismiss(BACK_TO_MENUS)

		item = ("menus", t("Back to the menus"), t("to choose again"), self.shell.back_consequence())
		self.app.push_screen(MenuScreen(t("Back to the menus?"), [item], first=False,
			last=(t("Stay here"), t("Go on where you were."))), answer)

	@work(thread=True, exclusive=True)
	def grade_in_background(self, command):
		"""A grading takes a while: it runs in a thread, the screen stays alive."""
		over, printed = self.capture(command)
		self.app.call_from_thread(self.finish_command, over, printed)

	def finish_command(self, over, printed):
		"""Show what the command printed; at the end of the exam, wait for Enter."""
		self.busy = False
		self.show_activity(None)
		command = self.query_one("#command", Input)
		command.disabled = False
		command.focus()
		log = self.query_one("#log", RichLog)
		if printed.strip():
			log.write(clickable(Text.from_ansi(printed.rstrip("\n"))))
		self.refresh_subject()
		self.refresh_header()
		if over:
			self.over = True
			self.final = printed
			command.placeholder = t("Press Enter to leave")
			log.write(Text(t("Press Enter to leave."), style="dim"))

class Pal42App(App):
	"""42pal in full screen: login, menus, then the exam (or the practice).

	shell is a ScreenShell (or a ScreenPracticeShell with practice=True). The
	app exits with what the session printed last (the summary), for the
	terminal once the screen is gone.
	"""

	CSS_PATH = "tui.tcss"
	ENABLE_COMMAND_PALETTE = False
	TITLE = "42pal"
	# Ctrl+C copies the text selected (textual's screens do it first); with
	# nothing selected, it leaves, like Ctrl+Q.
	BINDINGS = [("ctrl+c", "quit", "Leave"), ("ctrl+q", "quit", "Leave")]
	# The clipboard programs to try (the tests put their own).
	clipboard_commands = CLIPBOARD_COMMANDS

	# How a command is started apart (the tests put their own).
	launch = staticmethod(launch)
	# The check for a newer 42pal started at launch, and the function that pulls it.
	update_check = None
	# Where Settings keeps the language (None: ~/.42pal/settings.json; the tests give their own).
	settings_file = None
	updater = staticmethod(apply_update)

	def __init__(self, shell, practice=False, theme=None, user=None):
		super().__init__()
		self.shell = shell
		self.practice = practice
		self.practice_theme = theme
		self.user = user or getpass.getuser()

	def on_mount(self):
		if self.practice:
			self.practice_flow()
		else:
			self.exam_flow()

	def copy_to_clipboard(self, text):
		"""Copy `text`: through the terminal, and with a clipboard program if there is one."""
		super().copy_to_clipboard(text)
		self.copy_with_program(text)
		lines = text.count("\n") + 1
		self.notify(t("Copied: 1 line") if lines == 1 else t("Copied: {count} lines", count=lines), timeout=2)

	def copy_with_program(self, text):
		"""Give `text` to the first clipboard program found (xclip, xsel, wl-copy...)."""
		for command in self.clipboard_commands:
			if shutil.which(command[0]) is None:
				continue
			try:
				subprocess.run(command, input=text, text=True, timeout=3,
					stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			except (OSError, subprocess.TimeoutExpired):
				continue
			return

	def action_open_link(self, target):
		"""Open a file, a folder or a web page with the default application of the system."""
		program = "open" if sys.platform == "darwin" else "xdg-open"
		if self.launch is launch and shutil.which(program) is None:
			self.notify(t("Cannot open it here: {program} is missing. {target}", program=program, target=target),
				severity="warning")
			return
		self.launch([program, target])
		shown = target if WEB_ADDRESS.match(target) else display.short_path(target)
		self.notify(t("Opening {target}", target=shown), timeout=3)

	async def ask(self, title, items, first, highlight=0, last=None, subtitle=TAGLINE):
		"""Show a menu; return the value of the item chosen, or BACK."""
		return await self.push_screen(MenuScreen(title, items, first, highlight, last, subtitle),
			wait_for_dismiss=True)

	async def ask_progress(self):
		"""The progress: the summary under the logo, the weak themes as choices; the theme, or None."""
		store = self.shell.store
		history, grades = store.history(), store.grades()
		_, themes = self.shell._catalog()
		exams = ", ".join(f"{row.title} {display.points(row.best)}/100" for row in exam_rows(history))
		items = [(row.theme, row.theme, display.theme_score(row),
			(t(themes[row.theme].skill) if row.theme in themes else "") + ". " + t("Practise it now."))
			for row in weak_themes(grades) if row.theme in themes]
		if not items:
			items = [("none", t("No weak theme"), t("every theme passed"), t("Nothing to practise again for now."))]
		value = await self.ask(t("Progress"), items, first=False, subtitle=summary(history, grades),
			last=(t("Back"), t("Best grades: {exams}.", exams=exams) if exams else t("Back to the menu before.")))
		return None if value in (BACK, "none") else value

	@work
	async def cheat_flow(self, screen):
		"""The cheat menu, from the session screen: the passphrase, then the menus of the pack.

		Back in a menu goes to the menu before; in the first one, back to the
		exam. What the choices print goes to the log of the session screen.
		"""
		shell = screen.shell
		passphrase = await self.push_screen(PassphraseScreen(), wait_for_dismiss=True)
		# PBKDF2 is slow on purpose: not in the loop of the screens.
		menu = await asyncio.to_thread(cheat.unlock, passphrase, shell.cheat_pack) if passphrase else None
		if menu is None:
			screen.finish_command(False, "Wrong passphrase.\n" if passphrase else "")
			return
		current, before, printed = menu.first_menu(shell), [], ""
		while True:
			title, items = current
			last = ("Back to the exam", "Close the cheat menu.") if not before else None
			value = await self.ask(title, items, first=not before, last=last)
			if value is BACK:
				if not before:
					break
				current = before.pop()
				continue
			screen.fit_console()
			shell.console.begin_capture()
			try:
				step = menu.choose(shell, value)
				if step.text:
					shell.console.print(step.text)
			finally:
				printed += shell.console.end_capture()
			if step.over or not step.menu:
				screen.finish_command(step.over, printed)
				return
			before.append(current)
			current = step.menu
		screen.finish_command(False, printed)

	def run_quietly(self, action):
		"""Run action() in the shell; what it printed is shown as a notification."""
		console = self.shell.console
		console.begin_capture()
		try:
			result = action()
		finally:
			printed = console.end_capture()
		if printed.strip():
			self.notify(Text.from_ansi(printed).plain.strip(), timeout=8)
		return result

	# The examshell, when a practice took its place (Back gives it back).
	exam_shell = None

	@work
	async def exam_flow(self):
		shell = self.exam_shell = self.shell
		shell.user = await self.push_screen(LoginScreen(self.user), wait_for_dismiss=True)
		if await self.offer_update():
			return
		resumed = False
		if self.run_quietly(shell.restore_saved):
			choice = await self.ask_resume()
			if choice is BACK:
				return
			resumed = choice == "resume"
		while True:
			if resumed:
				self.shell.show_subject()
			elif not await self.start_from_menus():
				return
			resumed = False
			if not await self.run_session():
				return

	async def start_from_menus(self):
		"""The menus until an exam or a practice starts (True); False when the app quits."""
		shell = self.shell
		start = await self.choose_start()
		while start in SIDE_CHOICES:
			if start == SETTINGS:
				await self.settings_flow()
				start = await self.choose_start()
				continue
			if start == TESTERS:
				await self.testers_flow()
				start = await self.choose_start()
				continue
			practice = self.practice_shell()
			if start == PROGRESS:
				theme = await self.ask_progress()
			else:
				theme = await self.choose_practice_theme(practice, first=False)
			if theme is not None:
				# The practice shell takes over: the session screen and the end use it.
				self.shell, self.practice = practice, True
				practice.theme = theme
				self.run_quietly(practice.next_subject)
				return True
			start = await self.choose_start()
		if start is None:
			self.exit()
			return False
		self.run_quietly(lambda: shell.begin(*start))
		return True

	async def settings_flow(self):
		"""Settings: the language of 42pal, each one under its own name; the choice is kept."""
		languages = i18n.languages()
		current = i18n.language()
		items = [(code, name, t("in use") if code == current else "", "")
			for code, name in languages.items()]
		code = await self.ask(t("Language"), items, first=False, highlight=list(languages).index(current))
		if code is not BACK:
			settings.choose_language(code, self.settings_file)

	async def testers_flow(self):
		"""Testers: a tester (downloaded when the student agrees), the folder, its results; Back comes here again."""
		shell = self.shell
		while True:
			items = [(tester, tester.name, tester.project if testers_core.available(tester) else t("Linux only"),
				t(tester.summary)) for tester in shell._testers()]
			tester = await self.ask(t("Testers"), items, first=False)
			if tester is BACK:
				return
			if not testers_core.available(tester):
				self.notify(t("{tester} runs on Linux only.", tester=tester.name), severity="warning")
				continue
			if await self.tester_ready(tester):
				await self.test_folders(tester)

	async def tester_ready(self, tester):
		"""Download the tester, or its new version, when the student agrees; True when it can run."""
		shell = self.shell
		state = testers_core.state(tester, shell.testers_root)
		if state == testers_core.READY:
			return True
		where = f"{testers_core.source(tester, shell.testers_environ)} · {tester.tag}"
		if state == testers_core.MISSING:
			choice = await self.ask(t("Download {tester}?", tester=tester.name), [
				("download", t("Download"), tester.tag,
					t("Once, from {where}; 42pal checks it is the version expected.", where=where)),
			], first=False, last=(t("Back"), t("Back to the testers.")))
		else:
			choice = await self.ask(t("A new version of {tester}", tester=tester.name), [
				("download", t("Update now"), tester.tag, where),
				("later", t("Not now"), t("keep the version installed"), t("You will be asked again next time.")),
			], first=False)
		if choice is BACK:
			return False
		if choice == "later":
			return True
		self.notify(t("Downloading {tester}…", tester=tester.name), timeout=3)
		ok, why = await asyncio.to_thread(testers_core.install, tester, shell.testers_root, shell.testers_environ)
		if not ok:
			self.notify(f"{t('The download failed:')} {why}", severity="error", timeout=10)
			return state == testers_core.OUTDATED
		self.notify(t("{tester} is ready ({tag}).", tester=tester.name, tag=tester.tag), timeout=3)
		return True

	async def test_folders(self, tester):
		"""The folder, then the results; another folder as many times as asked; None at the end."""
		while True:
			last = testers_core.last_project(tester, self.settings_file)
			project = await self.push_screen(FolderScreen(tester, root=self.shell.projects_root, last=last),
				wait_for_dismiss=True)
			if project is None:
				return
			again = await self.push_screen(TesterScreen(tester, project, self.run_tester), wait_for_dismiss=True)
			if again != "folder":
				return

	def run_tester(self, tester, project, on_progress=None):
		"""Run the tester on `project` in the language of 42pal; the folder is kept for the next time."""
		lang = testers_core.tester_language(tester, i18n.language())
		report = testers_core.run(tester, project, lang, self.shell.testers_root, on_progress=on_progress)
		testers_core.remember_project(tester, project, self.settings_file)
		return report

	def practice_shell(self):
		"""A practice shell with the console, workspace and catalog of the examshell."""
		shell = self.shell
		catalog, themes = shell._catalog()
		return ScreenPracticeShell(shell.console, None, shell.workspace, rng=shell.rng,
			catalog=catalog, themes=themes, sleep=shell.sleep, store=shell.store)

	async def offer_update(self):
		"""Offer the newer 42pal found at launch; return True when the app is leaving.

		Update now pulls it, then the app exits with RESTART; a failed pull is
		said, and the app goes on with this version.
		"""
		if self.update_check is None:
			return False
		# result() may wait a little for the check: not in the loop of the screens.
		update = await asyncio.to_thread(self.update_check.result)
		if update is None:
			return False
		commits = (t("{count} new commits, then 42pal starts again", count=update.count) if update.count != 1
			else t("1 new commit, then 42pal starts again"))
		changes = "\n".join(f"· {change[:56]}" for change in update.changes[:3])
		choice = await self.ask(t("A new version of 42pal"), [
			("update", t("Update now"), commits, changes),
			("later", t("Not now"), t("keep this version"), t("You will be asked again next time.")),
		], first=True)
		if choice is BACK:
			self.exit()
			return True
		if choice == "later":
			return False
		self.notify("Updating…", timeout=3)
		ok, why = await asyncio.to_thread(self.updater)
		if not ok:
			self.notify(t("The update failed, nothing was changed: {why}", why=why), severity="error", timeout=10)
			return False
		self.exit(RESTART)
		return True

	async def ask_resume(self):
		"""Resume the saved exam, or start a new one (the saved one is abandoned)."""
		shell = self.shell
		left = shell._time_left()
		time = t("no time limit") if shell.mode == "revision" else t("{duration} left", duration=display.duration(left))
		choice = await self.ask(t("Resume your exam?"), [
			("resume", t("Resume"), f"{shell.exam.title} · {t('level {level}', level=shell.level)} · {time}",
				t("Subject: {subject}. The time kept running while you were away.", subject=shell.variant.name)),
			("new", t("Start a new exam"), t("the exam in progress goes to the history"),
				t("It is kept in the history as abandoned.")),
		], first=True)
		if choice is BACK:
			self.exit()
		elif choice == "new":
			shell.abandon_saved()
		return choice

	async def choose_start(self):
		"""The menus: who, which exam, which mode, which level; None to quit.

		The last choice of each menu goes back to the one before it, skipping
		the steps that needed no menu (a single exam, the level in exam mode).
		Practice chosen in the first menu gives PRACTICE.
		"""
		steps = [self.pick_audience, self.pick_exam, self.pick_mode, self.pick_level]
		chosen = []
		# For each answer in chosen: True if a menu was shown to get it.
		shown = []
		while len(chosen) < len(steps):
			answer, asked = await steps[len(chosen)](chosen, not any(shown))
			if answer in SIDE_CHOICES:
				return answer
			if answer is BACK:
				if not any(shown):
					return None
				while not shown.pop():
					chosen.pop()
				chosen.pop()
				continue
			chosen.append(answer)
			shown.append(asked)
		_, exam, mode, level = chosen
		return exam, mode, level

	async def pick_audience(self, chosen, first):
		by_audience = {}
		for exam in self.shell._exams():
			by_audience.setdefault(exam.audience, []).append(exam)
		audiences = [audience for audience in AUDIENCES if audience in by_audience]
		items = []
		for audience in audiences:
			exams = by_audience[audience]
			meta = exams[0].title if len(exams) == 1 else t("{count} exams", count=len(exams))
			items.append((audience, t(display.AUDIENCE_TEXTS[audience]), meta,
				", ".join(exam.title for exam in exams)))
		if self.shell._can_practise():
			items.append((PRACTICE, t(display.PRACTICE_TEXT), t(display.PRACTICE_SUMMARY),
				t("Subjects of one theme, one after the other: no timer, no wait.")))
		if self.shell.store and self.shell.store.grades():
			items.append((PROGRESS, t(display.PROGRESS_TEXT), t(display.PROGRESS_SUMMARY),
				t("How your exams went, and the themes that fail the most, to practise them.")))
		items.append((TESTERS, t(display.TESTERS_TEXT), t(display.TESTERS_SUMMARY),
			t("Download a tester of your projects and run it here: libfterator for the libft.")))
		items.append((SETTINGS, t(display.SETTINGS_TEXT), display.settings_summary(i18n.languages()[i18n.language()]),
			t("The language of 42pal: the menus, the messages, the traces and the subjects.")))
		return await self.ask(t(display.FIRST_MENU_TITLE), items, first), True

	async def pick_exam(self, chosen, first):
		exams = [exam for exam in self.shell._exams() if exam.audience == chosen[0]]
		if len(exams) == 1:
			return exams[0], False
		items = [(exam, exam.title, display.exam_summary(exam),
			t("{points} points a level, 100 to pass.", points=display.points(exam.points_per_level))
			+ f" {display.exam_tools(exam)}") for exam in exams]
		return await self.ask(t("Choose your exam"), items, first), True

	async def pick_mode(self, chosen, first):
		exam = chosen[1]
		hard = ", ".join(map(display.points, exam.retry["hard"].minutes))
		soft = ", ".join(map(display.points, exam.retry["soft"].minutes))
		items = [
			("exam", t("Exam"), t("the real conditions · {length}", length=display.exam_length(exam.duration_minutes)),
				t("Starts at level 1. Waits after a failed grademe grow fast (minutes): {waits}.", waits=hard)),
			("revision", t("Revision"), t("no time limit · any starting level"),
				t("Waits after a failed grademe stay short (minutes): {waits}.", waits=soft)),
		]
		return await self.ask(f"{exam.title} · {t('mode')}", items, first, highlight=1), True

	async def pick_level(self, chosen, first):
		exam, mode = chosen[1], chosen[2]
		playable = exam.playable_levels
		if mode == "exam":
			return playable[0], False
		points = display.points(exam.points_per_level)
		items = [(level, t("Level {level}", level=level),
			t("{points} points · {count} styles", points=points, count=len(exam.levels[level])),
			t("If you start higher, the levels before it give no points.")) for level in playable]
		return await self.ask(f"{exam.title} · {t('starting level')}", items, first), True

	@work
	async def practice_flow(self):
		"""./42pal practice: a theme, the subjects; Back comes to the themes again."""
		shell = self.shell
		theme = self.practice_theme
		while True:
			if theme is None:
				theme = await self.choose_practice_theme(shell)
				if theme is None:
					self.exit()
					return
			shell.theme = theme
			self.run_quietly(shell.next_subject)
			if not await self.run_session():
				return
			theme = None

	async def choose_practice_theme(self, shell, first=True):
		"""The language (when there are several), then a theme of it; None to leave.

		Back in the theme menu goes back to the language menu. first: the
		outer menu quits; otherwise (practice chosen in the first menu) it goes
		back, and None is returned too.
		"""
		_, themes = shell._catalog()
		languages = shell.practice_languages()
		asks_language = shell.language is None and len(languages) > 1
		while True:
			language = shell.language
			if asks_language:
				items = [(name, display.LANGUAGE_NAMES.get(name, name),
					t("{count} themes", count=count) if count != 1 else t("1 theme"),
					t("Exams: {exams}", exams=", ".join(exam.title for exam in shell._exams() if exam.language == name)))
					for name, count in languages.items()]
				language = await self.ask(t("Choose a language"), items, first=first)
				if language is BACK:
					return None
			items = [(name, name, t(themes[name].skill),
				t("Real levels: {levels}", levels=", ".join(f"{exam} {levels}" for exam, levels in themes[name].exams.items())))
				for name in shell.practisable_themes(language)]
			theme = await self.ask(t("Choose a theme to practise"), items, first=first and not asks_language)
			if theme is not BACK:
				return theme
			if not asks_language:
				return None

	async def run_session(self):
		"""The session screen until the end, then leave with what it printed last; True after Back."""
		final = await self.push_screen(SessionScreen(self.shell, self.practice), wait_for_dismiss=True)
		if final is BACK_TO_MENUS:
			self.back_to_menus()
			return True
		self.exit(final)
		return False

	def back_to_menus(self):
		"""After Back: the exam is left (forgotten, or abandoned after a grademe); a practice just stops."""
		if not self.practice:
			self.run_quietly(self.shell.leave_exam)
		elif self.exam_shell is not None:
			self.shell, self.practice = self.exam_shell, False

def finish_in_terminal(final, shell, practice=False):
	"""After the full screen: the summary stays in the terminal, or how to resume."""
	console = Console()
	if final is RESTART:
		console.print(t("42pal is updated: it starts again."))
		restart()
	if final:
		console.print(Text.from_ansi(final.rstrip("\n")))
	elif not practice and shell.variant is not None and shell.store and shell.store.load():
		console.print(t("Exam stopped: run ./42pal again to resume it."))

def run_exam(workspace, store, update_check=None):
	"""42pal in full screen, on the real terminal; return the exit code.

	update_check: the check for a newer 42pal started at launch, if any.
	"""
	shell = ScreenShell(capture_console(), None, None, workspace=workspace, store=store)
	app = Pal42App(shell)
	app.update_check = update_check
	final = app.run()
	# Practice chosen in the first menu: the app ends with the practice shell.
	finish_in_terminal(final, app.shell, practice=app.practice)
	return 0

def run_practice(workspace, theme=None):
	"""Practice in full screen, on the real terminal; return the exit code.

	A theme with no exercise is said before the screen opens: exit code 1.
	"""
	shell = ScreenPracticeShell(capture_console(), None, workspace, store=SessionStore())
	choices = shell.practisable_themes()
	if theme is not None and theme not in choices:
		Console().print(t("No exercise to practise '{theme}' yet. Themes: {themes}",
			theme=escape(theme), themes=", ".join(choices)))
		return 1
	final = Pal42App(shell, practice=True, theme=theme).run()
	finish_in_terminal(final, shell, practice=True)
	return 0

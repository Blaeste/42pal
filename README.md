# 42pal

An exam trainer for 42 students: it works like the examshell, but every
subject you get is a **variant** of an exercise, drawn at random, so you
train on the skill instead of learning one subject by heart. Your work is
graded on your machine, like the moulinette, with a trace when it fails.

It runs on the campus machines with **nothing to install and no sudo**.

## Install

You need Linux with:

- Python 3.10 or newer (the system `python3` is enough),
- a C compiler called `cc`, and `nm` (binutils),
- optionally `valgrind` (memory leaks) and `git` (to push your rendu).

```sh
git clone https://github.com/Blaeste/42pal.git
cd 42pal
./42pal
```

No `pip`, no virtual environment: the libraries of the display,
[textual](https://github.com/Textualize/textual) and
[rich](https://github.com/Textualize/rich), are copied in `vendor/` (see
[vendor/README.md](vendor/README.md)).

## Take an exam

```sh
./42pal
```

In a terminal, 42pal opens **full screen**: move in the menus with the arrow
keys (or `j` and `k`) and Enter, or with the mouse; `Esc` goes back to the
menu before. During the exam, the screen shows the level, the grade and the
time left (it runs live), the subject (`PgUp` and `PgDn` scroll it), a log of
your commands, and the `examshell>` line where you type them. The paths of
the subject, of your rendu and of the traces, and the web addresses, open with
a click: a file in its default application, a folder in the file manager, a
page in the browser (`xdg-open`, or `open` on macOS). `./42pal --plain` gives
the text interface, line by line; it is also used when the input is not a
terminal (answers sent through a pipe). There, the terminal opens the paths
with a Ctrl+click, if it knows links.

1. **Log in** like at the exam. The login defaults to your user name; the
   password can be anything, it is never checked nor kept.
2. **Say who you are**: piscine (piscineux) or student (cursus). Then
   **choose the exam** among the ones for you: a piscine student picks one
   of the 4 piscine exams; a student gets the Exam Rank 02, the only one so
   far. Then choose the **mode** (see below). Exam mode starts at level 1,
   like the real exam; revision mode asks the **starting level**, among the
   levels that have exercises. Each menu says what its choices mean: the
   levels and length of each exam, the waits of each mode, the points of a
   level. Its last choice goes back to the menu before (Quit in the first
   one).
3. **Read the subject**: it is shown on the screen and written in
   `~/42pal_exam/subjects/<name>/subject.en.txt`.
4. **Write your code** in `~/42pal_exam/rendu/<name>/`.
5. **Type `grademe`** at the `examshell>` prompt.

```
~/42pal_exam/
├── subjects/<name>/subject.en.txt   the subject
├── rendu/<name>/                    your code
└── traces/                          a trace for each grademe
```

### Commands

| Command | Or | What it does |
|---|---|---|
| `grademe` | `g` | grades your work |
| `status` | `s` | exam, level, subject, time spent and left, next grademe |
| `finish` | `f` | ends the exam, with a summary |
| `help` | `?` | lists the commands |

Type the command (or its letter), then Enter. The up and down arrows bring
back the commands you typed: up then Enter runs the last one again. The
right arrow (full screen) or Tab (text interface) completes a command. The grading runs while the screen stays
alive, with the number of the test being run.

### What grademe checks

Your files are compiled with `cc -Wall -Wextra -Werror`, then:

- the files the subject expects must be there;
- no forbidden function may be used (only those in "Allowed functions");
- each test must not crash nor run more than 5 seconds, and must print
  exactly what is expected;
- for some exercises, `valgrind` must find no leak.

**OK**: you go to the next level, with a new subject. **KO**: the trace is
shown in the terminal and written in `traces/` (the path can be clicked).
The student's lines are marked `-`, the expected ones `+`, shown like
`cat -e`:

```
= Test 1 =======================================================================
$> ./forward_shift_2 | cat -e
--- student
+++ moulinette
+$

Diff KO
```

### Two modes: exam and revision

After a KO, you keep the same subject, and the next grademe must wait a
little longer after each failure. The mode, chosen after the exam, sets
these waits and the time:

| Mode | Waits after the 1st, 2nd, 3rd... KO | Time |
|---|---|---|
| Exam | 0.5, 2.5, 3, 5.5, 8.5, 14, 22.5... min, like 42_EXAM | the real duration (Exam Rank 02: 3 h) |
| Revision (Enter) | 0, 1, 2, 3, 5 min: the first retry is free | no time limit |

Each grademe tells what a KO would cost, and `status` shows when the next
one is allowed. Each passed level is worth 100 divided by the number of
levels (25 points at rank 02), for a grade out of 100.

### Time, resume and history

- In exam mode, when the time is up, the exam ends (in full screen, at once;
  in the text interface, at the next command): a late grademe is not graded.
  You are warned once, 10 minutes before the end.
- Closed the terminal, or pressed Ctrl-C? Run `./42pal` again: it offers to
  resume your exam, with the same subject; the time kept running.
- Every finished exam is kept in `~/.42pal/history.json`.
- `~/42pal_exam/rendu/` is also a git repository: `git add`, `git commit` and
  `git push` work like at the exam, but grademe grades your files whether
  they are committed or not.

## Practise one theme

```sh
./42pal practice                       # a menu of the themes
./42pal practice --theme letter_rotation
```

Subjects of one theme, one after the other: no login, no timer, no wait.
A passed `grademe` (`g`) gives the next subject; `next` (`n`) skips to
another one; `finish` (`f`) stops. It opens full screen too, unless `--plain`
is given.

## What the catalog has today

Five exams, like in 42_EXAM:

| Exam | Levels | Time | Levels that can be played today |
|---|---|---|---|
| Exam Rank 02 | 4 (25 points each) | 3 h | 1, 2, 3, 4 |
| Piscine Exam 01 | 8 (12.5 points each) | 4 h | 1 to 8 |
| Piscine Exam 02 | 8 (12.5 points each) | 4 h | 1 to 8 |
| Piscine Exam 03 | 4 (25 points each) | 4 h | 1 to 4 |
| Piscine Final Exam | 4 (25 points each) | 8 h | 1 to 4 |

| Exercise | Kind | Theme | Variants |
|---|---|---|---|
| `shift_letters` | program | letter_rotation | 18 |
| `char_position` | function | string_length | 6 |
| `char_filter` | program | common_chars | 11 |
| `split_fields` | function, leaks checked | string_split | 7 |
| `print_range` | function (void, prints) | print_digits | 10 |
| `arg_pick` | program | pick_argument | 6 |
| `word_order` | program | word_reverse | 13 |
| `number_facts` | program | prime_factors | 9 |
| `base_string` | function, leaks checked | base_to_string | 6 |
| `byte_rotate` | function | bit_rotate | 12 |
| `sequence_array` | function, leaks checked | int_range | 10 |
| `list_drop` | function + header handed in, leaks checked | list_remove | 12 |
| `name_style` | program | case_convert | 18 |
| `word_pick` | program | find_word | 10 |
| `base_print` | program | print_in_base | 8 |
| `list_measure` | function, header given | list_walk | 10 |
| `number_read` | function | read_base_number | 11 |
| `tab_index` | function | array_search | 10 |
| `tab_sort` | function | array_sort | 8 |
| `nest_report` | program | bracket_check | 9 |
| `longest_span` | program | longest_part | 8 |
| `alpha_wave` | program | alternating_alphabet | 11 |
| `alpha_back` | program | backward_alphabet | 7 |
| `case_flip` | program | case_swap | 12 |
| `calc_form` | program | calculator | 11 |
| `replace_pick` | program | char_replace | 8 |
| `letter_step` | program | letter_step | 7 |
| `rev_part` | program | reverse_print | 5 |
| `repeat_rule` | program | letter_repeat | 5 |
| `pointer_pair` | function | value_swap | 5 |
| `copy_shape` | function | string_copy | 8 |
| `put_filter` | function (void, prints) | string_print | 8 |
| `bip_bop` | program | number_words | 8 |

The subjects are
written for 42pal: no real exam subject is in this repository. Each theme
of [themes.json](themes.json) is the style of one real exam subject, at the
levels where 42_EXAM places it, and a test checks it. A level draws one of
its styles, then one exercise of that style: like the real exam, which draws
one of the subjects of the level. 33 of the 75 styles have an exercise so
far; every level of every exam has at least one, and level 1 of the Exam
Rank 02 has all of its 12.

## For contributors

Run the tests (Python's `unittest`, nothing to install):

```sh
python3 -m unittest
```

Check that the whole catalog grades right: each exercise has a reference
solution (`ref.c`) that must pass every one of its variants. When the
student hands in a header too, the reference header sits next to `ref.c`,
under its own name.

```sh
./42pal check-catalog
```

| Folder | What is in it |
|---|---|
| `pal42/` | the core: exercises, variants, subjects, grading (no display) |
| `pal42/cli/` | the terminal: examshell, practice, check-catalog, and the full screen (`tui.py`, `tui.tcss`) |
| `exercises/c/<name>/` | one exercise: `exercise.py`, its `ref.c` (and the header the student hands in, if any) |
| `exams/` | the exams: title, duration, compile command, retry waits |
| `tests/` | the tests |

The plan of the project, in French, is in
[docs/plans/42pal.md](docs/plans/42pal.md).

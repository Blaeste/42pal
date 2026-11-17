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

No `pip`, no virtual environment: the only library used for the display,
[rich](https://github.com/Textualize/rich), is copied in `vendor/` (see
[vendor/README.md](vendor/README.md)).

## Take an exam

```sh
./42pal
```

1. **Log in** like at the exam. The login defaults to your user name; the
   password can be anything, it is never checked nor kept.
2. **Choose the exam**, the **mode** (see below) and the **starting level**,
   among the levels that have exercises.
3. **Read the subject**: it is printed in the terminal and written in
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

| Command | What it does |
|---|---|
| `grademe` | grades your work |
| `status` | exam, level, subject, time spent and left, next grademe |
| `finish` | ends the exam, with a summary |
| `help` | lists the commands |

Tab completes the commands, and the arrow keys bring back the ones you typed.

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

- In exam mode, when the time is up, the next command ends the exam: a late
  grademe is not graded. You are warned once, 10 minutes before the end.
- Closed the terminal, or pressed Ctrl-C? Run `./42pal` again: it offers to
  resume your exam, with the same subject; the time kept running.
- Every finished exam is kept in `~/.42pal/history.json`.
- `~/42pal_exam/rendu/` is also a git repository: `git add`, `git commit` and
  `git push` work like at the exam, but grademe grades your files whether
  they are committed or not.

## Practise one theme

```sh
./42pal practice                       # a menu of the themes
./42pal practice --theme string_basics
```

Subjects of one theme, one after the other: no login, no timer, no wait.
A passed `grademe` gives the next subject; `next` skips to another one;
`finish` stops.

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
| `shift_letters` | program | char_transform | 18 |
| `char_position` | function | string_basics | 6 |
| `char_filter` | program | char_sets | 11 |
| `split_fields` | function, leaks checked | split | 7 |
| `print_range` | function (void, prints) | print_basics | 10 |
| `arg_pick` | program | program_args | 6 |
| `word_order` | program | words | 13 |
| `number_facts` | program | arithmetic | 9 |
| `base_string` | function, leaks checked | number_print | 6 |
| `byte_rotate` | function | bits | 12 |
| `sequence_array` | function, leaks checked | allocation | 10 |
| `list_drop` | function + header handed in, leaks checked | linked_lists | 12 |

The subjects are
written for 42pal: no real exam subject is in this repository. The list of
themes and the levels where they appear is in [themes.json](themes.json).

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
| `pal42/cli/` | the terminal: examshell, practice, check-catalog |
| `exercises/c/<name>/` | one exercise: `exercise.py`, its `ref.c` (and the header the student hands in, if any) |
| `exams/` | the exams: title, duration, compile command, retry waits |
| `tests/` | the tests |

The plan of the project, in French, is in
[docs/plans/42pal.md](docs/plans/42pal.md).

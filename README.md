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
2. **Choose the exam** (Exam Piscine, 4 h, or Exam Rank 02, 3 h) and the
   **starting level**, among the levels that have exercises.
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

### Waiting between two grademe

After a KO, you keep the same subject. The first retry is free; then the
wait grows with each failure:

| Mode | Waits after the 1st, 2nd, 3rd... KO |
|---|---|
| soft (default) | 0, 1, 2, 3, 5 min |
| hard: `./42pal --hard` | 0, 5, 10, 20, 40 min |

Each grademe tells what a KO would cost, and `status` shows when the next
one is allowed.

### Time, resume and history

- When the time is up, the next command ends the exam: a late grademe is not
  graded. You are warned once, 10 minutes before the end.
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

| Exercise | Kind | Theme | Levels (rank 02 and piscine) | Variants |
|---|---|---|---|---|
| `shift_letters` | program | char_transform | 1, 2 | 18 |
| `char_position` | function | string_basics | 1, 2 | 6 |
| `char_filter` | program | char_sets | 2, 3 | 11 |

Levels 1 to 3 can be played; level 4 has no exercise yet. The subjects are
written for 42pal: no real exam subject is in this repository. The list of
themes and the levels where they appear is in [themes.json](themes.json).

## For contributors

Run the tests (Python's `unittest`, nothing to install):

```sh
python3 -m unittest
```

Check that the whole catalog grades right: each exercise has a reference
solution (`ref.c`) that must pass every one of its variants.

```sh
./42pal check-catalog
```

| Folder | What is in it |
|---|---|
| `pal42/` | the core: exercises, variants, subjects, grading (no display) |
| `pal42/cli/` | the terminal: examshell, practice, check-catalog |
| `exercises/c/<name>/` | one exercise: `exercise.py` and its `ref.c` |
| `exams/` | the exams: title, duration, compile command, retry waits |
| `tests/` | the tests |

The plan of the project, in French, is in
[docs/plans/42pal.md](docs/plans/42pal.md).

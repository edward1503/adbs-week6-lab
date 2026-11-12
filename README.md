# Week 6 Lab: Access Methods, Cost Estimation and Plan Search

A 60-minute lab for COMP5330 Week 6 (Monday 30 November 2026), on Edinburgh ADBS week 6
([course page](https://opencourse.inf.ed.ac.uk/adbs/week-6), lectures 16 to 18).
Students check the lecture's cost formulas against PostgreSQL's `EXPLAIN`, then see how one wrong
row estimate makes the optimizer pick a slow join.

This repository contains the answers. Students only get the student zip (see "Edit and release").

## Run it

You need Docker (Docker Desktop on Windows or macOS), about 3 GB of free disk and 1.5 GB of free memory.

```
docker compose up -d --build
```

Open http://localhost:8888. `notebooks/lab.ipynb` is what students see, and `solution/solution.ipynb` is the solution key.
Stop with `docker compose stop`. Reset the data with `docker compose down -v`, then `docker compose up -d`.

## What students do

| Minutes | Part | Question | Tasks, optional ones in brackets |
|---|---|---|---|
| 0–5 | Warm-up | Start from `events` or from `buyers`? | a vote |
| 5–17 | A. Access methods | When is an index worth it? | A1 break-even (worked for them), A2 measure, A3 two-column index, (A4 CLUSTER) |
| 17–29 | B. Cost estimation | How does the optimizer guess row counts? | B1 independence, B2 join size, (B3 histogram) |
| 29–49 | C. Plan search | How does a wrong guess pick a slow plan? | C1 PostgreSQL's choice, C2 System R by hand, (C3 full query) |
| 49–55 | Exit ticket | When does INL stop being cheaper than a hash join? | one number |
| 55–60 | Wrap-up | Back to the vote | four ideas to try at home |

The `check()` cells grade the answers as students go. Optional tasks left blank are skipped.

## Files

| File | What it is |
|---|---|
| `AGENTS.md` | Rules for working in this repository. Read it first. |
| `tools/build_notebooks.py` | The only source of both notebooks. Edit here, then rebuild. |
| `notebooks/labkit.py` | Helpers used in the notebook: `sql()`, `explain()`, `show_pev2()`, `save()`, `check()` |
| `tests/test_lab.py` | The autograder. Fixed answers are stored as hashes. |
| `solution/` | Solution notebook and reference answers |
| `data/01_init.sql` | The dataset. It has no randomness, so it is the same on every machine. |
| `tools/make_student_release.py` | Builds the student zip and stops if an answer would leak into it |
| `STUDENT_README.md` | The README inside the student zip |

## Edit and release

After editing `tools/build_notebooks.py`, rebuild both notebooks:

```
uv run --no-project --with nbformat python tools/build_notebooks.py
```

48 hours before the lab, build the student zip and upload `dist/week6-lab-student.zip` to Canvas:

```
uv run --no-project --with nbformat python tools/make_student_release.py
```

## Dataset

| Table | Rows | Design |
|---|---:|---|
| events | 10,000 | 10 cities with 10% each, 50 genres with 2% each. All 200 Jazz events are in Hanoi. |
| buyers | 10,000 | 500 Campus buyers (5%), 20 tickets each |
| tickets | 200,000 | 20 tickets per event, stored in shuffled order (correlation about 0). Indexes on `event_id` and `buyer_id`. |

The full query returns exactly 200 tickets.

## Dry runs

PostgreSQL 17.6, 9 November 2026 (Duc):

| Task | By hand, with the slide formula | Measured in PostgreSQL |
|---|---|---|
| A1 break-even, 1274 / (191 + 200000) | 0.64%, about 64 events | Bitmap off: Index Scan up to 70 events, Seq Scan from 100 |
| A2 30 events, unclustered | (191 + 200000) × 0.003, about 601 pages | 599 buffers |
| A2 bitmap on | | Bitmap Heap Scan up to about 40% selectivity, Seq Scan from about 60% |
| B1 city and genre | 10000 × 0.1 × 0.02 = 20 | est 20, actual 200 |
| B2 join with tickets | 20 × 200000 / 10000 = 400 | est 400, actual 4000 |
| B3 price > 60, equi-depth | about 49,300 | est about 49,050, actual 47,866 |
| C1 join of events and tickets | INL 63 + 200 × 22 = 4,463; HJ 63 + 1274 = 1,337 | 4,429 and 1,337 |
| Full query | | Default statistics: Nested Loop, 16,429 buffers. After `CREATE STATISTICS (mcv)`: Hash Join, 1,388 buffers. |

- `CREATE STATISTICS (dependencies)` only raises the estimate to 24 and does not fix the plan. The extension uses this.
- On the full query, PostgreSQL joins `buyers` with an index nested loop on its primary key (about 12,000 pages),
  while the lab's model uses a hash join for the third join. That is why C3 costs more than the model.

Windows laptop (Intel i7-1255U, 16 GB), Docker Desktop 4.99.0, 12 November 2026 (Khai): the student zip sets up
in about 2 minutes (image download 53 s, build 79 s), the setup check passes, and Docker uses 3.2 GB of disk.

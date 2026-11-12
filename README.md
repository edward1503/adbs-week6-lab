# Week 6 Lab: Access Methods, Cost Estimation and Plan Search

A 60-minute lab for COMP5330 Week 6 (Monday 30 November 2026), on Edinburgh ADBS week 6
([course page](https://opencourse.inf.ed.ac.uk/adbs/week-6), lectures 16 to 18).
Students watch PostgreSQL choose between an index and a full scan, find out why one of its row
estimates is 10 times too small, and fix it with better statistics: the same query then reads about 12 times fewer pages.

This repository contains the answers. Students only get the student zip (see "Edit and release").

## Run it

You need Docker (Docker Desktop on Windows or macOS), about 3 GB of free disk and 1.5 GB of free memory.

```
docker compose up -d --build
```

Open http://localhost:8888. `notebooks/lab.ipynb` is what students see, and `solution/solution.ipynb` is the solution key.
Stop with `docker compose stop`. Reset the data with `docker compose down -v`, then `docker compose up -d`.

## What students do

| Minutes | Part | Question | Answers |
|---|---|---|---|
| 0–5 | Warm-up | Look up each concert's tickets in the index, or read all tickets once? | a vote |
| 5–17 | A. Index or full scan? | When does PostgreSQL stop using the index? A2: which filters does a two-column index match? | 2, and 4 true/false |
| 17–27 | B. Why the estimate is wrong | Estimate Jazz concerts in Hanoi with the lecture's rules: 20, but actually 200. Which assumption fails? | 3 |
| 27–40 | C. What a wrong estimate costs | The full query: nested loops and about 16,400 pages. After `CREATE STATISTICS`: hash joins and about 1,400 pages. | 4 |
| 40–45 | Exit ticket | Up to how many concerts is a nested loop cheaper than a hash join? | 1 |
| 45–55 | Extra tasks | Bitmap scan, histograms, System R by hand, clustered index | optional |
| 55–60 | Wrap-up | Back to the vote; three open-ended ideas for home | |

The `check()` cells mark the answers as students go. Extra tasks left blank are skipped.

## Files

| File | What it is |
|---|---|
| `AGENTS.md` | Rules for working in this repository. Read it first. |
| `tools/build_notebooks.py` | The only source of both notebooks. Edit here, then rebuild. |
| `notebooks/labkit.py` | Helpers used in the notebook: `sql()`, `explain()`, `show_pev2()`, `save()`, `check()` |
| `tests/test_lab.py` | The autograder. Fixed answers are stored as hashes; answers read from a plan are compared with the same plan run live. For C1 it drops the Part C statistics inside a transaction and rolls back. |
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

PostgreSQL 17.6, 9 November 2026 (Duc), measured on the earlier version of the lab; the queries are the same:

| Task | By hand, with the slide formula | Measured in PostgreSQL |
|---|---|---|
| A1 break-even, 1274 / (191 + 200000) | 0.64%, about 64 events | Bitmap off: Index Scan up to 70 events, Seq Scan from 100 |
| A1 30 events, unclustered | (191 + 200000) × 0.003, about 601 pages | 599 buffers |
| Extra 1, bitmap on | | Bitmap Heap Scan up to about 40% selectivity, Seq Scan from about 60% |
| B1 city and genre | 10000 × 0.1 × 0.02 = 20 | est 20, actual 200 |
| C1 and C2, full query | | Default statistics: Nested Loop, 16,429 buffers. After `CREATE STATISTICS (mcv)`: Hash Join, 1,388 buffers. |
| Extra 2, price > 60, equi-depth | about 49,300 | est about 49,050, actual 47,866 |
| Extra 3, events and tickets | Nested loop 63 + 200 × 22 = 4,463; hash join 63 + 1274 = 1,337 | 4,429 and 1,337 |

- `CREATE STATISTICS (dependencies)` only raises the estimate to 24 and does not fix the plan. The extension uses this.
- On the full query, PostgreSQL joins `buyers` with an index nested loop on its primary key (about 12,000 pages),
  while the lab's model uses a hash join for the third join. That is why the real plan costs more than the model in Extra 3.

Windows laptop (Intel i7-1255U, 16 GB), Docker Desktop 4.99.0, 12 November 2026 (Khai): the student zip sets up
in about 2 minutes (image download 53 s, build 79 s), the setup check passes, and Docker uses 3.2 GB of disk.

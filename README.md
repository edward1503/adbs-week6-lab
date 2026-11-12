# Week 6 Lab — Access Methods, Cost Estimation & Plan Search

A 60-minute hands-on lab for the Edinburgh ADBS course, Week 6 ([course page](https://opencourse.inf.ed.ac.uk/adbs/week-6)).
Students play the query optimizer: **predict with the formulas from the slides → measure with `EXPLAIN` → explain the gap.**

## Run (students)

Requirements: Docker Desktop (≈1.5 GB RAM). Internet only for the first build and the optional PEV2 plan viewer.

```bash
docker compose up -d --build   # PostgreSQL 17.6 + JupyterLab (first time ~2 min)
```

Open http://localhost:8888 — `notebooks/lab.ipynb` opens automatically. All ports listen on localhost only.
In the notebook, `check("task_a")` … `check()` runs the autograder; answers are saved to `answers.json`.

Reset the data (after ★★★ A4 or the extension): `docker compose down -v && docker compose up -d`.
Stop: `docker compose stop`.

## Lab outline (undergraduate level)

Every task follows **predict → measure with `EXPLAIN` → explain the gap**. The notebook opens with a one-line glossary
(page, buffers, selectivity, Seq/Index Scan, estimated vs actual rows); formulas are given with the numbers to plug in,
and C2 has a worked example.

| Minutes | Part | Question | Required tasks | Optional |
|---|---|---|---|---|
| 0–5 | Warm-up | Start the join from `events` or `buyers`? | vote | — |
| 5–17 | **A** Access methods | When is an index worth it? | A1 break-even, A2 measure (incl. bitmap), A3 two-column index | A4 CLUSTER |
| 17–29 | **B** Cost estimation | How does the optimizer guess row counts? | B1 independence (est 20 vs 200), B2 join size | B3 histogram |
| 29–49 | **C** Plan search | How does a wrong guess pick a slow plan? | C1 NL vs HJ in PostgreSQL, C2 System R by hand | C3 full query |
| 49–55 | Exit ticket | Break-even number of events for INL vs HJ | — | — |
| 55–60 | Wrap-up | Back to the vote; "going further" ideas | — | 4 home extensions |

Optional tasks are skipped by the autograder when left blank.

## For the teaching team

| File | Contents |
|---|---|
| `AGENTS.md` | **Rules for working in this repo** (people and AI assistants) — read first |
| `tools/build_notebooks.py` | **Single source** of the student and solution notebooks — edit here, then rebuild |
| `notebooks/labkit.py` | `sql()`, `explain()`, `show_pev2()`, `save()`, `check()` |
| `solution/solution.ipynb` | Solution key, computed live from the database (no machine-dependent numbers hard-coded) |
| `solution/answers.json` | Reference answers |
| `tests/test_lab.py` | Autograder; fixed answers are stored as hashes |
| `data/01_init.sql` | Deterministic dataset |
| `tools/make_student_release.py` | Builds `dist/week6-lab-student.zip` from an allow-list and fails if any answer leaks |
| `STUDENT_README.md` | README shipped to students (setup at home, troubleshooting) |

```bash
uv run --no-project --with nbformat python tools/build_notebooks.py
```

### Releasing to students (48 h before the lab)

Never share this repo directly — `solution/` **and** `tools/build_notebooks.py` contain the answers.

```bash
uv run --no-project --with nbformat python tools/make_student_release.py
```

Upload `dist/week6-lab-student.zip` (10 files: compose, Dockerfile, data, notebook, labkit, autograder, blank answers, student README).

## Dataset (deterministic — no randomness)

| Table | Rows | Design |
|---|---:|---|
| events | 10,000 | 10 cities × 10%, 50 genres × 2%. 200 Jazz events, **all in Hanoi** |
| buyers | 10,000 | 500 Campus (5%), 20 tickets each |
| tickets | 200,000 | 20 tickets/event, physically shuffled (correlation ≈ 0). Indexes on `event_id`, `buyer_id` |

The main query returns exactly 200 tickets.

## Dry-run results (PostgreSQL 17.6, 9 Nov 2026)

| Task | By hand (slide formula) | Measured in PostgreSQL |
|---|---|---|
| A1 sel* = 1274 / (191 + 200000) | 0.64% ≈ 64 events | Bitmap off: Index Scan up to 70 events, Seq Scan from 100 |
| A2 30 events, unclustered | (191+200000)·0.003 ≈ 601 pages | 599 buffers |
| A2 bitmap on | — | Bitmap Heap Scan up to ~40% sel, Seq Scan from ~60% |
| B1 city ∧ genre | 10000·0.1·0.02 = 20 | rows=20, actual 200 |
| B2 E′ ⋈ T | 20·200000/10000 = 400 | rows=400, actual 4000 |
| B3 price > 60 (equi-depth) | ≈ 49,300 | rows ≈ 49,050, actual 47,866 |
| C1 E′ ⋈ T | INL 63+200·22 = 4,463 / HJ 63+1274 = 1,337 | 4,429 / **1,337** |
| Full query | — | Default stats: Nested Loop, 16,429 buffers. After `CREATE STATISTICS (mcv)`: Hash Join, 1,388 buffers |

Notes:
- `CREATE STATISTICS (dependencies)` only raises the estimate to 24 and does **not** fix the plan — used in the extension.
- On the full query, PostgreSQL joins `buyers` with an index nested loop on its primary key (≈12,000 pages), whereas the lab model uses HJ for the third join — that is why C3 costs more than the model.

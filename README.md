# Week 6 Lab: Access Methods, Cost Estimation and Plan Search

A 60-minute lab for COMP5330 Week 6 (Monday 30 November 2026), based on
[Edinburgh ADBS week 6](https://opencourse.inf.ed.ac.uk/adbs/week-6). Students watch PostgreSQL choose a plan,
find out why one of its estimates is wrong, and fix it.

This repository contains the answers, so keep it private. Students only get the student zip.

## Try the lab

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (on Windows: AMD64), open it,
   and wait for "Engine running". You need about 3 GB of free disk.
2. On this page, click **Code**, then **Download ZIP**, and unzip it.
3. Open a terminal in the unzipped folder. Windows 11: right-click inside the folder, then "Open in Terminal".
   Mac: open Terminal, type `cd `, drag the folder in, and press Enter.
4. Run `docker compose up -d --build`. The first time takes a few minutes.
5. Open http://localhost:8888.
   - `notebooks/lab.ipynb` is what students see.
   - `solution/solution.ipynb` is the solution key. Choose Run, then Run All Cells: every check should pass.

| To ... | Run |
|---|---|
| stop | `docker compose stop` |
| start again | `docker compose up -d` |
| reset the data | `reset_database()` in a notebook cell, or `docker compose down -v`, then `docker compose up -d` |

Only one copy can run at a time. Before starting a new version, run `docker compose down -v` in the old folder.

### Without Docker: Google Colab

Upload `notebooks/lab_colab.ipynb` to https://colab.research.google.com and run the first cell.
`colab/setup.sh` installs PostgreSQL 17 with the same planner settings as `docker-compose.yml`, downloads the
lab files (not the solution) from this repository on GitHub, and loads the data, in about 2 minutes.
The Colab notebook downloads from GitHub, so it only works while the repository is public.
To try a branch before it is merged, change `LAB_BRANCH` in the first cell.

## What students do

| Minutes | Part |
|---|---|
| 0–5 | Warm-up: index lookups or read all tickets? |
| 5–17 | A. When does PostgreSQL stop using the index? Which filters does a two-column index match? |
| 17–27 | B. Why is the estimate wrong? 20 Jazz concerts in Hanoi expected, 200 actual |
| 27–40 | C. The full query: nested loops and 16,429 pages, then hash joins and 1,388 pages after `CREATE STATISTICS` |
| 40–45 | Exit ticket |
| 45–55 | Extra tasks: bitmap scan, histograms, System R by hand, clustered index |
| 55–60 | Wrap-up with the class |

## Files

| File | What it is |
|---|---|
| `AGENTS.md` | Rules for working in this repository. Read it first. |
| `tools/build_notebooks.py` | The only source of the notebooks: `lab.ipynb`, `lab_colab.ipynb` and the solution |
| `colab/setup.sh` | Sets up PostgreSQL and the lab files on Google Colab |
| `notebooks/labkit.py` | Helpers used in the notebook, such as `explain()` and `check()` |
| `tests/test_lab.py` | The autograder |
| `solution/` | Solution notebook and reference answers |
| `data/01_init.sql` | The dataset, the same on every machine |
| `tools/make_student_release.py` | Builds the student zip and stops if an answer would leak into it |
| `STUDENT_README.md` | The README inside the student zip |

## Edit and release

After editing `tools/build_notebooks.py`, rebuild the notebooks:

```
uv run --no-project --with nbformat python tools/build_notebooks.py
```

48 hours before the lab, build `dist/week6-lab-student.zip` and upload it to Canvas:

```
uv run --no-project --with nbformat python tools/make_student_release.py
```

## Dataset

| Table | Rows | Design |
|---|---:|---|
| events | 10,000 | 10 cities, 50 genres. All 200 Jazz events are in Hanoi. |
| buyers | 10,000 | 500 are Campus buyers |
| tickets | 200,000 | 20 per event, in shuffled order. Indexes on `event_id` and `buyer_id`. |

## Dry runs

PostgreSQL 17.6, 9 November 2026 (Duc):

| Task | Measured |
|---|---|
| A1, bitmap off | Index Scan up to 50 events, Seq Scan from 100. At 30 events: 599 pages. At 70 events the plan depends on the random sample of `ANALYZE`, so the sweep leaves 70 out. |
| B1 | est 20, actual 200 |
| C1, C2 | Nested Loop, 16,429 pages. After `CREATE STATISTICS (mcv)`: Hash Join, 1,388 pages. |
| Extra 1, bitmap on | Bitmap Heap Scan up to about 40% of the tickets, Seq Scan from about 60% |
| Extra 2, price > 60 | est about 49,050, actual 47,866 |
| Extra 3, events with tickets | Nested loop 4,429 pages, hash join 1,337 |

`CREATE STATISTICS (dependencies)` does not fix the plan (estimate 24), which the first idea for home asks about.

Windows laptop, Docker Desktop 4.99.0, 12 November 2026 (Khai): the student zip starts in about 2 minutes and uses 3.2 GB of disk.
The solution notebook passes all checks with the same numbers as above (histogram estimate 49,030).

Ubuntu 22.04 container standing in for Colab, PostgreSQL 17 from the PostgreSQL apt repository, 16 November 2026 (Duc):
`colab/setup.sh` finishes in under a minute, and the solution notebook passes all checks with the same numbers
as the Docker run. Not yet tried on Colab itself.

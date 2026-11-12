# Rules for everyone working in this repository (people and AI assistants)

Read this before changing anything. If a rule is in the way, discuss it with the team and change
this file; do not quietly work around it.

## 1. Pull before you start, pull before you push

- `git pull --rebase` before you start and again before you push, then read what came in:
  `git log -p ORIG_HEAD..`.
- Set once per clone: `git config pull.rebase true`, so that a plain `git pull` rebases.
  `main` stays one straight line, without merge commits.

## 2. Edit only `tools/build_notebooks.py`

- `notebooks/lab.ipynb` and `solution/solution.ipynb` are generated from it. Never edit them by hand.
- After an edit, rebuild both with
  `uv run --no-project --with nbformat python tools/build_notebooks.py`
  (without uv: `pip install nbformat`, then `python tools/build_notebooks.py`).
  Commit the source and both notebooks together.
- A conflict in a notebook during a pull: resolve it in `build_notebooks.py`, then rebuild.
  Never merge notebook JSON by hand.

## 3. Check before you push

After a change to the notebooks, `labkit.py`, `tests/`, the data or `docker-compose.yml`,
on a laptop with Docker:

1. Fresh database: `docker compose down -v`, then `docker compose up -d --build`
   (two commands: Windows PowerShell does not accept `&&`).
2. Open `solution/solution.ipynb` (http://localhost:8888/lab/tree/solution/solution.ipynb) and run
   all cells. Every `check(...)` cell says that all checks passed.
3. `uv run --no-project --with nbformat python tools/make_student_release.py` ends with
   "student package: …", not with "LEAK".
4. Throw away what the run changed: `git restore notebooks/ solution/ answers.json`.

Changes to Markdown files only (README, this file) need no check.

## 4. Numbers in the text come from a run

- The notebook text and the README quote measured numbers ("about 600 pages", "about 64 events",
  "about 3 times more pages", the dry-run table). After a change to the data, to the planner settings
  in `docker-compose.yml` or to the PostgreSQL version, rerun the solution and update every
  quoted number.
- The dry-run table in `README.md` says the date and the PostgreSQL version it was measured with.

## 5. Small commits; bigger changes through a pull request

- One change per commit. The message says what changed and why.
- Small fixes (a typo, wording, a hint) go straight to `main`.
- Bigger changes (adding, cutting or reordering tasks; changing the data or the autograder) go on
  a branch with a pull request, and the other lab designer reviews it before it is merged.

## 6. Answers stay hidden

- The repository is private. No forks and no copies anywhere public.
- Students only get `dist/week6-lab-student.zip` from `tools/make_student_release.py`, never
  this repository.
- No notebook outputs, `solution/answers_solution.json`, a filled-in `answers.json`, `dist/` or
  keys in git.

## 7. No AI attribution

Commit messages and pull requests carry no AI attribution (no "Co-Authored-By: <AI tool>",
no "Generated with …" lines). The author is the person who commits.

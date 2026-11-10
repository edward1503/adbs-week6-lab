# Week 6 Lab — Access Methods, Cost Estimation & Plan Search

## Before the lab (please do this at home — the first build downloads ~1 GB)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it.
2. In this folder run:

   ```bash
   docker compose up -d --build
   ```

3. Open http://localhost:8888 — `notebooks/lab.ipynb` opens automatically.
4. Run the first cell. You must see `✅ 1 passed`.

## During the lab

- Replace every `None`, run the cell, and at the end of each part run `check("task_a")`, `check("task_b")`, `check("task_c")`.
- `check()` grades everything. Your answers are stored in `answers.json` — this is what you submit.
- ★★★ tasks are optional.

## Troubleshooting

| Problem | Fix |
|---|---|
| `check` says the autograder could not run | The database is down: `docker compose up -d` |
| Port 8888 or 55432 already in use | Stop the other program, or change the left-hand port in `docker-compose.yml` |
| Data changed after A4 / the extension | `docker compose down -v && docker compose up -d` |
| Plan viewer (`show_pev2`) is blank | It needs internet; use the text plan instead |

Stop everything after the lab: `docker compose stop`.

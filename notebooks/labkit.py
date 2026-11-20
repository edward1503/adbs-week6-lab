"""Helpers for the Week 6 lab notebook (keep the notebook itself short)."""
import html
import json
import os
import re
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore", message="Consider using IPython.display.IFrame")
from pathlib import Path

import pandas as pd
import psycopg
from IPython.display import HTML, display

ROOT = Path(__file__).resolve().parent.parent
ANSWERS = Path(os.getenv("ANSWERS", ROOT / "answers.json"))

COLAB = os.getenv("LAB_ENV") == "colab"      # set by the setup cell of the Colab notebook


def _connect(dbname="tickets"):
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "55432")),
        user="lab", password="lab", dbname=dbname, autocommit=True,
    )


_conn = _connect()

RANGE = "SELECT sum(price) FROM tickets WHERE event_id <= {n}"
SWEEP = (10, 30, 50, 100, 150, 300)      # values of n in Part A; tests/test_lab.py uses the same.
# No n = 70: there the plan depends on the random sample taken by ANALYZE, so it differs between laptops.
QUERY = """SELECT sum(t.price)
FROM tickets t
JOIN events e ON e.id = t.event_id
JOIN buyers b ON b.id = t.buyer_id
WHERE e.city = 'Hanoi' AND e.genre = 'Jazz' AND b.segment = 'Campus'"""


# ------------------------------------------------------------------ SQL
def sql(query):
    """Run a statement. Queries return a DataFrame; DDL/DML (CREATE, CLUSTER, ...) print the status."""
    with _conn.cursor() as cur:
        cur.execute(query)
        if cur.description is None:          # no result set
            print("OK:", cur.statusmessage)
            return None
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def reset_database():
    """Rebuild the lab data from data/01_init.sql (under a minute). Your answers are kept."""
    global _conn
    _conn.close()
    with _connect("postgres") as admin:
        admin.execute("DROP DATABASE IF EXISTS tickets WITH (FORCE)")
        admin.execute("CREATE DATABASE tickets OWNER lab")
    _conn = _connect()
    script = (ROOT / "data" / "01_init.sql").read_text(encoding="utf-8")
    for stmt in re.split(r";\s*\n", script):      # one statement at a time: VACUUM cannot run in a batch
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            _conn.execute(body)
    print("The database is back to its starting state.")


class Plan:
    def __init__(self, root, query):
        self.root, self.query = root, query

    # numbers students read from the plan
    @property
    def buffers(self):
        return self.root.get("Shared Hit Blocks", 0) + self.root.get("Shared Read Blocks", 0)

    def nodes(self, node=None):
        node = node or self.root
        yield node
        for child in node.get("Plans", []):
            yield from self.nodes(child)

    def find(self, node_type):
        return next(n for n in self.nodes() if n["Node Type"] == node_type)

    @property
    def scan(self):
        """First node that reads a table (skips Aggregate / Bitmap Index Scan)."""
        return next(n for n in self.nodes()
                    if "Scan" in n["Node Type"] and n["Node Type"] != "Bitmap Index Scan")

    def text(self):
        lines = []

        def walk(n, depth):
            rel = f" on {n['Relation Name']}" if "Relation Name" in n else ""
            idx = f" using {n['Index Name']}" if "Index Name" in n else ""
            bufs = n.get("Shared Hit Blocks", 0) + n.get("Shared Read Blocks", 0)
            loops = n["Actual Loops"]
            loops_txt = "" if loops == 1 else f" (x{loops} loops)"
            lines.append(
                f"{'   ' * depth}-> {n['Node Type']}{rel}{idx}  "
                f"est rows={n['Plan Rows']:,}  actual rows={n['Actual Rows']:,}{loops_txt}"
                f"  buffers={bufs:,}")
            for c in n.get("Plans", []):
                walk(c, depth + 1)

        walk(self.root, 0)
        return "\n".join(lines)

    def _repr_html_(self):
        return f"<pre>{html.escape(self.text())}</pre>"


def explain(query, settings=""):
    """EXPLAIN (ANALYZE, BUFFERS) a query. settings: e.g. 'SET enable_nestloop=off'."""
    with _conn.cursor() as cur:
        cur.execute("RESET ALL")
        for s in filter(None, (x.strip() for x in settings.split(";"))):
            cur.execute(s)
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
        raw = cur.fetchone()[0]
        cur.execute("RESET ALL")
    p = Plan(raw[0]["Plan"], query)
    p.raw = raw
    return p


def scan_sweep(values=SWEEP):
    """Part A: run RANGE for each n with bitmap scans off; one row per n."""
    rows = []
    for n in values:
        p = explain(RANGE.format(n=n), "SET enable_bitmapscan=off")
        rows.append({"n": n, "matching tickets": 20 * n, "scan": p.scan["Node Type"], "pages read": p.buffers})
    return pd.DataFrame(rows).set_index("n")


def show_pev2(plan, height=520):
    """Interactive plan tree with PEV2 (needs internet for the CDN)."""
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://unpkg.com/pev2@1.12.1/dist/style.css" rel="stylesheet">
<script src="https://unpkg.com/vue@3.4.21/dist/vue.global.prod.js"></script>
<script src="https://unpkg.com/pev2@1.12.1/dist/pev2.umd.js"></script></head>
<body><div id="app" class="d-flex flex-column vh-100"><pev2 :plan-source="plan" :plan-query="query"></pev2></div>
<script>
const app = Vue.createApp({{data() {{ return {{plan: {json.dumps(json.dumps(plan.raw))}, query: {json.dumps(plan.query)}}} }}}});
app.component("pev2", pev2.Plan); app.mount("#app");
</script></body></html>"""
    display(HTML(f'<iframe srcdoc="{html.escape(page)}" style="width:100%;height:{height}px;border:1px solid #ccc"></iframe>'))


# ------------------------------------------------------------------ answers & grading
def save(**answers):
    """Store answers in answers.json (only the keys you pass)."""
    data = json.loads(ANSWERS.read_text(encoding="utf-8")) if ANSWERS.exists() else {}
    data.update(answers)
    # numpy / pandas scalars (e.g. from sql(...)) -> plain Python numbers
    to_py = lambda o: o.item() if hasattr(o, "item") else str(o)
    ANSWERS.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=to_py), encoding="utf-8")
    print("saved:", ", ".join(f"{k}={v!r}" for k, v in answers.items()))


MARKERS = ("setup", "task_a", "task_b", "task_c", "exit", "extras")
# test name (without "test_") -> task name shown to students
LABELS = {"setup": "Setup", "a1": "A1", "a2": "A2", "b1": "B1", "c1": "C1", "c2": "C2",
          "exit_ticket": "Exit ticket", "extra_histogram": "Extra 2", "extra_optimizer": "Extra 3"}
NOT_RUNNING = "Could not run the checks. Is the database running?\n" + (
    "Run the setup cell at the top of the notebook again, then run this cell again." if COLAB else
    "Start Docker Desktop, then run this in your terminal:  docker compose up -d\n"
    "Then run this cell again.")


def check(part=None):
    """Check your answers: check("task_a"), ..., check("extras"), or check() for the whole lab."""
    if part is not None and part not in MARKERS:
        print(f"There is no part called {part!r}. Use one of {', '.join(MARKERS)}, or check() for everything.")
        return
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=no", "-rfE",
           "--color=no", "-p", "no:cacheprovider", "-W", "ignore"]
    if part:
        cmd += ["-m", part]
    env = {**os.environ, "ANSWERS": str(ANSWERS), "PYTHONIOENCODING": "utf-8", "COLUMNS": "400"}
    res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                         text=True, encoding="utf-8")
    # pytest exit codes: 0 all passed, 1 some failed, 2-4 internal/usage error, 5 no tests
    if res.returncode not in (0, 1, 5):
        print(NOT_RUNNING)
        print((res.stdout + res.stderr).strip()[-800:])
        return
    counts, wrong = {}, []
    for line in res.stdout.splitlines():
        if line.startswith("ERROR"):            # a fixture failed: no database or no answers file
            print(NOT_RUNNING)
            return
        if line.startswith("FAILED"):
            test = line.split("::")[-1].split(" ")[0].removeprefix("test_")
            hint = line.split(" - ", 1)[-1].strip() if " - " in line else ""
            hint = hint.removeprefix("AssertionError:").strip()
            hint = "" if hint.startswith("assert ") else hint
            wrong.append(f"  {LABELS.get(test, test)}" + (f": {hint}" if hint else ""))
        for number, word in re.findall(r"(\d+) (passed|failed|skipped)", line.split(" in ")[0]):
            counts[word] = int(number)
    total = counts.get("passed", 0) + counts.get("failed", 0)
    if total == 0:
        print("No checks found for this part.")
    elif not wrong:
        print("1 check passed." if total == 1 else f"All {total} checks passed.")
    else:
        print(f"{len(wrong)} of {total} {'check' if total == 1 else 'checks'} "
              f"{'needs' if len(wrong) == 1 else 'need'} another look:")
        print("\n".join(wrong))
        print("Run progress() to see every task and how far you are.")
    if counts.get("skipped"):
        print("(Extra tasks you left blank were skipped.)")


# ------------------------------------------------------------------ progress table
# (part, task shown to students, test name, answer names, required)
TASKS = [
    ("Setup", "Setup", "setup", (), True),
    ("A", "A1. When does PostgreSQL stop using the index?", "a1",
     ("a1_first_seq_scan_n", "a1_pages_per_ticket"), True),
    ("A", "A2. An index on two columns", "a2", ("a2_matches",), True),
    ("B", "B1. Jazz concerts in Hanoi", "b1", ("b1_estimate", "b1_actual", "b1_assumption"), True),
    ("C", "C1. The plan PostgreSQL picks", "c1", ("c1_join", "c1_pages"), True),
    ("C", "C2. Better statistics", "c2", ("c2_join", "c2_pages"), True),
    ("Exit", "Exit ticket", "exit_ticket", ("exit_max_events",), True),
    ("Extra", "Extra 2. Histograms", "extra_histogram", ("hist_my_estimate", "hist_postgres_estimate"), False),
    ("Extra", "Extra 3. Be the optimizer", "extra_optimizer",
     ("opt_events_nl_estimated", "opt_events_nl_actual", "opt_events_hj",
      "opt_chosen_plan", "opt_chosen_plan_actual_cost"), False),
]
# status -> (text, background, text colour)
_STATUS = {
    "done": ("Done", "#d3f4dd", "#145c2c"),
    "again": ("Check again", "#fde2e1", "#8a1c17"),
    "partly": ("In progress", "#fff1cc", "#7a5300"),
    "todo": ("Not started", "#eceef1", "#3d4450"),
    "optional": ("Optional", "#eceef1", "#6b7280"),
    "error": ("Could not check", "#fde2e1", "#8a1c17"),
}


def _filled(value):
    return any(v is not None for v in value) if isinstance(value, list) else value is not None


def progress():
    """Show every task of the lab with its status: done, check again, in progress or not started."""
    import tempfile
    import xml.etree.ElementTree as ET

    report = Path(tempfile.gettempdir()) / "week6_progress.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "--color=no", "-p", "no:cacheprovider",
           "-W", "ignore", f"--junitxml={report}"]
    env = {**os.environ, "ANSWERS": str(ANSWERS), "PYTHONIOENCODING": "utf-8"}
    res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    if res.returncode not in (0, 1) or not report.exists():
        print(NOT_RUNNING)
        return
    results = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        name = case.get("name").removeprefix("test_")
        bad = case.find("failure")
        if case.find("error") is not None:
            results[name] = ("error", "")
        elif case.find("skipped") is not None:
            results[name] = ("skipped", "")
        elif bad is not None:
            msg = (bad.get("message") or "").removeprefix("AssertionError:").strip().splitlines()
            hint = msg[0].strip() if msg and not msg[0].startswith("assert ") else ""
            results[name] = ("failed", hint)
        else:
            results[name] = ("passed", "")
    report.unlink(missing_ok=True)
    if any(outcome == "error" for outcome, _ in results.values()):
        print(NOT_RUNNING)
    answers = json.loads(ANSWERS.read_text(encoding="utf-8")) if ANSWERS.exists() else {}

    rows, done, required = [], 0, 0
    for part, title, test, keys, needed in TASKS:
        outcome, hint = results.get(test, ("error", ""))
        filled = [_filled(answers.get(k)) for k in keys]
        if outcome == "error":
            status = "error"
        elif outcome == "passed":
            status = "done"
        elif keys and not any(filled):
            status = "todo" if needed else "optional"
        elif outcome == "skipped":
            status = "optional"
        else:
            status = "again" if all(filled) else "partly"
        if needed:
            required += 1
            done += status == "done"
        rows.append((part, title, status, hint if status in ("again", "partly") else ""))

    _show_progress(rows, done, required)


def _show_progress(rows, done, required):
    pct = round(100 * done / required) if required else 0
    cells = []
    for part, title, status, hint in rows:
        text, bg, fg = _STATUS[status]
        badge = (f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;'
                 f'font-size:12px;white-space:nowrap">{text}</span>')
        cells.append(f"<tr><td style='text-align:left;vertical-align:top;padding:4px 10px;color:#6b7280'>{html.escape(part)}</td>"
                     f"<td style='text-align:left;vertical-align:top;padding:4px 10px'>{html.escape(title)}</td>"
                     f"<td style='text-align:left;vertical-align:top;padding:4px 10px'>{badge}</td>"
                     f"<td style='text-align:left;vertical-align:top;padding:4px 10px;font-size:12px;color:#6b7280'>{html.escape(hint)}</td></tr>")
    page = f"""<div style="font-family:system-ui,sans-serif;font-size:14px;max-width:900px">
<div style="margin:4px 0 6px"><b>{done} of {required}</b> required tasks done</div>
<div style="height:8px;background:#eceef1;border-radius:4px;margin-bottom:10px">
  <div style="height:8px;width:{pct}%;background:#2f9e57;border-radius:4px"></div></div>
<table style="border-collapse:collapse">
<tr style="text-align:left;border-bottom:1px solid #d0d4da"><th style="text-align:left;padding:4px 10px">Part</th>
<th style="text-align:left;padding:4px 10px">Task</th><th style="text-align:left;padding:4px 10px">Status</th><th style="text-align:left;padding:4px 10px">Hint</th></tr>
{''.join(cells)}</table></div>"""
    lines = [f"{done} of {required} required tasks done"] + [
        f"  {title}: {_STATUS[status][0]}" + (f"  ({hint})" if hint else "") for _, title, status, hint in rows]
    display({"text/html": page, "text/plain": "\n".join(lines)}, raw=True)

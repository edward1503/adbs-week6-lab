"""Helpers for the Week 6 lab notebook (keep the notebook itself short)."""
import html
import json
import os
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

_conn = psycopg.connect(
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "55432")),
    user="lab", password="lab", dbname="tickets", autocommit=True,
)

RANGE = "SELECT sum(price) FROM tickets WHERE event_id <= {n}"
QUERY = """SELECT sum(t.price)
FROM tickets t
JOIN events e ON e.id = t.event_id
JOIN buyers b ON b.id = t.buyer_id
WHERE e.city = 'Hanoi' AND e.genre = 'Jazz' AND b.segment = 'Campus'"""


# ------------------------------------------------------------------ SQL
def sql(query):
    """Run a query and return a DataFrame."""
    with _conn.cursor() as cur:
        cur.execute(query)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


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
                f"  cost={n['Total Cost']:,.0f}  buffers={bufs:,}")
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
    ANSWERS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved:", ", ".join(f"{k}={v!r}" for k, v in answers.items()))


def check(marker=None):
    """Run the autograder for one part: check('task_a'), ..., or check() for all."""
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=no", "-rf",
           "--color=no", "-p", "no:cacheprovider", "-W", "ignore"]
    if marker:
        cmd += ["-m", marker]
    env = {**os.environ, "ANSWERS": str(ANSWERS), "PYTHONIOENCODING": "utf-8", "COLUMNS": "400"}
    out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                         text=True, encoding="utf-8").stdout
    for line in out.splitlines():
        if line.startswith("FAILED"):
            test = line.split("::")[-1].split(" ")[0].removeprefix("test_")
            hint = line.split("AssertionError:", 1)[-1].strip() if "AssertionError:" in line else ""
            hint = "" if hint.startswith("assert ") else hint
            print(f"  ✗ {test}" + (f" — hint: {hint}" if hint else ""))
        elif " passed" in line or " failed" in line:
            summary = line.split(" in ")[0].replace(", ", " · ")
            print(("❌ " if "failed" in line else "✅ ") + summary)

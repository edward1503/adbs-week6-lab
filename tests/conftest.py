import hashlib
import json
import os
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent


def h(value):
    """Hash an answer so the expected values are not readable in the repo."""
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()[:16]


@pytest.fixture(scope="session")
def db():
    conn = psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "55432")),
        user="lab", password="lab", dbname="tickets", autocommit=True,
    )
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def ans():
    path = Path(os.getenv("ANSWERS", ROOT / "answers.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def explain(db, sql, settings=""):
    """Return (plan_root, top-level buffers) for EXPLAIN ANALYZE of sql."""
    with db.cursor() as cur:
        cur.execute("RESET ALL")
        for s in filter(None, settings.split(";")):
            cur.execute(s)
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
        plan = cur.fetchone()[0][0]["Plan"]
        cur.execute("RESET ALL")
    return plan


def first_scan(plan):
    """First node below the Aggregate that touches a table."""
    node = plan
    while node.get("Plans"):
        node = node["Plans"][0]
        if "Scan" in node["Node Type"] and node["Node Type"] != "Bitmap Index Scan":
            return node
    return node


def close(student, truth, rel):
    return student is not None and abs(student - truth) <= rel * abs(truth)

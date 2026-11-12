import hashlib
import json
import os
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent


def normalize(value):
    """20.0 -> 20, ' e-inl-t-hj-b ' -> 'E-INL-T-HJ-B', lists element-wise."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        try:                                   # "20" typed as a string
            f = float(s)
            return int(f) if f.is_integer() else f
        except ValueError:
            return s.upper()
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def h(value):
    """Hash an answer so the expected values are not readable in the repo."""
    return hashlib.sha256(json.dumps(normalize(value)).encode()).hexdigest()[:16]


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
    try:
        student = float(student)
    except (TypeError, ValueError):
        return False
    return abs(student - truth) <= rel * abs(truth)


def buffers(plan):
    """Pages read by a plan node: shared hit + read, as `buffers=` in the notebook."""
    return plan.get("Shared Hit Blocks", 0) + plan.get("Shared Read Blocks", 0)


def explain_without_extended_stats(db, sql):
    """Plan as PostgreSQL makes it before Part C adds statistics.

    Drops every extended statistics object inside a transaction, explains, then rolls back,
    so the student's database is left as it was.
    """
    with db.transaction():
        for (name,) in db.execute("SELECT stxname FROM pg_statistic_ext").fetchall():
            db.execute(f'DROP STATISTICS "{name}"')
        plan = explain(db, sql)
        raise psycopg.Rollback()
    return plan

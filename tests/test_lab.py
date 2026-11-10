"""Week 6 lab autograder.  Run one part:  pytest -m task_b"""
import pytest

from conftest import close, explain, first_scan, h

RANGE = "SELECT sum(price) FROM tickets WHERE event_id <= {n}"


# ------------------------------------------------------------------ setup
@pytest.mark.setup
def test_dataset(db):
    q = lambda sql: db.execute(sql).fetchone()
    assert q("SELECT count(*) FROM events")[0] == 10_000
    assert q("SELECT count(*) FROM buyers")[0] == 10_000
    assert q("SELECT count(*) FROM tickets")[0] == 200_000
    assert q("SELECT min(c), max(c) FROM (SELECT count(*) c FROM tickets GROUP BY event_id) x") == (20, 20)
    assert q("SELECT count(*) FROM events WHERE genre='Jazz' AND city='Hanoi'")[0] == 200
    assert q("""SELECT count(*) FROM tickets t JOIN events e ON e.id=t.event_id
                JOIN buyers b ON b.id=t.buyer_id
                WHERE e.city='Hanoi' AND e.genre='Jazz' AND b.segment='Campus'""")[0] == 200
    assert q("SELECT count(*) FROM pg_statistic_ext")[0] == 0, \
        "Extended statistics found: reset with `docker compose down -v && docker compose up -d`"


# ------------------------------------------------------------------ A
@pytest.mark.task_a
def test_a1_break_even(db, ans):
    npt, npi = db.execute("""SELECT (SELECT relpages FROM pg_class WHERE relname='tickets'),
                                    (SELECT relpages FROM pg_class WHERE relname='idx_tickets_event')""").fetchone()
    assert ans["a1_npages_t"] == npt, "Read NPages(tickets) from pg_class.relpages"
    assert ans["a1_npages_i"] == npi, "Read NPages(idx_tickets_event) from pg_class.relpages"
    truth = npt / (npi + 200_000)
    assert close(ans["a1_sel_star"], truth, 0.03), \
        "sel* = NPages(T) / (NPages(I) + NTuples(T))  (L18 slide 6, unclustered vs file scan)"


@pytest.mark.task_a
def test_a2_observed_plans(db, ans):
    off = "SET enable_bitmapscan=off"
    p30 = explain(db, RANGE.format(n=30), off)
    p150 = explain(db, RANGE.format(n=150), off)
    p150_on = explain(db, RANGE.format(n=150))
    assert ans["a2_scan_30"] == first_scan(p30)["Node Type"], "Re-check the scan node for 30 events"
    assert close(ans["a2_buffers_30"], p30["Shared Hit Blocks"] + p30["Shared Read Blocks"], 0.05), \
        "Use the Buffers of the top node (shared hit + read)"
    assert ans["a2_scan_150"] == first_scan(p150)["Node Type"]
    assert ans["a2_scan_150_bitmap_on"] == first_scan(p150_on)["Node Type"]


@pytest.mark.task_a
def test_a3_composite_key(ans):
    assert h(ans["a3_matches"]) == "10882820c88dd08a", \
        "Index (city, genre): matches = equality prefix + at most one range (L16 slides 14-21)"


# ------------------------------------------------------------------ B
@pytest.mark.task_b
def test_b1_conjunction(ans):
    assert h(ans["b1_est"]) == "f5ca38f748a1d6ea", "sel(P1 AND P2) = sel(P1)*sel(P2) (L17 s19)"
    assert h(ans["b1_actual"]) == "27badc983df1780b", "Count the rows: actual rows of the events scan"
    assert "indep" in str(ans["b1_violated_assumption"]).lower(), \
        "Name the assumption behind sel(P1 AND P2) = sel(P1)*sel(P2)"


@pytest.mark.task_b
def test_b2_join_size(ans):
    assert h(ans["b2_est"]) == "26d228663f13a885", "|R join S| = |R||S| / max(NKeys) (L17 s21)"
    assert h(ans["b2_actual"]) == "b090147020e03353"


@pytest.mark.task_b
def test_b3_histogram(db, ans):
    bounds = db.execute("""SELECT histogram_bounds::text::numeric[] FROM pg_stats
                           WHERE tablename='tickets' AND attname='price'""").fetchone()[0]
    x, nb = 60, len(bounds) - 1
    frac = 0.0
    for lo, hi in zip(bounds, bounds[1:]):
        lo, hi = float(lo), float(hi)
        if lo >= x:
            frac += 1
        elif hi > x:
            frac += (hi - x) / (hi - lo)
    hand = frac / nb * 200_000
    assert close(ans["b3_price_gt_60_hand"], hand, 0.03), \
        "Equi-depth: whole buckets above 60 + fraction of the bucket containing 60 (L17 s35)"
    pg = explain(db, "SELECT count(*) FROM tickets WHERE price > 60")["Plans"][0]["Plan Rows"]
    assert close(ans["b3_pg_est"], pg, 0.01), "Copy rows= from the Seq Scan node"


# ------------------------------------------------------------------ C
SQL_ET = """SELECT sum(t.price) FROM events e JOIN tickets t ON t.event_id=e.id
            WHERE e.city='Hanoi' AND e.genre='Jazz'"""


@pytest.mark.task_c
def test_c1_join_methods(db, ans):
    nl = explain(db, SQL_ET)
    hj = explain(db, SQL_ET, "SET enable_nestloop=off")
    assert close(ans["c1_nl_buffers"], nl["Shared Hit Blocks"] + nl["Shared Read Blocks"], 0.05), \
        "Default plan: buffers of the top node (shared hit + read)"
    assert close(ans["c1_hj_buffers"], hj["Shared Hit Blocks"] + hj["Shared Read Blocks"], 0.05), \
        "Plan with enable_nestloop=off: buffers of the top node"


@pytest.mark.task_c
def test_c2_pass2(ans):
    assert h(ans["c2_et_inl_est"]) == "7182dd431b5c8833", "63 + |E'|*(2 index pages + 20 heap pages)"
    assert h(ans["c2_et_inl_act"]) == "c91d793d0e481d8b", "Same formula with the ACTUAL |E'|"
    assert h(ans["c2_et_hj"]) == "5db1fee4b5703808", "Hash join reads both base tables once"
    assert h(ans["c2_bt_inl"]) == "666f3094ce81bff7"
    assert h(ans["c2_bt_hj"]) == "59c4d02848bada0d"


@pytest.mark.task_c
def test_c2_pass3(ans):
    assert h(ans["c2_pass3_choice_est"]) == "d7636687c9cb51fc", "Format: E-INL-T-HJ-B"
    assert h(ans["c2_pass3_cost_est"]) == "833cd8c0e698745b"
    assert h(ans["c2_chosen_plan_actual_cost"]) == "6bb731a8009cb35b", \
        "Re-cost the plan chosen with estimates, using actual cardinalities"
    assert h(ans["c2_best_actual_cost"]) == "e401f2bd399f3456"


# ------------------------------------------------------------------ exit ticket
@pytest.mark.exit
def test_exit_threshold(ans):
    assert ans["exit_threshold_events"] in (57, 58), "Solve 63 + 22x < 63 + 1274"

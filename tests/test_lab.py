"""Week 6 lab autograder. Run one part:  pytest -m task_b

Each assert message is the hint a student sees for that answer. Fixed answers are stored as hashes.
"""
import pytest

from conftest import close, explain, first_scan, h, normalize

RANGE = "SELECT sum(price) FROM tickets WHERE event_id <= {n}"
RESET = "The data is not as expected. Reset the database: docker compose down -v, then docker compose up -d"


# ------------------------------------------------------------------ setup
@pytest.mark.setup
def test_setup(db):
    q = lambda sql: db.execute(sql).fetchone()
    assert q("SELECT count(*) FROM events")[0] == 10_000, RESET
    assert q("SELECT count(*) FROM buyers")[0] == 10_000, RESET
    assert q("SELECT count(*) FROM tickets")[0] == 200_000, RESET
    assert q("SELECT min(c), max(c) FROM (SELECT count(*) c FROM tickets GROUP BY event_id) x") == (20, 20), RESET
    assert q("SELECT count(*) FROM events WHERE genre='Jazz' AND city='Hanoi'")[0] == 200, RESET
    assert q("""SELECT count(*) FROM tickets t JOIN events e ON e.id=t.event_id
                JOIN buyers b ON b.id=t.buyer_id
                WHERE e.city='Hanoi' AND e.genre='Jazz' AND b.segment='Campus'""")[0] == 200, RESET
    assert q("SELECT count(*) FROM pg_statistic_ext")[0] == 0, RESET


# ------------------------------------------------------------------ A
@pytest.mark.task_a
def test_a2(db, ans):
    off = "SET enable_bitmapscan=off"
    p30 = explain(db, RANGE.format(n=30), off)
    p150 = explain(db, RANGE.format(n=150), off)
    p150_on = explain(db, RANGE.format(n=150))
    assert normalize(ans["a2_scan_30"]) == normalize(first_scan(p30)["Node Type"]), \
        "a2_scan_30: copy the name of the scan from the n = 30 plan, for example 'Seq Scan'"
    assert close(ans["a2_buffers_30"], p30["Shared Hit Blocks"] + p30["Shared Read Blocks"], 0.05), \
        "a2_buffers_30: copy the number after buffers= on the first line of the n = 30 plan"
    assert normalize(ans["a2_scan_150"]) == normalize(first_scan(p150)["Node Type"]), \
        "a2_scan_150: copy the name of the scan from the n = 150 plan"
    assert normalize(ans["a2_scan_150_bitmap_on"]) == normalize(first_scan(p150_on)["Node Type"]), \
        "a2_scan_150_bitmap_on: copy the name of the scan on the second line of the last plan"


@pytest.mark.task_a
def test_a3(ans):
    assert h(ans["a3_matches"]) == "10882820c88dd08a", \
        ("a3_matches: an index on (city, genre) matches equality conditions on the first columns, "
         "plus at most one range condition on the next column (lecture 16, slides 14 to 21)")


# ------------------------------------------------------------------ B
@pytest.mark.task_b
def test_b1(ans):
    assert h(ans["b1_estimate"]) == "f5ca38f748a1d6ea", \
        "b1_estimate: 10000 × sel(city) × sel(genre), with sel = 1 / NKeys"
    assert h(ans["b1_actual"]) == "27badc983df1780b", "b1_actual: copy the actual rows from the plan"
    assert "indep" in str(ans["b1_assumption"]).lower(), \
        "b1_assumption: which assumption does the AND rule make?"


@pytest.mark.task_b
def test_b2(ans):
    assert h(ans["b2_estimate"]) == "26d228663f13a885", "b2_estimate: b1_estimate × 200000 / 10000"
    assert h(ans["b2_actual"]) == "b090147020e03353", "b2_actual: copy the actual rows from the first line of the plan"


@pytest.mark.task_b
def test_b3(db, ans):
    if ans.get("b3_my_estimate") is None and ans.get("b3_postgres_estimate") is None:
        pytest.skip("optional task B3 not attempted")
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
    assert close(ans["b3_my_estimate"], hand, 0.03), \
        ("b3_my_estimate: count the buckets completely above 60, add the fraction of the bucket "
         "that contains 60, then multiply by 20000 (lecture 17, slide 35)")
    pg = explain(db, "SELECT count(*) FROM tickets WHERE price > 60")["Plans"][0]["Plan Rows"]
    assert close(ans["b3_postgres_estimate"], pg, 0.01), "b3_postgres_estimate: copy the est rows on the Seq Scan line"


# ------------------------------------------------------------------ C
SQL_ET = """SELECT sum(t.price) FROM events e JOIN tickets t ON t.event_id=e.id
            WHERE e.city='Hanoi' AND e.genre='Jazz'"""


@pytest.mark.task_c
def test_c1(db, ans):
    nl = explain(db, SQL_ET)
    hj = explain(db, SQL_ET, "SET enable_nestloop=off")
    assert close(ans["c1_buffers_nested_loop"], nl["Shared Hit Blocks"] + nl["Shared Read Blocks"], 0.05), \
        "c1_buffers_nested_loop: copy the number after buffers= on the first line of the first plan"
    assert close(ans["c1_buffers_hash_join"], hj["Shared Hit Blocks"] + hj["Shared Read Blocks"], 0.05), \
        "c1_buffers_hash_join: copy the number after buffers= on the first line of the second plan"


@pytest.mark.task_c
def test_c2_step1(ans):
    assert h(ans["c2_buyers_inl"]) == "666f3094ce81bff7", "c2_buyers_inl: keep the worked example as it is"
    assert h(ans["c2_buyers_hj"]) == "59c4d02848bada0d", "c2_buyers_hj: keep the worked example as it is"
    assert h(ans["c2_events_inl_estimated"]) == "7182dd431b5c8833", \
        "c2_events_inl_estimated: follow the buyers example, with 63 pages for events and the estimated 20 events"
    assert h(ans["c2_events_inl_actual"]) == "c91d793d0e481d8b", \
        "c2_events_inl_actual: the same formula with the actual 200 events"
    assert h(ans["c2_events_hj"]) == "5db1fee4b5703808", "c2_events_hj: read events once, then read tickets once"


@pytest.mark.task_c
def test_c2_step2(ans):
    assert h(ans["c2_chosen_plan"]) == "6b86b273ff34fce1", \
        "c2_chosen_plan: the optimizer picks the plan with the smaller estimated cost"
    assert h(ans["c2_chosen_plan_actual_cost"]) == "6bb731a8009cb35b", \
        "c2_chosen_plan_actual_cost: cost the chosen plan again, with the actual 200 events"


# ------------------------------------------------------------------ exit ticket
@pytest.mark.exit
def test_exit_ticket(ans):
    assert normalize(ans["exit_max_events"]) == 57, \
        "exit_max_events: the largest whole x with 63 + 22x < 63 + 1274. Check your rounding."

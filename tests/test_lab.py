"""Week 6 lab autograder. Run one part:  pytest -m task_b

Each assert message is the hint a student sees for that answer. Fixed answers are stored as hashes;
answers read from a plan are compared with the same plan, run live.
"""
import pytest

from conftest import buffers, close, explain, explain_without_extended_stats, first_scan, h, normalize

RANGE = "SELECT sum(price) FROM tickets WHERE event_id <= {n}"
SWEEP = (10, 30, 50, 70, 100, 150, 300)      # same as notebooks/labkit.py
QUERY = """SELECT sum(t.price)
FROM tickets t
JOIN events e ON e.id = t.event_id
JOIN buyers b ON b.id = t.buyer_id
WHERE e.city = 'Hanoi' AND e.genre = 'Jazz' AND b.segment = 'Campus'"""
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
    # Part C creates ev_stats; anything else means the database was changed
    assert q("SELECT count(*) FROM pg_statistic_ext WHERE stxname <> 'ev_stats'")[0] == 0, RESET


# ------------------------------------------------------------------ A
@pytest.mark.task_a
def test_a1(db, ans):
    plans = {n: explain(db, RANGE.format(n=n), "SET enable_bitmapscan=off") for n in SWEEP}
    first_seq = next((n for n, p in plans.items() if first_scan(p)["Node Type"] == "Seq Scan"), None)
    assert normalize(ans["a1_first_seq_scan_n"]) == first_seq, \
        "a1_first_seq_scan_n: go down the table and take the first n whose scan is Seq Scan"
    assert close(ans["a1_pages_per_ticket"], buffers(plans[30]) / 600, 0.1), \
        "a1_pages_per_ticket: take the pages read in the row n = 30 and divide by 600"


@pytest.mark.task_a
def test_a2(ans):
    assert h(ans["a2_matches"]) == "10882820c88dd08a", \
        ("a2_matches: an index on (city, genre) matches equality conditions on the first columns, "
         "plus at most one range condition on the next column (lecture 16, slides 14 to 21)")


# ------------------------------------------------------------------ B
@pytest.mark.task_b
def test_b1(ans):
    assert h(ans["b1_estimate"]) == "f5ca38f748a1d6ea", \
        "b1_estimate: 10000 × sel(city) × sel(genre), with sel = 1 / NKeys"
    assert h(ans["b1_actual"]) == "27badc983df1780b", "b1_actual: copy the actual rows from the plan"
    assert "indep" in str(ans["b1_assumption"]).lower(), \
        "b1_assumption: which assumption does the AND rule make?"


# ------------------------------------------------------------------ C
@pytest.mark.task_c
def test_c1(db, ans):
    before = explain_without_extended_stats(db, QUERY)
    assert normalize(ans["c1_join"]) == normalize(before["Plans"][0]["Node Type"]), \
        "c1_join: copy the name of the join method on the second line of the plan"
    assert close(ans["c1_pages"], buffers(before), 0.05), \
        "c1_pages: copy the number after buffers= on the first line of the plan"


@pytest.mark.task_c
def test_c2(db, ans):
    made = db.execute("SELECT count(*) FROM pg_statistic_ext WHERE stxname = 'ev_stats'").fetchone()[0]
    assert made == 1, "C2: run the cell with CREATE STATISTICS first"
    after = explain(db, QUERY)
    assert normalize(ans["c2_join"]) == normalize(after["Plans"][0]["Node Type"]), \
        "c2_join: copy the join method on the second line of the new plan"
    assert close(ans["c2_pages"], buffers(after), 0.05), \
        "c2_pages: copy the number after buffers= on the first line of the new plan"


# ------------------------------------------------------------------ exit ticket
@pytest.mark.exit
def test_exit_ticket(ans):
    assert normalize(ans["exit_max_events"]) == 57, \
        "exit_max_events: the largest whole x with 63 + 22x < 63 + 1274. Check your rounding."


# ------------------------------------------------------------------ extras (skipped when left blank)
@pytest.mark.extras
def test_extra_histogram(db, ans):
    if ans.get("hist_my_estimate") is None and ans.get("hist_postgres_estimate") is None:
        pytest.skip("extra task left blank")
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
    assert close(ans["hist_my_estimate"], frac / nb * 200_000, 0.03), \
        ("hist_my_estimate: count the buckets completely above 60, add the fraction of the bucket "
         "that contains 60, then multiply by 20000 (lecture 17, slide 35)")
    pg = explain(db, "SELECT count(*) FROM tickets WHERE price > 60")["Plans"][0]["Plan Rows"]
    assert close(ans["hist_postgres_estimate"], pg, 0.01), \
        "hist_postgres_estimate: copy the est rows on the Seq Scan line"


@pytest.mark.extras
def test_extra_optimizer(ans):
    mine = ("opt_events_nl_estimated", "opt_events_nl_actual", "opt_events_hj",
            "opt_chosen_plan", "opt_chosen_plan_actual_cost")
    if all(ans.get(k) is None for k in mine):
        pytest.skip("extra task left blank")
    assert h(ans["opt_buyers_nl"]) == "666f3094ce81bff7", "opt_buyers_nl: keep the worked example as it is"
    assert h(ans["opt_buyers_hj"]) == "59c4d02848bada0d", "opt_buyers_hj: keep the worked example as it is"
    assert h(ans["opt_events_nl_estimated"]) == "7182dd431b5c8833", \
        "opt_events_nl_estimated: follow the buyers example, with 63 pages for events and the estimated 20 events"
    assert h(ans["opt_events_nl_actual"]) == "c91d793d0e481d8b", \
        "opt_events_nl_actual: the same formula with the actual 200 events"
    assert h(ans["opt_events_hj"]) == "5db1fee4b5703808", "opt_events_hj: read events once, then read tickets once"
    assert h(ans["opt_chosen_plan"]) == "6b86b273ff34fce1", \
        "opt_chosen_plan: the optimizer picks the plan with the smaller estimated cost"
    assert h(ans["opt_chosen_plan_actual_cost"]) == "6bb731a8009cb35b", \
        "opt_chosen_plan_actual_cost: cost the chosen plan again, with the actual 200 events"

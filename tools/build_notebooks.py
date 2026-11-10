"""Build notebooks/lab.ipynb (student) and solution/solution.ipynb from ONE source.

    uv run --no-project --with nbformat python tools/build_notebooks.py

Cell kinds:  md(text) | code(src) | ans(student_src, solution_src)
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
CELLS = []


def md(s): CELLS.append(("md", s.strip()))
def code(s): CELLS.append(("code", s.strip()))
def ans(student, solution): CELLS.append(("ans", student.strip(), solution.strip()))


# =====================================================================
md("""
# Week 6 Lab — Which table does PostgreSQL join first?
**Access Methods · Cost Estimation · Plan Search** · 60 minutes · work in pairs

You are a data engineer at a ticketing platform. A report needs the **revenue from Jazz tickets in Hanoi bought by Campus members**.
For the next 60 minutes you play the optimizer: **predict with the formulas from the slides → measure with `EXPLAIN` → explain the gap.**

| Minutes | Part | Edinburgh slides |
|---|---|---|
| 0–5 | Warm-up | L18 s3–4 |
| 5–15 | **A** Access methods | L16 s9–11, 14–29 · L18 s6–7 |
| 15–27 | **B** Cost estimation | L17 s14–21, 25–36 |
| 27–47 | **C** Plan search | L18 s9–19, 22 |
| 47–52 | **D** Extension kick-off | — |
| 52–60 | Exit ticket | — |

**Rules:** replace every `None` → run the cell → at the end of each part run `check(...)`. ★★★ tasks are optional.
The cost unit in this lab is the **page**, as on the slides; `buffers` in `EXPLAIN` is the number of pages PostgreSQL touched.
""")

code("""
from labkit import *          # sql(), explain(), show_pev2(), save(), check()
check("setup")                # you must see ✅ before you start
""")

md("""
## 0 · Warm-up (5′)
The report query:
```sql
SELECT sum(t.price) FROM tickets t
JOIN events e ON e.id = t.event_id
JOIN buyers b ON b.id = t.buyer_id
WHERE e.city = 'Hanoi' AND e.genre = 'Jazz' AND b.segment = 'Campus';
```
Each of you: if you were the optimizer, would you **start from `events` or from `buyers`**? Write one sentence of reasoning. Not graded — we come back to it at the end.
""")
ans("""
hook_vote = None      # 'events' or 'buyers'
hook_reason = None    # one sentence
save(hook_vote=hook_vote, hook_reason=hook_reason)
""", """
hook_vote = "events"
hook_reason = "Filtering on city+genre looks more selective than the 500 Campus buyers."
save(hook_vote=hook_vote, hook_reason=hook_reason)
""")

# ===================================================================== A
md("""
## A · Access methods (10′)
Query: `SELECT sum(price) FROM tickets WHERE event_id <= n` — there is an **unclustered** B+-tree on `event_id`.

Formulas (L18 s6), where `sel` = fraction of rows that satisfy the predicate:
* Sequential scan: `NPages(R)`
* Unclustered index: `(NPages(I) + NTuples(R)) · sel` — every matching row costs ~1 page (L16 s24)

### A1 ★ Break-even point
Read `NPages` from the catalog, then solve `(NPages(I) + NTuples(R)) · sel* = NPages(R)`.
""")
code("""
sql(\"\"\"SELECT relname, relpages AS npages, reltuples::int AS ntuples
       FROM pg_class WHERE relname IN ('tickets', 'idx_tickets_event')\"\"\")
""")
ans("""
a1_npages_t = None    # NPages(tickets)
a1_npages_i = None    # NPages(idx_tickets_event)
a1_sel_star = None    # your formula
save(a1_npages_t=a1_npages_t, a1_npages_i=a1_npages_i, a1_sel_star=a1_sel_star)
""", """
cat = sql("SELECT relname, relpages FROM pg_class WHERE relname IN ('tickets','idx_tickets_event')").set_index("relname").relpages
a1_npages_t = int(cat["tickets"])
a1_npages_i = int(cat["idx_tickets_event"])
a1_sel_star = a1_npages_t / (a1_npages_i + 200_000)
print(f"sel* = {a1_sel_star:.4%}  ≈ {a1_sel_star * 10_000:.0f} events")
save(a1_npages_t=a1_npages_t, a1_npages_i=a1_npages_i, a1_sel_star=a1_sel_star)
""")

md("""
### A2 ★ Measure it on PostgreSQL
Every event has 20 tickets, so `event_id <= n` has `sel = n / 10 000`.
First **turn bitmap scans off** so PostgreSQL only has the two options from the slide.

✍️ **Predict before you run:** for `n = 30` and `n = 150`, does PostgreSQL pick `Index Scan` or `Seq Scan`? Roughly how many buffers at `n = 30`, according to the formula?
""")
code("""
p30  = explain(RANGE.format(n=30),  "SET enable_bitmapscan=off")
p150 = explain(RANGE.format(n=150), "SET enable_bitmapscan=off")
display(p30, p150)
""")
ans("""
a2_scan_30 = None       # 'Index Scan' / 'Seq Scan' (read it from the plan)
a2_buffers_30 = None    # buffers of the top node
a2_scan_150 = None
save(a2_scan_30=a2_scan_30, a2_buffers_30=a2_buffers_30, a2_scan_150=a2_scan_150)
""", """
a2_scan_30 = p30.scan["Node Type"]
a2_buffers_30 = p30.buffers
a2_scan_150 = p150.scan["Node Type"]
print(f"formula: {(191 + 200_000) * 30 / 10_000:.0f} pages — measured: {a2_buffers_30}")
save(a2_scan_30=a2_scan_30, a2_buffers_30=a2_buffers_30, a2_scan_150=a2_scan_150)
""")
md("""
Now **turn bitmap scans back on** (PostgreSQL's default) and rerun `n = 150`.
💬 Why does PostgreSQL still use the index even though `sel` is above `sel*`? Hint: L16 s24 (sort rids, then read pages in order) and s29 (Bitmap Heap Scan).
""")
code("""
p150_on = explain(RANGE.format(n=150))
p150_on
""")
ans("""
a2_scan_150_bitmap_on = None
save(a2_scan_150_bitmap_on=a2_scan_150_bitmap_on)
""", """
a2_scan_150_bitmap_on = p150_on.scan["Node Type"]
save(a2_scan_150_bitmap_on=a2_scan_150_bitmap_on)
""")
code("""
# (optional) interactive plan tree — needs internet
show_pev2(p150_on)
""")

md("""
### A3 ★ Composite search key (L16 s14–21)
Assume a B+-tree on `events(city, genre)`. Which predicates does this index **match**? (`True`/`False`)
1. `city = 'Hanoi' AND genre = 'Jazz'`
2. `city = 'Hanoi'`
3. `genre = 'Jazz'`
4. `city > 'H' AND genre = 'Jazz'`
""")
ans("""
a3_matches = [None, None, None, None]
save(a3_matches=a3_matches)
""", """
a3_matches = [True, True, False, False]   # 3: no prefix; 4: range before equality → not one contiguous key range
save(a3_matches=a3_matches)
""")
md("""
#### ★★★ A4 (optional)
Run `CLUSTER tickets USING idx_tickets_event; ANALYZE tickets;` and measure `n = 150` again with bitmap scans off.
Use the clustered formula `(NPages(I) + NPages(R)) · sel` to explain the result. **Reset the data afterwards** (see README).
""")
code('check("task_a")')

# ===================================================================== B
md("""
## B · Cost estimation (12′)
The catalog stores `NTuples`, `NPages`, `NKeys` and histograms (L17 s14). Formulas:
* `sel(A = c) = 1 / NKeys(A)` (L17 s17)
* `sel(P1 ∧ P2) = sel(P1) · sel(P2)` — **independence assumption** (L17 s19)
* `|R ⋈ S| ≈ |R| · |S| / max(NKeys(R.A), NKeys(S.A))` (L17 s21)

### B1 ★ Two filters on `events`
""")
code("""
sql(\"\"\"SELECT attname, n_distinct AS nkeys, most_common_freqs[1] AS freq_of_top_value
       FROM pg_stats WHERE tablename = 'events' AND attname IN ('city', 'genre')\"\"\")
""")
md("✍️ Use the formulas to predict how many events satisfy `city = 'Hanoi' AND genre = 'Jazz'`, **then** run the next cell.")
ans("""
b1_est = None      # your prediction = PostgreSQL's estimate?
save(b1_est=b1_est)
""", """
b1_est = round(10_000 * (1 / 10) * (1 / 50))
save(b1_est=b1_est)
""")
code("""
pb1 = explain("SELECT * FROM events WHERE city = 'Hanoi' AND genre = 'Jazz'")
pb1
""")
ans("""
b1_actual = None
b1_violated_assumption = None   # which assumption from the slides is violated?
save(b1_actual=b1_actual, b1_violated_assumption=b1_violated_assumption)
""", """
b1_actual = pb1.root["Actual Rows"]
b1_violated_assumption = "independence of predicates — every Jazz event is in Hanoi"
save(b1_actual=b1_actual, b1_violated_assumption=b1_violated_assumption)
""")

md("""
### B2 ★ The error propagates into the join
Use the L17 s21 formula with the **estimated** `|E'|` from B1, `|T| = 200 000`, `NKeys = 10 000`.
""")
ans("""
b2_est = None
save(b2_est=b2_est)
""", """
b2_est = round(b1_est * 200_000 / 10_000)
save(b2_est=b2_est)
""")
code("""
pb2 = explain(\"\"\"SELECT t.* FROM events e JOIN tickets t ON t.event_id = e.id
                  WHERE e.city = 'Hanoi' AND e.genre = 'Jazz'\"\"\")
pb2
""")
ans("""
b2_actual = None   # actual rows of the join node
save(b2_actual=b2_actual)
""", """
b2_actual = pb2.root["Actual Rows"]
save(b2_actual=b2_actual)
""")

md("""
### B3 ★★ Equi-depth histogram (L17 s31–35)
PostgreSQL's `histogram_bounds` is an **equi-depth** histogram: 11 bounds → 10 buckets, each holding ~10% of the rows.
Estimate `price > 60` = buckets entirely above 60 + the fraction of the bucket that contains 60 (assume uniform within a bucket).
""")
code("""
bounds = [float(x) for x in sql(\"\"\"SELECT unnest(histogram_bounds::text::numeric[]) AS b
                                   FROM pg_stats WHERE tablename='tickets' AND attname='price'\"\"\").b]
bounds
""")
ans("""
b3_price_gt_60_hand = None   # your estimated row count (out of 200 000 tickets)
save(b3_price_gt_60_hand=b3_price_gt_60_hand)
""", """
frac = sum(1 if lo >= 60 else (hi - 60) / (hi - lo) if hi > 60 else 0
           for lo, hi in zip(bounds, bounds[1:]))
b3_price_gt_60_hand = round(frac / (len(bounds) - 1) * 200_000)
save(b3_price_gt_60_hand=b3_price_gt_60_hand)
""")
code("""
pb3 = explain("SELECT count(*) FROM tickets WHERE price > 60")
pb3
""")
ans("""
b3_pg_est = None   # est rows of the Seq Scan
save(b3_pg_est=b3_pg_est)
""", """
b3_pg_est = pb3.scan["Plan Rows"]
save(b3_pg_est=b3_pg_est)
""")
code('check("task_b")')

# ===================================================================== C
md("""
## C · Plan search (20′)
### C1 ★ Two join algorithms in real PostgreSQL (L18 s11–12)
Join the filtered `events` with `tickets`. Run the default plan, then forbid nested loops.
✍️ Predict: what does PostgreSQL pick by default, given it **believes** there are only 20 events?
""")
code("""
SQL_ET = \"\"\"SELECT sum(t.price) FROM events e JOIN tickets t ON t.event_id = e.id
            WHERE e.city = 'Hanoi' AND e.genre = 'Jazz'\"\"\"
pc_nl = explain(SQL_ET)
pc_hj = explain(SQL_ET, "SET enable_nestloop=off")
display(pc_nl, pc_hj)
""")
ans("""
c1_nl_buffers = None
c1_hj_buffers = None
save(c1_nl_buffers=c1_nl_buffers, c1_hj_buffers=c1_hj_buffers)
""", """
c1_nl_buffers, c1_hj_buffers = pc_nl.buffers, pc_hj.buffers
save(c1_nl_buffers=c1_nl_buffers, c1_hj_buffers=c1_hj_buffers)
""")

md("""
### C2 ★★ System R-style dynamic programming (L18 s12–19, 22)
**The lab's cost model** — in pages, validated against C1:

| Operation | Cost (pages) | Source |
|---|---|---|
| Read + filter `events` / `buyers` / `tickets` | `NPages`: **63 / 51 / 1 274** | L18 s6 |
| **INL** into `tickets` (index on `event_id` or `buyer_id`) | per outer row: **2** index pages (root → leaf) + **20** heap pages (20 tickets, unclustered) | L16 s23–24 |
| **HJ** with a base table | read that whole table: `NPages` (the outer input is pipelined, no extra cost) | — |

**Rules:** left-deep trees · no cross products · keep only the cheapest plan per subset · in pass 3 the remaining table is joined with HJ.

**Cardinalities:** `|E'|` estimated **20**, actual **200** · `|B'| = 500` · every event and every buyer has 20 tickets.

**Pass 2** — fill in the cost of each candidate (including the cost of reading the outer table):

| Subset | Candidate | Estimated | Actual |
|---|---|---|---|
| {E,T} | E' →INL T | `c2_et_inl_est` | `c2_et_inl_act` |
| {E,T} | E' ⋈HJ T | `c2_et_hj` | (same as left) |
| {B,T} | B' →INL T | `c2_bt_inl` | (same as left) |
| {B,T} | B' ⋈HJ T | `c2_bt_hj` | (same as left) |
| {E,B} | — | cross product → pruned | |
""")
ans("""
c2_et_inl_est = None
c2_et_inl_act = None
c2_et_hj = None
c2_bt_inl = None
c2_bt_hj = None
save(c2_et_inl_est=c2_et_inl_est, c2_et_inl_act=c2_et_inl_act, c2_et_hj=c2_et_hj,
     c2_bt_inl=c2_bt_inl, c2_bt_hj=c2_bt_hj)
""", """
NP_E, NP_B, NP_T, PROBE = 63, 51, 1274, 2 + 20
inl = lambda outer_pages, outer_rows: outer_pages + outer_rows * PROBE
c2_et_inl_est = inl(NP_E, 20)       # 503
c2_et_inl_act = inl(NP_E, 200)      # 4463
c2_et_hj = NP_E + NP_T              # 1337
c2_bt_inl = inl(NP_B, 500)          # 11051
c2_bt_hj = NP_B + NP_T              # 1325
save(c2_et_inl_est=c2_et_inl_est, c2_et_inl_act=c2_et_inl_act, c2_et_hj=c2_et_hj,
     c2_bt_inl=c2_bt_inl, c2_bt_hj=c2_bt_hj)
""")
md("""
**Pass 3** — for each 2-table subset, take the plan that was **kept** and join the remaining table with HJ.
1. Based on **estimates**, which plan does the optimizer pick and at what cost? Write the plan as `E-INL-T-HJ-B` or `B-HJ-T-HJ-E`.
2. Recompute the **actual cost** of that same plan.
3. What is the actual cost of the **best** plan?
""")
ans("""
c2_pass3_choice_est = None
c2_pass3_cost_est = None
c2_chosen_plan_actual_cost = None
c2_best_actual_cost = None
save(c2_pass3_choice_est=c2_pass3_choice_est, c2_pass3_cost_est=c2_pass3_cost_est,
     c2_chosen_plan_actual_cost=c2_chosen_plan_actual_cost, c2_best_actual_cost=c2_best_actual_cost)
""", """
est_plans = {"E-INL-T-HJ-B": c2_et_inl_est + NP_B, "B-HJ-T-HJ-E": c2_bt_hj + NP_E}
c2_pass3_choice_est = min(est_plans, key=est_plans.get)          # E-INL-T-HJ-B
c2_pass3_cost_est = est_plans[c2_pass3_choice_est]                # 554
c2_chosen_plan_actual_cost = c2_et_inl_act + NP_B                 # 4514
c2_best_actual_cost = min(c2_et_hj + NP_B, c2_bt_hj + NP_E)       # 1388 (the two HJ plans tie)
print(est_plans, "→ actual", c2_chosen_plan_actual_cost, "vs best", c2_best_actual_cost)
save(c2_pass3_choice_est=c2_pass3_choice_est, c2_pass3_cost_est=c2_pass3_cost_est,
     c2_chosen_plan_actual_cost=c2_chosen_plan_actual_cost, c2_best_actual_cost=c2_best_actual_cost)
""")
md("""
💬 One sentence: why does the error from B1 make the optimizer choose wrongly in pass 2?

#### ★★★ C3 (not graded) — what does real PostgreSQL do with the full query?
Compare its buffers with your `c2_chosen_plan_actual_cost`. How does PostgreSQL join `buyers`, and why does it cost more than the model?
""")
code("""
explain(QUERY)
""")
code('check("task_c")')

# ===================================================================== D
md("""
## D · Extension kick-off (5′) — continue at home
Pick **one** direction and write down a hypothesis and a metric. Deliverable: a notebook/short report with `EXPLAIN` before/after.
1. **Statistics:** `CREATE STATISTICS ... ON city, genre FROM events` with `(dependencies)` and with `(mcv)`. Which one fixes the estimate? Does PostgreSQL change the plan for `QUERY`? (L17 s19, L18)
2. **Histograms:** implement equi-width and equi-depth histograms for `tickets.price` yourself; measure the error vs number of buckets. (L17 s26–35)
3. **Search:** write a DP for 4 tables, add sort-merge join and *interesting orders*; count the plans considered vs L18 s9. (L18 s20–23)
4. **Access method:** an index on `(event_id, price)` to get an index-only scan for `sum(price)`; or compare a hash index with a B+-tree. (L16 s22, s25)
""")
ans("""
d_option = None       # 1..4
d_hypothesis = None
d_metric = None       # what will you measure?
save(d_option=d_option, d_hypothesis=d_hypothesis, d_metric=d_metric)
""", """
d_option = 1
d_hypothesis = "MCV statistics on (city, genre) give an estimate of 200, so PostgreSQL drops the nested loop; dependencies do not."
d_metric = "est rows of the events scan, join type, buffers of QUERY before/after"
save(d_option=d_option, d_hypothesis=d_hypothesis, d_metric=d_metric)
""")

# ===================================================================== Exit
md("""
## Exit ticket (individual)
Using the C2 cost model: **up to how many (actual) Jazz events** is `E' →INL T` still cheaper than `E' ⋈HJ T`?
Compare this number with `sel*` from part A — what do you notice?
""")
ans("""
exit_threshold_events = None
save(exit_threshold_events=exit_threshold_events)
""", """
exit_threshold_events = (1274 - 1) // 22     # 63 + 22x < 63 + 1274  →  x ≤ 57
save(exit_threshold_events=exit_threshold_events)
""")
code("""
check()    # the whole lab
""")
md("Thank you! Please fill in the 2-minute feedback form: **[Canvas link]**.")


# =====================================================================
def build(solution: bool, path: Path):
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    for cell in CELLS:
        kind = cell[0]
        if kind == "md":
            nb.cells.append(nbf.v4.new_markdown_cell(cell[1]))
        elif kind == "code":
            src = cell[1]
            if solution and src.startswith("from labkit"):
                src = ("import os, sys; sys.path.insert(0, '../notebooks')\n"
                       "os.environ['ANSWERS'] = os.path.abspath('answers_solution.json')\n" + src)
            nb.cells.append(nbf.v4.new_code_cell(src))
        else:
            nb.cells.append(nbf.v4.new_code_cell(cell[2] if solution else cell[1]))
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, path)
    print("wrote", path.relative_to(ROOT))


build(False, ROOT / "notebooks" / "lab.ipynb")
build(True, ROOT / "solution" / "solution.ipynb")

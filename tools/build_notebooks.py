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
# Week 6 Lab — How does a database decide how to run your query?
**Access methods · Cost estimation · Plan search** · 60 minutes · work in pairs

When you send SQL to a database, a component called the **query optimizer** picks *how* to run it:
which index to use, and in which order to join the tables. It does this by **guessing the cost** of each option and choosing the cheapest.

Today you will play the optimizer. Every task follows the same three steps:

> **1. Predict** with a formula from the lecture → **2. Measure** with PostgreSQL's `EXPLAIN` → **3. Explain** why the two numbers differ.

### The story
You work for a ticket-selling website. Your manager asks:
*"How much money did **Campus** members spend on **Jazz** concerts in **Hanoi**?"*

| Table | Rows | What is in it |
|---|---:|---|
| `events` | 10,000 | one row per concert: `city`, `genre` |
| `buyers` | 10,000 | one row per customer: `segment` (`Campus`, `VIP`, `Regular`) |
| `tickets` | 200,000 | one row per ticket sold: `event_id`, `buyer_id`, `price` — **20 tickets per event** |

### Words you need (one line each)
| Word | Meaning |
|---|---|
| **page** | the database reads data from disk in blocks of 8 KB called pages. **Cost = number of pages read.** |
| **buffers** | in `EXPLAIN` output, the number of pages PostgreSQL actually read. This is our "measured cost". |
| **selectivity (sel)** | the fraction of rows that pass a filter. `sel = 0.01` means 1% of rows. |
| **Seq Scan** | read the whole table, page by page. |
| **Index Scan** | use an index (like a book's index) to jump to matching rows only. |
| **estimated rows / actual rows** | how many rows PostgreSQL *guessed* vs. how many there *really* were. |

### Plan for the hour
| Minutes | Part | Question | Lecture |
|---|---|---|---|
| 0–5 | Warm-up | Which table would you start from? | L18 |
| 5–17 | **A** Access methods | When is an index worth using? | L16, L18 s6 |
| 17–29 | **B** Cost estimation | How does the optimizer guess row counts — and when is it wrong? | L17 |
| 29–49 | **C** Plan search | How does a wrong guess lead to a slow plan? | L18 |
| 49–55 | Exit ticket | — | — |
| 55–60 | Wrap-up | Back to the warm-up vote | — |

**How to work:** replace every `None` with your answer → run the cell → at the end of each part run `check(...)`.
Tasks marked **(optional)** are for fast pairs; skipping them does not cost you anything.
""")

code("""
from labkit import *          # sql(), explain(), show_pev2(), save(), check()
check("setup")                # you must see ✅ before you start
""")

md("""
## 0 · Warm-up (5 min)
This query answers the manager's question:
```sql
SELECT sum(t.price) FROM tickets t
JOIN events e ON e.id = t.event_id
JOIN buyers b ON b.id = t.buyer_id
WHERE e.city = 'Hanoi' AND e.genre = 'Jazz' AND b.segment = 'Campus';
```
**Your guess:** to answer it, should the database first find the *Jazz concerts in Hanoi* (`events`), or first find the *Campus buyers* (`buyers`)?
There is no wrong answer here — we come back to it at the end.
""")
ans("""
hook_vote = None      # 'events' or 'buyers'
hook_reason = None    # one sentence: why?
save(hook_vote=hook_vote, hook_reason=hook_reason)
""", """
hook_vote = "events"
hook_reason = "Jazz-in-Hanoi sounds rarer than the 500 Campus buyers."
save(hook_vote=hook_vote, hook_reason=hook_reason)
""")

# ===================================================================== A
md("""
## A · Access methods — when is an index worth it? (12 min)
We look at one simple query: **the total price of all tickets for events 1 … n**
```sql
SELECT sum(price) FROM tickets WHERE event_id <= n
```
There is an index on `tickets.event_id`. The tickets are stored in random order on disk (the index is **unclustered**),
so every matching ticket is probably on a different page.

PostgreSQL has two options:

| Option | Idea | Cost in pages (L18 slide 6) |
|---|---|---|
| **Seq Scan** | read every page of the table | `NPages(tickets)` — the same, whatever `n` is |
| **Index Scan** | read the index, then fetch each matching ticket | `(NPages(index) + NTuples(tickets)) × sel` — roughly **1 page per matching ticket** |

💡 **Key idea:** the index is cheap when few rows match, and expensive when many rows match.
There is a **break-even** selectivity `sel*` where both cost the same.

### A1 · Find the break-even point
Run the cell below to read the table and index sizes from PostgreSQL's catalog.
""")
code("""
sql(\"\"\"SELECT relname AS name, relpages AS npages, reltuples::int AS ntuples
       FROM pg_class WHERE relname IN ('tickets', 'idx_tickets_event')\"\"\")
""")
md("""
Copy the two `npages` values, then set the two costs equal and solve for `sel*`:

`(NPages(index) + 200000) × sel* = NPages(tickets)`  →  `sel* = NPages(tickets) / (NPages(index) + 200000)`
""")
ans("""
a1_npages_t = None    # npages of tickets
a1_npages_i = None    # npages of idx_tickets_event
a1_sel_star = None    # write the formula using the two variables above
save(a1_npages_t=a1_npages_t, a1_npages_i=a1_npages_i, a1_sel_star=a1_sel_star)
if a1_sel_star is not None:
    print(f"sel* = {a1_sel_star:.2%} of tickets  ≈  {a1_sel_star * 10_000:.0f} events")
""", """
cat = sql("SELECT relname, relpages FROM pg_class WHERE relname IN ('tickets','idx_tickets_event')").set_index("relname").relpages
a1_npages_t = int(cat["tickets"])
a1_npages_i = int(cat["idx_tickets_event"])
a1_sel_star = a1_npages_t / (a1_npages_i + 200_000)
save(a1_npages_t=a1_npages_t, a1_npages_i=a1_npages_i, a1_sel_star=a1_sel_star)
print(f"sel* = {a1_sel_star:.2%} of tickets  ≈  {a1_sel_star * 10_000:.0f} events")
""")

md("""
### A2 · Check your prediction on PostgreSQL
Each event has 20 tickets, so `event_id <= n` selects `n` out of 10,000 events.
Your `sel*` says the index wins below about **64 events**. Let's test `n = 30` (below) and `n = 150` (above).

(We switch off a third option called *bitmap scan* for now, so PostgreSQL has only the two options from the table.)

✍️ **Predict first:** which scan will PostgreSQL choose for `n = 30`? For `n = 150`?
""")
code("""
p30  = explain(RANGE.format(n=30),  "SET enable_bitmapscan=off")
p150 = explain(RANGE.format(n=150), "SET enable_bitmapscan=off")
display(p30, p150)
""")
md("""
**How to read the output:** each line is one step (a "node") of the plan.
Look for `Index Scan` or `Seq Scan`. `buffers=` on the **first line** is the total number of pages read.
""")
ans("""
a2_scan_30 = None       # 'Index Scan' or 'Seq Scan'
a2_buffers_30 = None    # buffers on the first line of the n=30 plan
a2_scan_150 = None      # 'Index Scan' or 'Seq Scan'
save(a2_scan_30=a2_scan_30, a2_buffers_30=a2_buffers_30, a2_scan_150=a2_scan_150)
""", """
a2_scan_30 = p30.scan["Node Type"]
a2_buffers_30 = p30.buffers
a2_scan_150 = p150.scan["Node Type"]
print(f"formula: {(191 + 200_000) * 30 / 10_000:.0f} pages — measured: {a2_buffers_30}")
save(a2_scan_30=a2_scan_30, a2_buffers_30=a2_buffers_30, a2_scan_150=a2_scan_150)
""")
md("""
💬 Compare `a2_buffers_30` with the formula: `(NPages(index) + 200000) × 30/10000 ≈ 601` pages. Close?

Now switch the **bitmap scan** back on (PostgreSQL's normal setting) and run `n = 150` again.
A bitmap scan first collects all matching ticket locations, **sorts them by page**, and then reads each page only once (L16 slides 24, 29).
""")
code("""
p150_on = explain(RANGE.format(n=150))
p150_on
""")
ans("""
a2_scan_150_bitmap_on = None    # the scan type on the second line
save(a2_scan_150_bitmap_on=a2_scan_150_bitmap_on)
""", """
a2_scan_150_bitmap_on = p150_on.scan["Node Type"]
save(a2_scan_150_bitmap_on=a2_scan_150_bitmap_on)
""")
code("""
# (optional) an interactive picture of the plan — needs internet
show_pev2(p150_on)
""")

md("""
### A3 · Indexes on two columns (L16 slides 14–21)
Imagine an index on `events(city, genre)`. It is sorted like a **phone book sorted by last name, then first name**:
first by `city`, and inside each city by `genre`.

The index can be used if the matching rows sit **next to each other** in that sorted order.
For each filter, answer `True` (the index can be used) or `False`:
1. `city = 'Hanoi' AND genre = 'Jazz'` — like "Nguyen, An"
2. `city = 'Hanoi'` — like "everyone named Nguyen"
3. `genre = 'Jazz'` — like "everyone with first name An"
4. `city > 'H' AND genre = 'Jazz'` — like "last name after H, first name An"
""")
ans("""
a3_matches = [None, None, None, None]    # e.g. [True, False, ...]
save(a3_matches=a3_matches)
""", """
a3_matches = [True, True, False, False]   # 3: no prefix; 4: range on first column → Jazz rows are scattered
save(a3_matches=a3_matches)
""")
md("""
#### (optional) A4 · Clustered index
Run `sql("CLUSTER tickets USING idx_tickets_event")` and `sql("ANALYZE tickets")`, then measure `n = 150` again with bitmap scans off.
Now the tickets are stored in `event_id` order. Use the clustered formula `(NPages(index) + NPages(tickets)) × sel` to explain the new result.
**Afterwards reset the data:** `docker compose down -v && docker compose up -d`.
""")
code('check("task_a")')

# ===================================================================== B
md("""
## B · Cost estimation — how does the optimizer guess? (12 min)
Before running a query, the optimizer must **guess how many rows** each step produces. It only has simple statistics,
for example the number of distinct values in a column (`NKeys`). Three rules from L17:

| Rule | Formula | In words |
|---|---|---|
| equality | `sel(A = c) = 1 / NKeys(A)` | each value is equally common |
| AND | `sel(P1 AND P2) = sel(P1) × sel(P2)` | the two conditions are **independent** |
| join | `|R ⋈ S| = |R| × |S| / NKeys` | each row of R matches `|S| / NKeys` rows of S |

### B1 · Two filters on `events`
""")
code("""
sql(\"\"\"SELECT attname AS column, n_distinct AS nkeys
       FROM pg_stats WHERE tablename = 'events' AND attname IN ('city', 'genre')\"\"\")
""")
md("""
There are 10 cities and 50 genres. ✍️ **Predict** with the rules above: how many of the 10,000 events are Jazz **and** in Hanoi?
""")
ans("""
b1_est = None      # 10000 × sel(city) × sel(genre)
save(b1_est=b1_est)
""", """
b1_est = round(10_000 * (1 / 10) * (1 / 50))
save(b1_est=b1_est)
""")
md("Now ask PostgreSQL. Look at `est rows` (its guess) and `actual rows` (the truth).")
code("""
pb1 = explain("SELECT * FROM events WHERE city = 'Hanoi' AND genre = 'Jazz'")
pb1
""")
ans("""
b1_actual = None
b1_violated_assumption = None   # which assumption in the table above is wrong for this data?
save(b1_actual=b1_actual, b1_violated_assumption=b1_violated_assumption)
""", """
b1_actual = pb1.root["Actual Rows"]
b1_violated_assumption = "independence of predicates — every Jazz event is in Hanoi"
save(b1_actual=b1_actual, b1_violated_assumption=b1_violated_assumption)
""")
md("""
💡 In this dataset **every** Jazz concert is in Hanoi (Hanoi is the jazz city). Knowing the genre tells you the city,
so the two conditions are *not* independent — and the guess is 10× too small.

### B2 · The mistake grows in the join
Each event has 20 tickets. Use the **estimated** number of events from B1:
`estimated tickets = b1_est × 200000 / 10000`.
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
b2_actual = None   # actual rows on the first line
save(b2_actual=b2_actual)
""", """
b2_actual = pb2.root["Actual Rows"]
save(b2_actual=b2_actual)
""")

md("""
#### (optional) B3 · Histograms (L17 slides 31–35)
For a number column like `price`, PostgreSQL keeps an **equi-depth histogram**: 11 boundaries that cut the prices into
10 buckets, each holding about 10% of the tickets.
To estimate `price > 60`: count the buckets completely above 60, add the fraction of the bucket that contains 60, then multiply by 20,000 tickets per bucket.
""")
code("""
bounds = [float(x) for x in sql(\"\"\"SELECT unnest(histogram_bounds::text::numeric[]) AS b
                                   FROM pg_stats WHERE tablename='tickets' AND attname='price'\"\"\").b]
bounds
""")
ans("""
b3_price_gt_60_hand = None   # your estimate (out of 200000 tickets)
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
b3_pg_est = None   # est rows of the Seq Scan line
save(b3_pg_est=b3_pg_est)
""", """
b3_pg_est = pb3.scan["Plan Rows"]
save(b3_pg_est=b3_pg_est)
""")
code('check("task_b")')

# ===================================================================== C
md("""
## C · Plan search — how a wrong guess picks a slow plan (20 min)
To join `events` with `tickets`, PostgreSQL has two main algorithms (L18 slides 11–12):

| Algorithm | How it works | Good when |
|---|---|---|
| **Index nested loop (INL)** | for **each** event, look up its tickets in the index | there are **few** events |
| **Hash join (HJ)** | read **all** tickets once, match them using a hash table | there are **many** events |

### C1 · Watch PostgreSQL choose
PostgreSQL believes there are only 20 Jazz-in-Hanoi events (B1). ✍️ **Predict:** which algorithm will it pick?
We run the query twice: once normally, once with nested loop forbidden (so we can see the hash join).
""")
code("""
SQL_ET = \"\"\"SELECT sum(t.price) FROM events e JOIN tickets t ON t.event_id = e.id
            WHERE e.city = 'Hanoi' AND e.genre = 'Jazz'\"\"\"
pc_nl = explain(SQL_ET)
pc_hj = explain(SQL_ET, "SET enable_nestloop=off")
display(pc_nl, pc_hj)
""")
ans("""
c1_nl_buffers = None   # buffers on the first line of the first plan (Nested Loop)
c1_hj_buffers = None   # buffers on the first line of the second plan (Hash Join)
save(c1_nl_buffers=c1_nl_buffers, c1_hj_buffers=c1_hj_buffers)
""", """
c1_nl_buffers, c1_hj_buffers = pc_nl.buffers, pc_hj.buffers
save(c1_nl_buffers=c1_nl_buffers, c1_hj_buffers=c1_hj_buffers)
""")
md("💬 PostgreSQL picked the plan that reads about **3× more pages**. Why? (Hint: B1.)")

md("""
### C2 · Be the optimizer (System R, L18 slides 12–19)
Now you do what the optimizer does: compute the cost of every plan and keep the cheapest.
We use a simple cost model, in pages:

| Step | Cost in pages |
|---|---|
| read `events` / `buyers` / `tickets` | **63 / 51 / 1274** |
| **INL** into `tickets` | **22 per outer row** (2 index pages + 20 tickets, each on its own page) |
| **HJ** with a table | read that table once (its page count above) |

Short names: **E'** = Jazz-in-Hanoi events (estimated **20**, actually **200**) · **B'** = Campus buyers (**500**) · **T** = tickets.

**Step 1 — join two tables.** The `buyers` rows are done for you as a worked example. Fill in the `events` rows the same way.
""")
ans("""
# worked example: start from Campus buyers (500 rows)
c2_bt_inl = 51 + 500 * 22         # read buyers, then 22 pages per buyer   = 11051
c2_bt_hj  = 51 + 1274             # read buyers, then read tickets once     = 1325

# your turn: start from Jazz-in-Hanoi events
c2_et_inl_est = None              # using the ESTIMATED 20 events
c2_et_inl_act = None              # same formula with the ACTUAL 200 events
c2_et_hj      = None              # read events, then read tickets once
save(c2_et_inl_est=c2_et_inl_est, c2_et_inl_act=c2_et_inl_act, c2_et_hj=c2_et_hj,
     c2_bt_inl=c2_bt_inl, c2_bt_hj=c2_bt_hj)
""", """
c2_bt_inl = 51 + 500 * 22         # 11051
c2_bt_hj  = 51 + 1274             # 1325
c2_et_inl_est = 63 + 20 * 22      # 503
c2_et_inl_act = 63 + 200 * 22     # 4463
c2_et_hj      = 63 + 1274         # 1337
save(c2_et_inl_est=c2_et_inl_est, c2_et_inl_act=c2_et_inl_act, c2_et_hj=c2_et_hj,
     c2_bt_inl=c2_bt_inl, c2_bt_hj=c2_bt_hj)
""")
md("""
The optimizer keeps only the cheapest way to join each pair, judged by its **estimates**:
* {B, T}: HJ (1325) is cheaper than INL (11051) → keep **B' HJ T**
* {E, T}: compare your `c2_et_inl_est` with `c2_et_hj` → which one is kept?

**Step 2 — add the third table** with a hash join. That means adding the pages of the table that is still missing:

| Plan | Estimated cost |
|---|---|
| `E-INL-T-HJ-B` : (E' INL T), then hash join with buyers | `c2_et_inl_est + 51` |
| `B-HJ-T-HJ-E` : (B' HJ T), then hash join with events | `c2_bt_hj + 63` |

1. Which plan does the optimizer choose, and what is its **estimated** cost?
2. What does the chosen plan **really** cost? (Use `c2_et_inl_act` or `c2_bt_hj` instead.)
3. What is the real cost of the **best** plan? (Real cost of both plans, take the smaller.)
""")
ans("""
c2_pass3_choice_est = None          # 'E-INL-T-HJ-B' or 'B-HJ-T-HJ-E'
c2_pass3_cost_est = None            # its estimated cost
c2_chosen_plan_actual_cost = None   # real cost of the chosen plan
c2_best_actual_cost = None          # real cost of the best plan
save(c2_pass3_choice_est=c2_pass3_choice_est, c2_pass3_cost_est=c2_pass3_cost_est,
     c2_chosen_plan_actual_cost=c2_chosen_plan_actual_cost, c2_best_actual_cost=c2_best_actual_cost)
""", """
est_plans = {"E-INL-T-HJ-B": c2_et_inl_est + 51, "B-HJ-T-HJ-E": c2_bt_hj + 63}
c2_pass3_choice_est = min(est_plans, key=est_plans.get)          # E-INL-T-HJ-B
c2_pass3_cost_est = est_plans[c2_pass3_choice_est]                # 554
c2_chosen_plan_actual_cost = c2_et_inl_act + 51                   # 4514
c2_best_actual_cost = min(c2_et_hj + 51, c2_bt_hj + 63)           # 1388 (both hash-join plans tie)
print(est_plans, "→ real", c2_chosen_plan_actual_cost, "vs best", c2_best_actual_cost)
save(c2_pass3_choice_est=c2_pass3_choice_est, c2_pass3_cost_est=c2_pass3_cost_est,
     c2_chosen_plan_actual_cost=c2_chosen_plan_actual_cost, c2_best_actual_cost=c2_best_actual_cost)
""")
md("""
💬 The optimizer did everything right *with the numbers it had* — the plan is slow only because the estimate from B1 was wrong.

#### (optional) C3 · What does PostgreSQL do with the full query?
Compare its buffers with your `c2_chosen_plan_actual_cost`. How does it join `buyers`?
""")
code("""
explain(QUERY)
""")
code('check("task_c")')

# ===================================================================== Exit
md("""
## Exit ticket (individual, 6 min)
With the C2 cost model, joining E' with T costs:
* INL: `63 + 22 × x` pages, where `x` = number of Jazz events
* HJ: `63 + 1274` pages, whatever `x` is

**What is the largest whole number `x` for which INL is still cheaper than HJ?**
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

# ===================================================================== Wrap-up
md("""
## Wrap-up (5 min)
Back to the warm-up: **start from `events` or from `buyers`?**
* With the *estimated* 20 events, starting from `events` with an index nested loop looks cheapest.
* With the *real* 200 events, the hash-join plans are about **3× cheaper**.

**Take-away:** the optimizer's search is correct, but it is only as good as its row estimates.
A single wrong assumption (independence of `city` and `genre`) changes the join algorithm.

## Going further (optional, at home)
Pick **one** and write down what you expect to happen and what you will measure:
1. **Fix the estimate:** `sql("CREATE STATISTICS ev_stats (mcv) ON city, genre FROM events")`, then `sql("ANALYZE events")`. Does `explain(QUERY)` change? Try `(dependencies)` instead of `(mcv)` too.
2. **Histograms:** write your own equi-width and equi-depth histograms for `tickets.price` and compare their errors.
3. **Search:** write a small program that enumerates all left-deep plans for 3–4 tables with the C2 cost model.
4. **Index-only scan:** create an index on `tickets(event_id, price)` and see how the plan for part A changes.
""")
ans("""
d_option = None       # 1..4, or None if you skip it
d_hypothesis = None   # what do you expect?
d_metric = None       # what will you measure?
save(d_option=d_option, d_hypothesis=d_hypothesis, d_metric=d_metric)
""", """
d_option = 1
d_hypothesis = "MCV statistics on (city, genre) give an estimate of 200, so PostgreSQL drops the nested loop; dependencies do not."
d_metric = "est rows of the events scan, join type, buffers of QUERY before/after"
save(d_option=d_option, d_hypothesis=d_hypothesis, d_metric=d_metric)
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

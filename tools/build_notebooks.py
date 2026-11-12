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
# Week 6 Lab: Access Methods, Cost Estimation and Plan Search

Work in pairs. The lab takes 60 minutes.

The query optimizer decides how a database runs a query: which index to use, and in which order to join
the tables. It estimates the cost of each option and picks the cheapest. In this lab you do the same by hand,
in three steps for each task:

1. Work out the answer with a formula from the lecture.
2. Run the query with `EXPLAIN` and read PostgreSQL's numbers.
3. Explain why the two numbers agree or not.

## The data

The database belongs to a website that sells concert tickets. The manager wants to know
how much Campus customers spent on Jazz concerts in Hanoi.

| Table | Rows | One row is |
|---|---:|---|
| `events` | 10,000 | a concert, with its `city` and `genre` |
| `buyers` | 10,000 | a customer, with a `segment`: Campus, VIP or Regular |
| `tickets` | 200,000 | a sold ticket, with `event_id`, `buyer_id` and `price`. Every event has exactly 20 tickets. |

## Words used in this lab

- A **page** is a block of 8 KB. PostgreSQL reads one page at a time, and in this lab
  the cost of a query is the number of pages it reads.
- **buffers** in the output of `EXPLAIN`: the number of pages actually read.
- **selectivity**: the fraction of rows that pass a filter. 0.01 means 1% of the rows.
- **est rows** and **actual rows** in the output of `EXPLAIN`: PostgreSQL's guess, and the true number.

## How to work

Replace each `None` with your answer and run the cell (click it, then press Shift+Enter).
At the end of each part, run the `check(...)` cell. It tells you which answers are right and gives hints for the others.
Tasks marked (optional) are for pairs who finish early.

| Minutes | Part |
|---|---|
| 0–5 | Warm-up |
| 5–17 | Part A: Access methods |
| 17–29 | Part B: Cost estimation |
| 29–49 | Part C: Plan search |
| 49–55 | Exit ticket |
| 55–60 | Wrap-up |

Run the next cell first. It connects to the database and should print "1 check passed".
""")

code("""
from labkit import *      # the helper functions sql(), explain(), save() and check()
check("setup")
""")

md("""
## Warm-up (5 minutes)

This query answers the manager's question:

```sql
SELECT sum(t.price) FROM tickets t
JOIN events e ON e.id = t.event_id
JOIN buyers b ON b.id = t.buyer_id
WHERE e.city = 'Hanoi' AND e.genre = 'Jazz' AND b.segment = 'Campus';
```

To answer it, should the database start with the Jazz concerts in Hanoi (from `events`),
or with the Campus customers (from `buyers`)? Make a guess. There is no wrong answer.
We come back to it at the end of the lab.
""")
ans("""
warmup_vote = None      # 'events' or 'buyers'
warmup_reason = None    # one sentence
save(warmup_vote=warmup_vote, warmup_reason=warmup_reason)
""", """
warmup_vote = "events"
warmup_reason = "Jazz concerts in Hanoi sound rarer than the 500 Campus customers."
save(warmup_vote=warmup_vote, warmup_reason=warmup_reason)
""")

# ===================================================================== A
md("""
## Part A: Access methods (12 minutes, lecture 16)

All tasks in this part use one query, with different values of `n`:

```sql
SELECT sum(price) FROM tickets WHERE event_id <= n
```

There is an index on `tickets.event_id`. It is unclustered: the tickets are not stored in `event_id` order,
so the tickets of one event are spread over many pages. PostgreSQL can run the query in two ways
(lecture 18, slide 6):

- Sequential scan: read every page of the table. Cost: NPages(tickets) pages, whatever `n` is.
- Index scan: look up the matching index entries, then fetch each ticket, which is probably on its own page.
  Cost: about (NPages(index) + NTuples(tickets)) × sel pages, where sel is the selectivity.

The index scan wins when few tickets match. The break-even point is the selectivity where both cost the same.

### A1. The break-even point

Run the next cell. It reads the table and index sizes from PostgreSQL's catalog
and solves NPages(tickets) = (NPages(index) + NTuples(tickets)) × sel.
""")
code("""
size = sql(\"\"\"SELECT relname AS name, relpages AS npages, reltuples::int AS ntuples
              FROM pg_class WHERE relname IN ('tickets', 'idx_tickets_event')\"\"\").set_index("name")
display(size)
npages_t = int(size.npages["tickets"])
npages_i = int(size.npages["idx_tickets_event"])
sel_break_even = npages_t / (npages_i + 200_000)
print(f"break-even selectivity = {npages_t} / ({npages_i} + 200000) = {sel_break_even:.2%} of the tickets")
print(f"that is about {sel_break_even * 10_000:.0f} events, because every event has 20 tickets")
""")

md("""
### A2. Check the break-even point in PostgreSQL

The filter `event_id <= n` selects `n` of the 10,000 events. From A1, the index scan should be cheaper
below about 64 events. We test `n = 30` and `n = 150`.

For now we switch off a third method, the bitmap scan, so that PostgreSQL can only choose between the two scans above.

Before you run the next cell, write down which scan you expect for `n = 30` and for `n = 150`.
""")
code("""
p30 = explain(RANGE.format(n=30), "SET enable_bitmapscan=off")
p150 = explain(RANGE.format(n=150), "SET enable_bitmapscan=off")
display(p30, p150)
""")
md("""
How to read the output: each line is one step of the plan. Look for `Index Scan` or `Seq Scan`.
The number after `buffers=` on the first line is the total number of pages read.
""")
ans("""
a2_scan_30 = None       # 'Index Scan' or 'Seq Scan'
a2_buffers_30 = None    # buffers= on the first line of the n = 30 plan
a2_scan_150 = None      # 'Index Scan' or 'Seq Scan'
save(a2_scan_30=a2_scan_30, a2_buffers_30=a2_buffers_30, a2_scan_150=a2_scan_150)
""", """
a2_scan_30 = p30.scan["Node Type"]
a2_buffers_30 = p30.buffers
a2_scan_150 = p150.scan["Node Type"]
print(f"formula: {(npages_i + 200_000) * 30 / 10_000:.0f} pages, measured: {a2_buffers_30}")
save(a2_scan_30=a2_scan_30, a2_buffers_30=a2_buffers_30, a2_scan_150=a2_scan_150)
""")
md("""
Compare `a2_buffers_30` with the formula: (NPages(index) + 200000) × 30 / 10000 is about 600 pages.

Now run `n = 150` again with the bitmap scan switched back on, which is PostgreSQL's normal setting.
A bitmap scan first collects the locations of all matching tickets, sorts them by page,
and then reads each page only once (lecture 16, slides 24 and 29).
""")
code("""
p150_on = explain(RANGE.format(n=150))
p150_on
""")
ans("""
a2_scan_150_bitmap_on = None    # the scan on the second line
save(a2_scan_150_bitmap_on=a2_scan_150_bitmap_on)
""", """
a2_scan_150_bitmap_on = p150_on.scan["Node Type"]
save(a2_scan_150_bitmap_on=a2_scan_150_bitmap_on)
""")
code("""
# (optional) draw the plan as a picture; this needs an internet connection
show_pev2(p150_on)
""")

md("""
### A3. An index on two columns

Suppose there is an index on `events(city, genre)`, sorted by `city` and then by `genre`,
like a phone book sorted by family name and then by given name. The index matches a filter when all the
entries the filter needs sit next to each other (lecture 16, slides 14 to 21).
Write `True` for each filter the index matches, and `False` otherwise.

1. `city = 'Hanoi' AND genre = 'Jazz'` (phone book: Nguyen, An)
2. `city = 'Hanoi'` (everyone named Nguyen)
3. `genre = 'Jazz'` (everyone with given name An)
4. `city > 'H' AND genre = 'Jazz'` (family names after H, given name An)
""")
ans("""
a3_matches = [None, None, None, None]    # for example [True, False, False, True]
save(a3_matches=a3_matches)
""", """
a3_matches = [True, True, False, False]   # 3: no condition on city; 4: range on city, so the Jazz entries are scattered
save(a3_matches=a3_matches)
""")
md("""
### A4 (optional). A clustered index

`CLUSTER` rewrites the table in `event_id` order, which makes the index clustered:

```python
sql("CLUSTER tickets USING idx_tickets_event")
sql("ANALYZE tickets")
```

Run the `n = 150` query again with bitmap scans switched off, and explain the new buffers
with the clustered formula (NPages(index) + NPages(tickets)) × sel.

Afterwards the Part A checks no longer pass. Reset the database in your terminal with
`docker compose down -v`, then `docker compose up -d`.
""")
code('check("task_a")')

# ===================================================================== B
md("""
## Part B: Cost estimation (12 minutes, lecture 17)

Before it runs a query, the optimizer has to guess how many rows each step returns.
It only has simple statistics, such as NKeys, the number of distinct values in a column.
The lecture gives three rules:

- Equality: sel(A = c) = 1 / NKeys(A). This assumes every value is equally common.
- AND: sel(P1 AND P2) = sel(P1) × sel(P2). This assumes the two conditions are independent.
- Join: |R ⋈ S| = |R| × |S| / max(NKeys(R.A), NKeys(S.A)). This assumes the join values are spread evenly.

### B1. Two filters on events

Run the next cell. It shows the number of distinct values PostgreSQL stores for `city` and `genre`.
""")
code("""
sql(\"\"\"SELECT attname AS column_name, n_distinct AS nkeys
       FROM pg_stats WHERE tablename = 'events' AND attname IN ('city', 'genre')\"\"\")
""")
md("""
There are 10 cities and 50 genres. Use the rules above to estimate how many of the 10,000 events
are Jazz concerts in Hanoi.
""")
ans("""
b1_estimate = None    # 10000 × sel(city) × sel(genre)
save(b1_estimate=b1_estimate)
""", """
b1_estimate = round(10_000 * (1 / 10) * (1 / 50))
save(b1_estimate=b1_estimate)
""")
md("Now ask PostgreSQL. Compare `est rows` (its guess) with `actual rows` (the true number).")
code("""
pb1 = explain("SELECT * FROM events WHERE city = 'Hanoi' AND genre = 'Jazz'")
pb1
""")
ans("""
b1_actual = None       # actual rows
b1_assumption = None   # which assumption in the rules above is wrong for this data? A few words.
save(b1_actual=b1_actual, b1_assumption=b1_assumption)
""", """
b1_actual = pb1.root["Actual Rows"]
b1_assumption = "independence: every Jazz concert is in Hanoi"
save(b1_actual=b1_actual, b1_assumption=b1_assumption)
""")
md("""
In this data, every Jazz concert is in Hanoi. Once you know that a concert is Jazz, you also know its city,
so the two conditions are not independent. That is why the estimate is 10 times too small.

### B2. The mistake carries into the join

Every event has 20 tickets. Use your estimate from B1 to estimate the number of tickets
for Jazz concerts in Hanoi: `b1_estimate × 200000 / 10000`.
""")
ans("""
b2_estimate = None
save(b2_estimate=b2_estimate)
""", """
b2_estimate = round(b1_estimate * 200_000 / 10_000)
save(b2_estimate=b2_estimate)
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
The join estimate is also 10 times too small. A wrong estimate in one step is carried into every step above it.

### B3 (optional). Histograms

For a number column like `price`, PostgreSQL keeps an equi-depth histogram (lecture 17, slides 31 to 35):
11 boundaries that cut the prices into 10 buckets, each holding about 10% of the tickets, so 20,000 tickets.

To estimate `price > 60`: count the buckets that lie completely above 60, add the fraction of the bucket
that contains 60, and multiply by 20,000.
""")
code("""
bounds = [float(x) for x in sql(\"\"\"SELECT unnest(histogram_bounds::text::numeric[]) AS b
                                   FROM pg_stats WHERE tablename='tickets' AND attname='price'\"\"\").b]
bounds
""")
ans("""
b3_my_estimate = None   # your estimate, out of 200000 tickets
save(b3_my_estimate=b3_my_estimate)
""", """
frac = sum(1 if lo >= 60 else (hi - 60) / (hi - lo) if hi > 60 else 0
           for lo, hi in zip(bounds, bounds[1:]))
b3_my_estimate = round(frac / (len(bounds) - 1) * 200_000)
save(b3_my_estimate=b3_my_estimate)
""")
code("""
pb3 = explain("SELECT count(*) FROM tickets WHERE price > 60")
pb3
""")
ans("""
b3_postgres_estimate = None   # est rows on the Seq Scan line
save(b3_postgres_estimate=b3_postgres_estimate)
""", """
b3_postgres_estimate = pb3.scan["Plan Rows"]
save(b3_postgres_estimate=b3_postgres_estimate)
""")
code('check("task_b")')

# ===================================================================== C
md("""
## Part C: Plan search (20 minutes, lecture 18)

To join `events` with `tickets`, PostgreSQL mainly chooses between two join methods:

- Index nested loop (INL): for each event, look up its tickets in the index on `tickets.event_id`.
  This is cheap when there are few events.
- Hash join (HJ): read all tickets once and match them to the events with a hash table.
  This is cheaper when there are many events.

### C1. Watch PostgreSQL choose

From B1, PostgreSQL believes there are only 20 Jazz concerts in Hanoi. Which join method do you expect it to pick?

The next cell runs the join twice: normally, and with nested loops switched off so that you also see the hash join.
""")
code("""
SQL_ET = \"\"\"SELECT sum(t.price) FROM events e JOIN tickets t ON t.event_id = e.id
            WHERE e.city = 'Hanoi' AND e.genre = 'Jazz'\"\"\"
pc_nl = explain(SQL_ET)
pc_hj = explain(SQL_ET, "SET enable_nestloop=off")
display(pc_nl, pc_hj)
""")
ans("""
c1_buffers_nested_loop = None   # buffers= on the first line of the first plan
c1_buffers_hash_join = None     # buffers= on the first line of the second plan
save(c1_buffers_nested_loop=c1_buffers_nested_loop, c1_buffers_hash_join=c1_buffers_hash_join)
""", """
c1_buffers_nested_loop, c1_buffers_hash_join = pc_nl.buffers, pc_hj.buffers
save(c1_buffers_nested_loop=c1_buffers_nested_loop, c1_buffers_hash_join=c1_buffers_hash_join)
""")
md("PostgreSQL picked the plan that reads about 3 times more pages. Why? Think back to B1.")

md("""
### C2. Be the optimizer

Now you choose the plan yourself, the way a System R optimizer does (lecture 18, slides 12 to 19):
work out the cost of each option and keep the cheapest. We use this simple cost model, counted in pages:

| Step | Cost in pages |
|---|---|
| Read `events` | 63 |
| Read `buyers` | 51 |
| Read `tickets` | 1274 |
| Index nested loop into `tickets` | 22 per outer row: 2 index pages and 20 tickets, each on its own page |
| Hash join with a table | the pages of that table, read once |

The Jazz concerts in Hanoi are estimated at 20 and are actually 200. There are 500 Campus customers.

Step 1: join two tables. The two `buyers` lines are worked out for you. Fill in the `events` lines the same way.
""")
ans("""
# worked example: start from the 500 Campus customers
c2_buyers_inl = 51 + 500 * 22     # read buyers, then 22 pages per customer = 11051
c2_buyers_hj = 51 + 1274          # read buyers, then read tickets once = 1325

# your turn: start from the Jazz concerts in Hanoi
c2_events_inl_estimated = None    # with the estimated 20 events
c2_events_inl_actual = None       # with the actual 200 events
c2_events_hj = None               # read events, then read tickets once
save(c2_buyers_inl=c2_buyers_inl, c2_buyers_hj=c2_buyers_hj, c2_events_inl_estimated=c2_events_inl_estimated,
     c2_events_inl_actual=c2_events_inl_actual, c2_events_hj=c2_events_hj)
""", """
c2_buyers_inl = 51 + 500 * 22     # 11051
c2_buyers_hj = 51 + 1274          # 1325
c2_events_inl_estimated = 63 + 20 * 22    # 503
c2_events_inl_actual = 63 + 200 * 22      # 4463
c2_events_hj = 63 + 1274                  # 1337
save(c2_buyers_inl=c2_buyers_inl, c2_buyers_hj=c2_buyers_hj, c2_events_inl_estimated=c2_events_inl_estimated,
     c2_events_inl_actual=c2_events_inl_actual, c2_events_hj=c2_events_hj)
""")
md("""
For each pair of tables, the optimizer keeps only the cheapest join, judged by its estimates:

- `buyers` and `tickets`: the hash join (1325) is cheaper than INL (11051), so it keeps the hash join.
- `events` and `tickets`: compare `c2_events_inl_estimated` with `c2_events_hj`. Which one does it keep?

Step 2: add the third table with a hash join, which adds the pages of that table. That leaves two complete plans:

| Plan | Order of the joins | Estimated cost |
|---|---|---|
| 1 | events, INL into tickets, then hash join with buyers | `c2_events_inl_estimated + 51` |
| 2 | buyers, hash join with tickets, then hash join with events | `c2_buyers_hj + 63` |

1. Which plan does the optimizer choose? Remember that it only knows the estimates.
2. How many pages does that plan actually read? Use the actual 200 events.
""")
ans("""
c2_chosen_plan = None               # 1 or 2
c2_chosen_plan_actual_cost = None   # pages, with the actual 200 events
save(c2_chosen_plan=c2_chosen_plan, c2_chosen_plan_actual_cost=c2_chosen_plan_actual_cost)
""", """
estimated = {1: c2_events_inl_estimated + 51, 2: c2_buyers_hj + 63}
c2_chosen_plan = min(estimated, key=estimated.get)          # plan 1: 554 against 1388
c2_chosen_plan_actual_cost = c2_events_inl_actual + 51      # 4514
print("estimated:", estimated, " chosen:", c2_chosen_plan, " actual cost:", c2_chosen_plan_actual_cost)
save(c2_chosen_plan=c2_chosen_plan, c2_chosen_plan_actual_cost=c2_chosen_plan_actual_cost)
""")
md("""
The cost of plan 2 does not depend on the number of Jazz concerts, so its actual cost is the same as its estimate.
Compare it with `c2_chosen_plan_actual_cost`.

The optimizer did the right thing with the numbers it had. The plan is slow only because the estimate from B1 was wrong.

### C3 (optional). The full query in PostgreSQL

Run the full query from the warm-up. Compare its buffers with `c2_chosen_plan_actual_cost`.
How does PostgreSQL join `buyers`?
""")
code("""
explain(QUERY)
""")
code('check("task_c")')

# ===================================================================== Exit
md("""
## Exit ticket (6 minutes, on your own)

With the cost model from C2, joining the Jazz concerts in Hanoi with `tickets` costs:

- INL: 63 + 22 × x pages, where x is the number of Jazz concerts in Hanoi
- Hash join: 63 + 1274 pages, whatever x is

What is the largest whole number x for which INL is still cheaper than the hash join?
""")
ans("""
exit_max_events = None
save(exit_max_events=exit_max_events)
""", """
exit_max_events = (1274 - 1) // 22     # 63 + 22x < 63 + 1274, so x <= 57
save(exit_max_events=exit_max_events)
""")
code("""
check()    # checks the whole lab
""")

# ===================================================================== Wrap-up
md("""
## Wrap-up (5 minutes)

Back to the warm-up: should the database start from `events` or from `buyers`?

- With the estimated 20 concerts, starting from `events` with an index nested loop looks cheapest.
- With the actual 200 concerts, the hash-join plans read about 3 times fewer pages.

The optimizer's search worked correctly, but it can only be as good as its row estimates.
One wrong assumption, that `city` and `genre` are independent, made it choose the slower join method.

In the lectures but not in this lab: hash index scans, combining two indexes (BitmapAnd in PostgreSQL),
index-only scans, and interesting orders.

## Going further (optional, at home)

Choose one. Before you start, write down what you expect to happen and what you will measure.

1. Fix the estimate. Run `sql("CREATE STATISTICS ev_stats (mcv) ON city, genre FROM events")` and
   `sql("ANALYZE events")`, then run `explain(QUERY)` again. Does the plan change?
   Try `(dependencies)` instead of `(mcv)` as well.
2. Histograms. Build your own equi-width and equi-depth histograms for `tickets.price` and compare their errors.
3. Plan search. Write a small program that lists all left-deep plans for 3 or 4 tables
   and costs them with the C2 cost model.
4. Index-only scan. Create an index on `tickets(event_id, price)` and see how the plans in Part A change.

Options 1 and 4 change the database. Reset it afterwards, as in A4.
""")
ans("""
extension_choice = None       # 1 to 4, or None if you skip it
extension_prediction = None   # what do you expect to happen?
extension_measure = None      # what will you measure?
save(extension_choice=extension_choice, extension_prediction=extension_prediction,
     extension_measure=extension_measure)
""", """
extension_choice = 1
extension_prediction = "With MCV statistics on (city, genre) the estimate becomes 200, so PostgreSQL drops the nested loop. Dependencies statistics do not fix it."
extension_measure = "est rows of the events scan, the join method, and the buffers of QUERY before and after"
save(extension_choice=extension_choice, extension_prediction=extension_prediction,
     extension_measure=extension_measure)
""")
md("Thank you. Please fill in the short feedback form on Canvas before you leave.")


# =====================================================================
def build(solution: bool, path: Path):
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    for i, cell in enumerate(CELLS):
        kind = cell[0]
        if kind == "md":
            new = nbf.v4.new_markdown_cell(cell[1])
        elif kind == "code":
            src = cell[1]
            if solution and src.startswith("from labkit"):
                src = ("import os, sys; sys.path.insert(0, '../notebooks')\n"
                       "os.environ['ANSWERS'] = os.path.abspath('answers_solution.json')\n" + src)
            new = nbf.v4.new_code_cell(src)
        else:
            new = nbf.v4.new_code_cell(cell[2] if solution else cell[1])
        new["id"] = f"cell-{i:03d}"          # fixed ids, so a rebuild without changes gives the same file
        nb.cells.append(new)
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, path)
    print("wrote", path.relative_to(ROOT))


build(False, ROOT / "notebooks" / "lab.ipynb")
build(True, ROOT / "solution" / "solution.ipynb")

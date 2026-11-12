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
# Week 6 Lab: How PostgreSQL Chooses a Plan

Work in pairs. The lab takes 60 minutes.

A query optimizer decides how to run a query: whether to use an index, and how to join the tables.
It estimates the cost of each option and picks the cheapest. In this lab you watch PostgreSQL make
these choices, find out why one of its estimates is wrong, and fix it.

## The data

A website that sells concert tickets. The manager asks: how much did Campus customers spend on Jazz concerts in Hanoi?

| Table | Rows | One row is |
|---|---:|---|
| `events` | 10,000 | a concert, with its `city` and `genre` |
| `buyers` | 10,000 | a customer, with a `segment`: Campus, VIP or Regular |
| `tickets` | 200,000 | a sold ticket, with `event_id`, `buyer_id` and `price`. Every event has exactly 20 tickets. |

## Words used in this lab

- A **page** is a block of 8 KB. PostgreSQL reads one page at a time, so we measure the cost of a query in pages read.
- **buffers** in the plans below: the number of pages actually read.
- **est rows** and **actual rows**: how many rows PostgreSQL expected, and how many there really were.

## How to work

Replace each `None` with your answer and run the cell (click it, then press Shift+Enter).
At the end of each part, run the `check(...)` cell. It marks your answers and gives hints.

| Minutes | Part |
|---|---|
| 0–5 | Warm-up |
| 5–17 | Part A: Index or full scan? |
| 17–27 | Part B: Why the estimate is wrong |
| 27–40 | Part C: What a wrong estimate costs |
| 40–45 | Exit ticket |
| 45–55 | Extra tasks, or time to catch up |
| 55–60 | Wrap-up with the class |

Run the next cell first. It should print "1 check passed".
""")

code("""
from labkit import *      # the helper functions used in this lab
check("setup")
""")

md("""
## Warm-up (5 minutes)

The manager's question needs the tickets of every Jazz concert in Hanoi. The database could get them in two ways:

- (a) For each Jazz concert in Hanoi, look up its tickets in the index on `tickets.event_id`.
- (b) Read all 200,000 tickets once and keep the ones that belong to a Jazz concert in Hanoi.

Which do you think is faster? Make a guess. There is no wrong answer, and we come back to it at the end.
""")
ans("""
warmup_vote = None    # 'a' or 'b'
save(warmup_vote=warmup_vote)
""", """
warmup_vote = "a"
save(warmup_vote=warmup_vote)
""")

# ===================================================================== A
md("""
## Part A: Index or full scan? (12 minutes, lecture 16)

We look at one query, with different values of `n`:

```sql
SELECT sum(price) FROM tickets WHERE event_id <= n
```

Every event has 20 tickets, so the query matches 20 × n tickets. PostgreSQL can use the index on
`tickets.event_id` to find them (Index Scan), or read the whole table (Seq Scan).

### A1. When does PostgreSQL stop using the index?

The next cell runs the query for several values of `n`. For each one it shows the scan PostgreSQL chose
and the number of pages it read. A third method, the bitmap scan, is switched off here to keep the
comparison simple. You can try it in the extra tasks.
""")
code("""
sweep = scan_sweep()
sweep
""")
md("""
1. What is the first `n` in the table for which PostgreSQL uses a Seq Scan?
2. At `n = 30` the query matches 600 tickets. How many pages did the index scan read per matching ticket?
""")
ans("""
a1_first_seq_scan_n = None    # a value of n from the table
a1_pages_per_ticket = None    # pages read at n = 30, divided by 600
save(a1_first_seq_scan_n=a1_first_seq_scan_n, a1_pages_per_ticket=a1_pages_per_ticket)
""", """
a1_first_seq_scan_n = int(sweep.index[sweep.scan == "Seq Scan"][0])
a1_pages_per_ticket = round(sweep.loc[30, "pages read"] / 600, 2)
save(a1_first_seq_scan_n=a1_first_seq_scan_n, a1_pages_per_ticket=a1_pages_per_ticket)
""")
md("""
About one page per ticket. The tickets are not stored in `event_id` order, so the index is unclustered
and each matching ticket sits on a different page. A Seq Scan always reads the whole table, 1274 pages.
So the index stops paying off at about 1274 matching tickets, or about 64 events. That is what the
lecture's formula gives (lecture 18, slide 6). PostgreSQL switches a little later, because its own
cost model is more detailed than the lecture's.

### A2. An index on two columns

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
a2_matches = [None, None, None, None]    # for example [True, False, False, True]
save(a2_matches=a2_matches)
""", """
a2_matches = [True, True, False, False]   # 3: no condition on city; 4: range on city, so the Jazz entries are scattered
save(a2_matches=a2_matches)
""")
code('check("task_a")')

# ===================================================================== B
md("""
## Part B: Why the estimate is wrong (10 minutes, lecture 17)

Before it runs a query, PostgreSQL estimates how many rows each step returns. It uses two rules from the lecture:

- One filter: sel(A = c) = 1 / NKeys(A), where NKeys is the number of distinct values in column A
  and sel is the fraction of rows that pass.
- Two filters with AND: sel(P1 AND P2) = sel(P1) × sel(P2). This assumes the two filters are independent.

### B1. Jazz concerts in Hanoi

The next cell shows the number of distinct values PostgreSQL keeps for `city` and `genre`.
""")
code("""
sql(\"\"\"SELECT attname AS column_name, n_distinct AS nkeys
       FROM pg_stats WHERE tablename = 'events' AND attname IN ('city', 'genre')\"\"\")
""")
md("Use the two rules to estimate how many of the 10,000 events are Jazz concerts in Hanoi.")
ans("""
b1_estimate = None    # 10000 × sel(city) × sel(genre)
save(b1_estimate=b1_estimate)
""", """
b1_estimate = round(10_000 * (1 / 10) * (1 / 50))
save(b1_estimate=b1_estimate)
""")
md("Now ask PostgreSQL. Compare its `est rows` with your estimate, and with `actual rows`.")
code("""
explain("SELECT * FROM events WHERE city = 'Hanoi' AND genre = 'Jazz'")
""")
ans("""
b1_actual = None       # actual rows
b1_assumption = None   # which assumption above is wrong for this data? A few words.
save(b1_actual=b1_actual, b1_assumption=b1_assumption)
""", """
b1_actual = explain("SELECT * FROM events WHERE city = 'Hanoi' AND genre = 'Jazz'").root["Actual Rows"]
b1_assumption = "independence: every Jazz concert is in Hanoi"
save(b1_actual=b1_actual, b1_assumption=b1_assumption)
""")
md("""
PostgreSQL makes the same estimate as you: 20. But in this data every Jazz concert is in Hanoi.
Once you know a concert is Jazz, you know its city, so the two filters are not independent,
and the estimate is 10 times too small.
""")
code('check("task_b")')

# ===================================================================== C
md("""
## Part C: What a wrong estimate costs (13 minutes, lecture 18)

Now the manager's full query. To join `events` with `tickets`, PostgreSQL mainly chooses between two methods,
the same two as in the warm-up:

- Nested loop: for each event, look up its tickets in the index. Cheap when there are few events.
- Hash join: read all tickets once and match them with a hash table. Cheaper when there are many events.

### C1. The plan PostgreSQL picks

From Part B, PostgreSQL believes there are 20 Jazz concerts in Hanoi. Run the full query:
""")
code("""
explain(QUERY)
""")
md("The first line shows the pages read. The second line shows how the tables are joined.")
ans("""
c1_join = None     # the join method on the second line
c1_pages = None    # buffers= on the first line
save(c1_join=c1_join, c1_pages=c1_pages)
""", """
before = explain(QUERY)
c1_join = before.root["Plans"][0]["Node Type"]
c1_pages = before.buffers
save(c1_join=c1_join, c1_pages=c1_pages)
""")
md("""
### C2. Better statistics

`CREATE STATISTICS` tells PostgreSQL to keep statistics on `city` and `genre` together,
so that it can see they depend on each other. The next cell creates these statistics,
fills them with `ANALYZE`, and runs the same query again.
""")
code("""
sql("CREATE STATISTICS IF NOT EXISTS ev_stats (mcv) ON city, genre FROM events")
sql("ANALYZE events")
explain(QUERY)
""")
ans("""
c2_join = None     # the join method on the second line
c2_pages = None    # buffers= on the first line
save(c2_join=c2_join, c2_pages=c2_pages)
""", """
after = explain(QUERY)
c2_join = after.root["Plans"][0]["Node Type"]
c2_pages = after.buffers
print(f"{c1_join}, {c1_pages} pages  ->  {c2_join}, {c2_pages} pages ({c1_pages / c2_pages:.0f} times fewer)")
save(c2_join=c2_join, c2_pages=c2_pages)
""")
md("""
Same query, same data, and about 12 times fewer pages. Only the estimate changed.
With a better estimate, PostgreSQL uses hash joins, which read each table once.
""")
code('check("task_c")')

# ===================================================================== Exit
md("""
## Exit ticket (5 minutes, on your own)

Joining the Jazz concerts in Hanoi with `tickets` costs about:

- Nested loop: 63 + 22 × x pages, where x is the number of concerts.
  That is 63 pages to read `events`, then 22 pages per concert (2 index pages and 20 tickets).
- Hash join: 63 + 1274 pages, whatever x is.

What is the largest whole number x for which the nested loop is still cheaper?
""")
ans("""
exit_max_events = None
save(exit_max_events=exit_max_events)
""", """
exit_max_events = (1274 - 1) // 22     # 63 + 22x < 63 + 1274, so x <= 57
save(exit_max_events=exit_max_events)
""")
code("""
check()    # checks the whole lab; extra tasks you left blank are skipped
""")

# ===================================================================== Extras
md("""
## Extra tasks (if you finish early)

Try any of these, in any order. Run `check("extras")` at the end.

### Extra 1. The bitmap scan (lecture 16, slides 24 and 29)

Part A switched the bitmap scan off. Run `n = 150` with PostgreSQL's normal settings.
A bitmap scan first collects the locations of all matching tickets, sorts them by page,
and then reads each page once. Which scan does PostgreSQL use now, and why can it be cheaper than both scans in Part A?
""")
code("""
explain(RANGE.format(n=150))
""")
md("""
### Extra 2. Histograms (lecture 17, slides 31 to 35)

For a number column like `price`, PostgreSQL keeps an equi-depth histogram: 11 boundaries that cut the prices
into 10 buckets, each holding about 10% of the tickets, so 20,000 tickets. To estimate `price > 60`,
count the buckets that lie completely above 60, add the fraction of the bucket that contains 60, and multiply by 20,000.
""")
code("""
bounds = [float(x) for x in sql(\"\"\"SELECT unnest(histogram_bounds::text::numeric[]) AS b
                                   FROM pg_stats WHERE tablename='tickets' AND attname='price'\"\"\").b]
bounds
""")
ans("""
hist_my_estimate = None   # your estimate, out of 200000 tickets
save(hist_my_estimate=hist_my_estimate)
""", """
frac = sum(1 if lo >= 60 else (hi - 60) / (hi - lo) if hi > 60 else 0
           for lo, hi in zip(bounds, bounds[1:]))
hist_my_estimate = round(frac / (len(bounds) - 1) * 200_000)
save(hist_my_estimate=hist_my_estimate)
""")
code("""
hist_plan = explain("SELECT count(*) FROM tickets WHERE price > 60")
hist_plan
""")
ans("""
hist_postgres_estimate = None   # est rows on the Seq Scan line
save(hist_postgres_estimate=hist_postgres_estimate)
""", """
hist_postgres_estimate = hist_plan.scan["Plan Rows"]
save(hist_postgres_estimate=hist_postgres_estimate)
""")
md("""
### Extra 3. Be the optimizer (lecture 18, slides 12 to 19)

Choose the plan for the full query yourself, the way a System R optimizer does: work out the cost of each option
and keep the cheapest. Use this cost model, in pages:

| Step | Cost in pages |
|---|---|
| Read `events` | 63 |
| Read `buyers` | 51 |
| Read `tickets` | 1274 |
| Nested loop into `tickets` | 22 per outer row |
| Hash join with a table | the pages of that table, read once |

The Jazz concerts in Hanoi are estimated at 20 and are actually 200. There are 500 Campus customers.

Step 1: join two tables. The `buyers` lines are worked out for you. Fill in the `events` lines the same way.
""")
ans("""
# worked example: start from the 500 Campus customers
opt_buyers_nl = 51 + 500 * 22     # read buyers, then 22 pages per customer = 11051
opt_buyers_hj = 51 + 1274         # read buyers, then read tickets once = 1325

# your turn: start from the Jazz concerts in Hanoi
opt_events_nl_estimated = None    # with the estimated 20 events
opt_events_nl_actual = None       # with the actual 200 events
opt_events_hj = None              # read events, then read tickets once
save(opt_buyers_nl=opt_buyers_nl, opt_buyers_hj=opt_buyers_hj, opt_events_nl_estimated=opt_events_nl_estimated,
     opt_events_nl_actual=opt_events_nl_actual, opt_events_hj=opt_events_hj)
""", """
opt_buyers_nl = 51 + 500 * 22     # 11051
opt_buyers_hj = 51 + 1274         # 1325
opt_events_nl_estimated = 63 + 20 * 22    # 503
opt_events_nl_actual = 63 + 200 * 22      # 4463
opt_events_hj = 63 + 1274                 # 1337
save(opt_buyers_nl=opt_buyers_nl, opt_buyers_hj=opt_buyers_hj, opt_events_nl_estimated=opt_events_nl_estimated,
     opt_events_nl_actual=opt_events_nl_actual, opt_events_hj=opt_events_hj)
""")
md("""
Step 2: add the third table with a hash join, which adds the pages of that table. The optimizer compares two plans:

| Plan | Order of the joins | Estimated cost |
|---|---|---|
| 1 | events, nested loop into tickets, then hash join with buyers | `opt_events_nl_estimated + 51` |
| 2 | buyers, hash join with tickets, then hash join with events | `opt_buyers_hj + 63` |

Which plan does the optimizer choose, knowing only the estimates? How many pages does that plan actually read, with 200 events?
""")
ans("""
opt_chosen_plan = None               # 1 or 2
opt_chosen_plan_actual_cost = None   # pages, with the actual 200 events
save(opt_chosen_plan=opt_chosen_plan, opt_chosen_plan_actual_cost=opt_chosen_plan_actual_cost)
""", """
estimated = {1: opt_events_nl_estimated + 51, 2: opt_buyers_hj + 63}
opt_chosen_plan = min(estimated, key=estimated.get)          # plan 1: 554 against 1388
opt_chosen_plan_actual_cost = opt_events_nl_actual + 51      # 4514
save(opt_chosen_plan=opt_chosen_plan, opt_chosen_plan_actual_cost=opt_chosen_plan_actual_cost)
""")
md("""
### Extra 4. A clustered index

`CLUSTER` rewrites the table in `event_id` order, which makes the index clustered.
Run `sql("CLUSTER tickets USING idx_tickets_event")`, then `sql("ANALYZE tickets")`, then `scan_sweep()` again.
What changes, and why?

This changes the data. Afterwards, reset the database in your terminal with
`docker compose down -v`, then `docker compose up -d`.
""")
code('check("extras")')

# ===================================================================== Wrap-up
md("""
## Wrap-up (with the class)

Back to the warm-up. With few concerts, (a) is faster: look up each concert's tickets in the index.
With many, (b) is faster: read all tickets once. PostgreSQL believed there were 20 and chose (a).
There are 200, and the plan with hash joins reads about 12 times fewer pages.

The optimizer's search was fine, but its input was wrong. One assumption, that `city` and `genre` are independent,
made it pick a slow plan, and better statistics fixed it.

## At home (open-ended)

Pick one, write down what you expect, then try it:

1. Run `sql("DROP STATISTICS ev_stats")`, then repeat C2 with `(dependencies)` instead of `(mcv)`.
   Does the plan still change? Look at the est rows and explain why.
2. Write a small program that lists all left-deep join orders for 3 or 4 tables and costs them with the model from Extra 3.
3. Create an index on `tickets(event_id, price)` and run `scan_sweep()` again. Which new scan appears,
   and why does it read so few pages?

Reset the database afterwards: `docker compose down -v`, then `docker compose up -d`.

Please fill in the short feedback form on Canvas before you leave.
""")


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

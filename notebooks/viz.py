"""Pictures for the visual copy of the Week 6 lab (notebooks/lab_visual.ipynb).

Each function reads the lab database, then draws a small self-contained page (inline SVG and
JavaScript, no internet needed) inside the notebook. None of them changes the database:
plans that need other statistics are made inside a transaction that is rolled back.
"""
import html
import json

from IPython.display import HTML, display

import labkit

PAGE_STYLE = """
body { font-family: system-ui, sans-serif; font-size: 13px; color: #1f2328; margin: 8px; }
button { font: inherit; padding: 3px 10px; margin-right: 4px; border: 1px solid #c4c9d0;
         border-radius: 4px; background: #f6f8fa; cursor: pointer; }
button.on { background: #1f6feb; color: white; border-color: #1f6feb; }
.muted { color: #6b7280; } .row { margin: 6px 0; } b.big { font-size: 15px; }
"""


def _show(body, script, height):
    """Render body + script in an iframe, as show_pev2 does, so it works in JupyterLab and Colab."""
    page = (f"<!doctype html><html><head><meta charset='utf-8'><style>{PAGE_STYLE}</style></head>"
            f"<body>{body}<script>{script}</script></body></html>")
    display(HTML(f'<iframe srcdoc="{html.escape(page)}" '
                 f'style="width:100%;height:{height}px;border:1px solid #d0d4da;border-radius:6px"></iframe>'))


# ===================================================================== A: pages read
def pages(max_n=200):
    """Part A. Which pages of `tickets` each scan reads, for events 1 .. n.

    Index Scan follows the index: one page per ticket, in index order, often the same page again later.
    Bitmap scan sorts the pages first and reads each one once. Seq Scan reads every page once.
    """
    size = labkit.sql("""SELECT relname, relpages FROM pg_class
                         WHERE relname IN ('tickets', 'idx_tickets_event')""").set_index("relname").relpages
    npages, index_pages = int(size["tickets"]), int(size["idx_tickets_event"])
    # break-even from the lecture's formula (lecture 18, slide 6), as in the notebook text: about 64 events
    break_even = round(npages / (index_pages + 200_000) * 10_000)
    rows = labkit.sql(f"""SELECT event_id, (ctid::text::point)[0]::int AS page
                          FROM tickets WHERE event_id <= {int(max_n)}
                          ORDER BY event_id, ctid""")      # the order an index scan visits them
    data = {"npages": npages, "be": break_even, "event": rows.event_id.tolist(), "page": rows.page.tolist(), "max": int(max_n)}
    body = """
<div class="row"><b class="big">Which pages does each scan read?</b>
  <span class="muted">Each square is one page (8 KB) of the tickets table.</span></div>
<div class="row">Events 1 to <b id="nval"></b> (<span id="tix"></span> tickets)
  <input id="n" type="range" min="10" max="200" step="10" value="30" style="width:260px;vertical-align:middle"></div>
<div class="row"><button data-m="index" class="on">Index Scan</button><button data-m="bitmap">Bitmap scan</button>
  <button data-m="seq">Seq Scan</button>
  <button id="play" style="margin-left:12px">Play</button></div>
<div style="display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start">
  <div><svg id="grid"></svg>
    <div class="row"><span id="reads"></span></div>
    <div class="row muted" id="explain"></div></div>
  <div><svg id="chart" width="330" height="220"></svg>
    <div class="row muted">Pages read as n grows. The dot is the current n.</div></div>
</div>"""
    script = "const D = " + json.dumps(data) + ";" + r"""
const COLS = 49, S = 9, grid = document.getElementById('grid');
const rowsN = Math.ceil(D.npages / COLS);
grid.setAttribute('width', COLS * S); grid.setAttribute('height', rowsN * S);
const cells = [];
for (let p = 0; p < D.npages; p++) {
  const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  r.setAttribute('x', (p % COLS) * S); r.setAttribute('y', Math.floor(p / COLS) * S);
  r.setAttribute('width', S - 1); r.setAttribute('height', S - 1); r.setAttribute('fill', '#eceef1');
  grid.appendChild(r); cells.push(r);
}
let mode = 'index', n = 30, timer = null;
function order(m, n) {               // the sequence of page reads for this scan
  const pages = [];
  for (let i = 0; i < D.event.length && D.event[i] <= n; i++) pages.push(D.page[i]);
  if (m === 'index') return pages;
  if (m === 'bitmap') return [...new Set(pages)].sort((a, b) => a - b);
  return [...Array(D.npages).keys()];
}
const shade = c => c === 0 ? '#eceef1' : c === 1 ? '#7fb3f5' : c === 2 ? '#2f74d0' : '#123e85';
function paint(seq, upto) {
  const count = new Array(D.npages).fill(0);
  for (let i = 0; i < upto; i++) count[seq[i]]++;
  cells.forEach((r, p) => r.setAttribute('fill', shade(count[p])));
  const distinct = count.filter(c => c > 0).length;
  document.getElementById('reads').innerHTML =
    `<b>${upto}</b> page reads, <b>${distinct}</b> different pages` +
    (upto < seq.length ? ' <span class="muted">(playing)</span>' : '');
}
function explain() {
  const t = {index: 'Follows the index: one page per matching ticket. The tickets are in random order, so many pages are read more than once (darker blue).',
             bitmap: 'Collects the matching tickets first, sorts them by page, then reads each page once.',
             seq: 'Reads the whole table once, whatever n is.'};
  document.getElementById('explain').textContent = t[mode];
}
function chart() {
  const svg = document.getElementById('chart'), W = 330, H = 220, L = 40, B = 24;
  const ns = []; for (let k = 10; k <= D.max; k += 10) ns.push(k);
  const idx = ns.map(k => order('index', k).length), bmp = ns.map(k => order('bitmap', k).length);
  const ymax = 20 * D.max * 1.05;
  const X = k => L + (k / D.max) * (W - L - 8), Y = v => H - B - Math.min(v, ymax) / ymax * (H - B - 8);
  const line = (vals, col) => `<polyline fill="none" stroke="${col}" stroke-width="2" points="${ns.map((k, i) => X(k) + ',' + Y(vals[i])).join(' ')}"/>`;
  const be = D.be;      // (NPages(I) + NTuples(R)) × sel = NPages(R), in events
  const cur = {index: order('index', n).length, bitmap: order('bitmap', n).length, seq: D.npages}[mode];
  svg.innerHTML =
    `<line x1="${L}" y1="${H - B}" x2="${W}" y2="${H - B}" stroke="#999"/><line x1="${L}" y1="8" x2="${L}" y2="${H - B}" stroke="#999"/>` +
    `<text x="${W - 8}" y="${H - 6}" text-anchor="end" font-size="11">n (events)</text>` +
    `<text x="${L - 4}" y="${Y(D.npages) + 4}" text-anchor="end" font-size="10">${D.npages}</text>` +
    line(idx, '#d0453a') + line(bmp, '#2f74d0') +
    `<line x1="${X(0)}" y1="${Y(D.npages)}" x2="${X(D.max)}" y2="${Y(D.npages)}" stroke="#2f9e57" stroke-width="2"/>` +
    `<text x="${X(D.max) - 2}" y="${Y(D.npages) - 4}" text-anchor="end" font-size="11" fill="#2f9e57">Seq Scan</text>` +
    `<text x="${X(D.max * 0.62)}" y="${Y(20 * D.max * 0.62) - 8}" font-size="11" fill="#d0453a">Index Scan</text>` +
    `<text x="${X(D.max) - 2}" y="${Y(bmp[bmp.length - 1]) + 14}" text-anchor="end" font-size="11" fill="#2f74d0">Bitmap scan</text>` +
    (be ? `<line x1="${X(be)}" y1="8" x2="${X(be)}" y2="${H - B}" stroke="#999" stroke-dasharray="3 3"/>` +
          `<text x="${X(be) + 3}" y="18" font-size="10" fill="#555">break-even ≈ ${be}</text>` : '') +
    `<circle cx="${X(n)}" cy="${Y(cur)}" r="5" fill="#111"/>`;
}
function draw() {
  document.getElementById('nval').textContent = n;
  document.getElementById('tix').textContent = 20 * n;
  const seq = order(mode, n); paint(seq, seq.length); explain(); chart();
}
document.getElementById('n').oninput = e => { n = +e.target.value; clearInterval(timer); draw(); };
document.querySelectorAll('button[data-m]').forEach(b => b.onclick = () => {
  document.querySelectorAll('button[data-m]').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); mode = b.dataset.m; clearInterval(timer); draw();
});
document.getElementById('play').onclick = () => {
  clearInterval(timer); const seq = order(mode, n); let i = 0;
  const step = Math.max(1, Math.ceil(seq.length / 150));
  timer = setInterval(() => { i = Math.min(seq.length, i + step); paint(seq, i); if (i >= seq.length) clearInterval(timer); }, 25);
};
draw();
"""
    _show(body, script, 420)


# ===================================================================== B: estimate vs actual
def city_genre():
    """Part B. Concerts per (city, genre): what PostgreSQL assumes against what is in the table."""
    counts = labkit.sql("SELECT city, genre, count(*) AS n FROM events GROUP BY city, genre")
    cities = sorted(counts.city.unique(), key=lambda c: (c != "Hanoi", c))
    genres = sorted(counts.genre.unique(), key=lambda g: (g != "Jazz", g))
    total = int(counts.n.sum())
    by_city = counts.groupby("city").n.sum().to_dict()
    by_genre = counts.groupby("genre").n.sum().to_dict()
    actual = {f"{r.city}|{r.genre}": int(r.n) for r in counts.itertuples()}
    data = {"cities": cities, "genres": genres, "actual": actual, "total": total,
            "pcity": {c: by_city[c] / total for c in cities}, "pgenre": {g: by_genre[g] / total for g in genres}}
    body = """
<div class="row"><b class="big">How many concerts in each city and genre?</b></div>
<div class="row"><button data-v="est" class="on">What PostgreSQL assumes</button>
  <button data-v="act">What is in the table</button></div>
<svg id="heat"></svg>
<div class="row" id="note"></div>"""
    script = "const D = " + json.dumps(data) + ";" + r"""
const S = 13, L = 70, T = 22, GAP = 8, svg = document.getElementById('heat');
const JW = 34;   // the Jazz column is wider, to hold the number
svg.setAttribute('width', L + JW + GAP + (D.genres.length - 1) * S + 10); svg.setAttribute('height', T + D.cities.length * (S + 5) + 10);
let view = 'est';
function value(c, g) {
  return view === 'est' ? D.total * D.pcity[c] * D.pgenre[g] : (D.actual[c + '|' + g] || 0);
}
function color(v) {           // 0 white, 20 light blue, 200 dark blue (square-root scale)
  if (v < 0.5) return '#ffffff';
  const t = Math.sqrt(Math.min(1, v / 200)), l = 92 - t * 62;
  return `hsl(215, 70%, ${l}%)`;
}
function draw() {
  let s = `<text x="${L + JW / 2}" y="14" font-size="11" text-anchor="middle" font-weight="600">Jazz</text>` +
          `<text x="${L + JW + GAP}" y="14" font-size="11" fill="#6b7280">the 49 other genres</text>`;
  D.cities.forEach((c, i) => {
    const y = T + i * (S + 5);
    s += `<text x="${L - 6}" y="${y + S - 1}" text-anchor="end" font-size="11">${c}</text>`;
    D.genres.forEach((g, j) => {
      const v = value(c, g), hot = c === 'Hanoi' && g === 'Jazz';
      const x = j === 0 ? L : L + JW + GAP + (j - 1) * S, w = j === 0 ? JW : S - 1;
      s += `<rect x="${x}" y="${y}" width="${w}" height="${S}" fill="${color(v)}" stroke="${hot ? '#d0453a' : '#d0d4da'}"` +
           ` stroke-width="${hot ? 2 : 0.5}"><title>${c}, ${g}: ${Math.round(v)}</title></rect>`;
      if (j === 0) s += `<text x="${x + w / 2}" y="${y + S - 2}" font-size="10" text-anchor="middle" fill="${v > 100 ? '#fff' : '#1f2328'}">${Math.round(v)}</text>`;
    });
  });
  svg.innerHTML = s;
  const hj = Math.round(value('Hanoi', 'Jazz'));
  document.getElementById('note').innerHTML = view === 'est'
    ? `Independence: every cell is 10,000 × 1/10 × 1/50 = <b>${hj}</b>. The cell for Hanoi and Jazz (red box) gets the same 20 as every other.`
    : `In the table, all Jazz concerts are in Hanoi: the red box holds <b>${hj}</b>, and Jazz in every other city is 0. Knowing the genre tells you the city.`;
}
document.querySelectorAll('button[data-v]').forEach(b => b.onclick = () => {
  document.querySelectorAll('button[data-v]').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); view = b.dataset.v; draw();
});
draw();
"""
    _show(body, script, 300)


# ===================================================================== C: plans before and after
def _plan_in_transaction(with_stats):
    """EXPLAIN ANALYZE of the full query with or without ev_stats, then roll back."""
    conn = labkit._connect()
    try:
        with conn.transaction():
            conn.execute("DROP STATISTICS IF EXISTS ev_stats")
            if with_stats:
                conn.execute("CREATE STATISTICS ev_stats (mcv) ON city, genre FROM events")
                conn.execute("ANALYZE events")
            conn.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            plan = conn.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {labkit.QUERY}").fetchone()[0][0]["Plan"]
            raise labkit.psycopg.Rollback()
    finally:
        conn.close()
    return plan


def _slim(node):
    return {"type": node["Node Type"], "rel": node.get("Relation Name", ""), "index": node.get("Index Name", ""),
            "est": node["Plan Rows"], "act": node["Actual Rows"], "loops": node["Actual Loops"],
            "pages": node.get("Shared Hit Blocks", 0) + node.get("Shared Read Blocks", 0),
            "kids": [_slim(k) for k in node.get("Plans", [])]}


def plans():
    """Part C. The plan for the full query before and after CREATE STATISTICS, side by side.

    Each box is one step of the plan. The two bars compare the rows PostgreSQL expected (grey)
    with the rows it got (blue). A red box means the estimate was off by 5 times or more.
    """
    data = {"before": _slim(_plan_in_transaction(False)), "after": _slim(_plan_in_transaction(True))}
    body = """
<div class="row"><b class="big">The same query, before and after CREATE STATISTICS</b></div>
<div class="row muted">Grey bar: rows PostgreSQL expected. Blue bar: rows it got (per loop). Red box: off by 5× or more.</div>
<div style="display:flex;gap:16px;flex-wrap:wrap">
  <div style="flex:1;min-width:330px"><div class="row"><b>Before</b> <span id="pb"></span></div><div id="before"></div></div>
  <div style="flex:1;min-width:330px"><div class="row"><b>After</b> <span id="pa"></span></div><div id="after"></div></div>
</div>"""
    script = "const D = " + json.dumps(data) + ";" + r"""
const bar = (v, max, col) => `<div style="height:7px;width:${Math.max(2, 140 * Math.log10(1 + v) / Math.log10(1 + max))}px;background:${col};border-radius:2px;margin:2px 0"></div>`;
function maxRows(n) { return Math.max(n.est, n.act, ...n.kids.map(maxRows)); }
function box(n, max) {
  const off = Math.max(n.est, 1) / Math.max(n.act, 1), bad = off >= 5 || off <= 0.2;
  const what = n.rel ? ` on <b>${n.rel}</b>` : '';
  const loops = n.loops > 1 ? ` <span class="muted">× ${n.loops.toLocaleString()} loops</span>` : '';
  return `<div style="border:1px solid ${bad ? '#d0453a' : '#d0d4da'};${bad ? 'background:#fdf1f0;' : ''}border-radius:6px;padding:5px 8px;margin:4px 0">
    <div><b>${n.type}</b>${what}${loops} <span class="muted" style="float:right">${n.pages.toLocaleString()} pages</span></div>
    <div style="display:flex;gap:8px;align-items:center"><div>${bar(n.est, max, '#b8bec7')}${bar(n.act, max, '#2f74d0')}</div>
    <div class="muted" style="font-size:12px">expected ${n.est.toLocaleString()}, got ${n.act.toLocaleString()}</div></div>
    <div style="margin-left:16px">${n.kids.map(k => box(k, max)).join('')}</div></div>`;
}
for (const k of ['before', 'after']) {
  const max = maxRows(D[k]);
  document.getElementById(k).innerHTML = box(D[k], max);
  document.getElementById(k === 'before' ? 'pb' : 'pa').innerHTML =
    `<span class="muted">${D[k].kids[0].type}, </span><b>${D[k].pages.toLocaleString()}</b> pages read`;
}
"""
    _show(body, script, 520)


# ===================================================================== Extra 3: System R search
def system_r():
    """Extra 3. Step through a System R search for the full query, with the lab's cost model.

    Switch between the estimated 20 and the actual 200 Jazz concerts and watch the kept plan change.
    """
    body = """
<div class="row"><b class="big">System R search, one pass at a time</b>
  <span class="muted">Cost in pages, the model from Extra 3.</span></div>
<div class="row">Jazz concerts in Hanoi: <button data-x="20" class="on">estimated 20</button><button data-x="200">actual 200</button></div>
<div class="row"><button data-p="1" class="on">Pass 1: one table</button><button data-p="2">Pass 2: two tables</button>
  <button data-p="3">Pass 3: all three</button></div>
<div id="out"></div>"""
    script = r"""
let x = 20, pass = 1;
const E = 63, B = 51, T = 1274, PER = 22, CAMPUS = 500;
function plans() {
  const p1 = [{set: '{events}', name: "events, filtered (E')", cost: E}, {set: '{buyers}', name: "buyers, filtered (B')", cost: B},
              {set: '{tickets}', name: 'tickets (T)', cost: T}];
  const p2 = [
    {set: '{events, tickets}', name: "E' nested loop into T", cost: E + x * PER, how: `63 + ${x} × 22`},
    {set: '{events, tickets}', name: "E' hash join T", cost: E + T, how: '63 + 1274'},
    {set: '{buyers, tickets}', name: "B' nested loop into T", cost: B + CAMPUS * PER, how: '51 + 500 × 22'},
    {set: '{buyers, tickets}', name: "B' hash join T", cost: B + T, how: '51 + 1274'},
    {set: '{events, buyers}', name: "E' × B' (no join condition)", cost: null, how: 'cross product, never considered'}];
  const best = s => p2.filter(p => p.set === s && p.cost !== null).reduce((a, b) => a.cost <= b.cost ? a : b);
  const et = best('{events, tickets}'), bt = best('{buyers, tickets}');
  const p3 = [{set: '{events, buyers, tickets}', name: `(${et.name}), then hash join buyers`, cost: et.cost + B, how: `${et.cost} + 51`},
              {set: '{events, buyers, tickets}', name: `(${bt.name}), then hash join events`, cost: bt.cost + E, how: `${bt.cost} + 63`}];
  return [p1, p2, p3];
}
function table(list) {
  const sets = [...new Set(list.map(p => p.set))];
  let s = '<table style="border-collapse:collapse;margin-top:6px">';
  for (const set of sets) {
    const group = list.filter(p => p.set === set), costs = group.filter(p => p.cost !== null);
    const min = costs.length ? Math.min(...costs.map(p => p.cost)) : null;
    group.forEach((p, i) => {
      const kept = p.cost !== null && p.cost === min && group.filter(q => q.cost === min).indexOf(p) === 0;
      const style = p.cost === null ? 'color:#9aa1ab;text-decoration:line-through' : kept ? 'font-weight:600' : 'color:#9aa1ab';
      s += `<tr style="border-top:${i ? '0' : '1px solid #d0d4da'}">
        <td style="padding:3px 10px;color:#6b7280">${i ? '' : set}</td>
        <td style="padding:3px 10px;${style}">${p.name}</td>
        <td style="padding:3px 10px;text-align:right;${style}">${p.cost === null ? '' : p.cost.toLocaleString()}</td>
        <td style="padding:3px 10px" class="muted">${p.how || ''}</td>
        <td style="padding:3px 10px">${kept ? '<span style="background:#d3f4dd;color:#145c2c;padding:1px 8px;border-radius:10px;font-size:12px">kept</span>' : ''}</td></tr>`;
    });
  }
  return s + '</table>';
}
function draw() {
  const all = plans();
  let s = table(all[pass - 1]);
  if (pass === 3) {
    const est = (() => { const k = x; x = 20; const r = plans()[2]; x = k; return r; })();
    const pick = est.reduce((a, b) => a.cost <= b.cost ? a : b);
    s += `<div class="row" style="margin-top:8px">With the estimate (20), the optimizer keeps <b>${pick.name}</b>.` +
         (x === 200 ? ` With the actual 200 concerts that plan costs <b>${(E + 200 * PER + B).toLocaleString()}</b> pages, while the best plan costs <b>${Math.min(E + T + B, B + T + E).toLocaleString()}</b>.` : ' Switch to "actual 200" to see what it really costs.') + '</div>';
  } else if (pass === 2) {
    s += '<div class="row muted">Only the cheapest plan for each pair of tables is kept. Pairs without a join condition are skipped.</div>';
  }
  document.getElementById('out').innerHTML = s;
}
document.querySelectorAll('button[data-x]').forEach(b => b.onclick = () => {
  document.querySelectorAll('button[data-x]').forEach(q => q.classList.remove('on')); b.classList.add('on'); x = +b.dataset.x; draw(); });
document.querySelectorAll('button[data-p]').forEach(b => b.onclick = () => {
  document.querySelectorAll('button[data-p]').forEach(q => q.classList.remove('on')); b.classList.add('on'); pass = +b.dataset.p; draw(); });
draw();
"""
    _show(body, script, 330)

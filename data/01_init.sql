-- Week 6 lab dataset: deterministic, no randomness (same data on every machine).
-- events 10,000 | buyers 10,000 | tickets 200,000

DROP TABLE IF EXISTS tickets, events, buyers;

CREATE TABLE events (
    id    int PRIMARY KEY,
    city  text NOT NULL,
    genre text NOT NULL
);

CREATE TABLE buyers (
    id      int PRIMARY KEY,
    segment text NOT NULL
);

CREATE TABLE tickets (
    id       int PRIMARY KEY,
    event_id int NOT NULL REFERENCES events(id),
    buyer_id int NOT NULL REFERENCES buyers(id),
    price    numeric(8,2) NOT NULL
);

-- ---------------------------------------------------------------- events
-- genre: (id-1) % 50  -> 50 genres x 200 events (2% each). Genre 0 = 'Jazz'.
-- city : 10 cities x 1,000 events (10% each).
--        Every Jazz event is in Hanoi (designed correlation).
--        The 9,800 non-Jazz events are spread in a hash order:
--        first 800 -> Hanoi, then 1,000 each to the other 9 cities.
-- Independence estimate: 10,000 * 0.10 * 0.02 = 20 events; actual = 200.
WITH g AS (
    SELECT id,
           CASE WHEN (id-1) % 50 = 0 THEN 'Jazz'
                ELSE 'Genre' || lpad(((id-1) % 50)::text, 2, '0') END AS genre
    FROM generate_series(1, 10000) AS id
), nonjazz AS (
    SELECT id, row_number() OVER (ORDER BY md5('e' || id)) - 1 AS r
    FROM g WHERE genre <> 'Jazz'
)
INSERT INTO events
SELECT g.id,
       CASE
         WHEN g.genre = 'Jazz' OR n.r < 800 THEN 'Hanoi'
         ELSE (ARRAY['HCMC','Danang','Hue','Haiphong','Cantho',
                     'Nhatrang','Dalat','Vinh','Quynhon'])[((n.r - 800) / 1000)::int + 1]
       END,
       g.genre
FROM g LEFT JOIN nonjazz n USING (id);

-- ---------------------------------------------------------------- buyers
-- 500 Campus members (id % 20 = 0), i.e. 5%.
INSERT INTO buyers
SELECT id,
       CASE WHEN id % 20 = 0 THEN 'Campus'
            WHEN id % 3  = 0 THEN 'VIP'
            ELSE 'Regular' END
FROM generate_series(1, 10000) AS id;

-- ---------------------------------------------------------------- tickets
-- k = 0..199,999 ; event_id = k/20 + 1          -> exactly 20 tickets per event
-- buyer_id = ((7919*k + 12345) mod 200000) mod 10000 + 1
--   (bijection on 0..199,999)                   -> exactly 20 tickets per buyer
--   and, because gcd(7919,20)=1, every Jazz event has exactly one Campus ticket
--   -> |Jazz-in-Hanoi tickets bought by Campus| = 200 exactly.
-- price: log-normal (skewed), derived from md5 -> deterministic.
-- Physical order is shuffled (ORDER BY md5) so event_id is NOT clustered.
INSERT INTO tickets
SELECT k + 1,
       k / 20 + 1,
       ((7919::bigint * k + 12345) % 200000) % 10000 + 1,
       round(exp(3.6 + 0.7 * sqrt(-2 * ln(u1)) * cos(2 * pi() * u2))::numeric, 2)
FROM (
    SELECT k,
           (('x' || substr(md5('p' || k), 1, 8))::bit(32)::bigint + 1) / 4294967297.0 AS u1,
           (('x' || substr(md5('p' || k), 9, 8))::bit(32)::bigint)     / 4294967296.0 AS u2
    FROM generate_series(0, 199999) AS k
) s
ORDER BY md5('t' || k);

CREATE INDEX idx_tickets_event ON tickets(event_id);
CREATE INDEX idx_tickets_buyer ON tickets(buyer_id);

-- Small histogram on price so students can compute B3 by hand (10 buckets).
ALTER TABLE tickets ALTER COLUMN price SET STATISTICS 10;

VACUUM ANALYZE events;
VACUUM ANALYZE buyers;
VACUUM ANALYZE tickets;

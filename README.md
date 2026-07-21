# Dublin Kids' Summer — activities finder

A browsable, filterable finder for children's summer activities across Dublin's museums,
libraries, parks and workshops. A parent opens it, filters (type / age / free-only /
drop-in-only / hide booked-out), and clicks straight through to book.

## What's already here (don't rebuild — run it, then improve)

- **`index.html`** — the working frontend. Vanilla HTML/CSS/JS, no build step. Loads
  `data/events.json` via fetch and renders a filterable, date-grouped list. Light + dark.
- **`data/events.json`** — the current dataset (~146 events, summer 2026), hand-gathered
  21 Jul 2026. Schema below.
- **`SCRAPING.md`** — every source, how it behaves, and the gotchas. This is the real IP;
  read it before writing the scraper.

Run locally:
```
cd projects/kids-activities
python3 -m http.server 8000     # then open http://localhost:8000
```
(Open via a server, not `file://` — fetch needs http.)

## Data schema (one row = one event on one date)
```
{ date, iso, day, time, venue, activity, category, ages, status,
  book (how to book), cost, link, area, ageTags[] }
```
- `category`: Museum · Library · Workshop · Camp · Show · Park
- `status`: Available · Limited · Waitlisted · Full · Sold out · No booking needed
- `book`: Drop-in · Book online · Contact branch · Register once
- `area`: Dublin City · dlr · South Dublin · Bray / D.L.
- `link`: the exact booking / detail URL

## Goal
Keep it **current** — that's the whole point. A live, smaller dataset beats a stale complete one.

## Status (21 Jul 2026)
1. **Deploy — DONE.** Live at https://pftzgrld.github.io/dublin-kids-summer/
   (public repo `pftzgrld/dublin-kids-summer`, GitHub Pages from main branch root).
2. **Calendar view — DONE.** Month-grid toggle next to Filters; category dots +
   per-day counts; click a day for its events; respects all filters.
3. **All branches — DONE** for Dublin City (all DCC branches incl. Central Library via
   `dublincity.ie/events` types 184/223), dlr (all branches via the Drupal listing), and
   SDCC (Ballyroan Eventbrite). Scope agreed 21 Jul: DCC + dlr + SDCC, no Fingal. UI
   narrows by area (new Area filter chips). Non-scraped venues (IMMA, The Ark, Mermaid,
   Pavilion, Hugh Lane, National Gallery, RHA, Print Museum) live in
   `data/manual-events.json` and merge at build — move each to a scraper over time.
4. **Booking links — audited 21 Jul.** 65 unique links, one 403 (Hugh Lane blocks
   curl; fine in a browser). Scraped rows link to the page that carries the booking
   action or detail; Eventbrite rows link straight to the ticket page.
5. **Booking status — DONE at scrape time** for all scraped sources (dlr inline text,
   Eventbrite JSON-LD availability, DCC/NMI page text) and **re-polled each run** for
   manual-seed venues (`scraper/status.py`). Ticket Tailor / FareHarbor / Hugh Lane need
   the headless pass, which runs in CI (Playwright); skipped when run locally without it.
6. **Scraper — DONE.** `python3 scraper/build.py` rebuilds `data/events.json`.
   Weekly GitHub Action (`.github/workflows/refresh.yml`, Mondays 10:30 Irish, after
   the Eventbrite booking window opens) rebuilds, commits, and Pages redeploys.
   Recurring events are parsed as rules ("Every Friday in July at 11am") and expanded
   at build within a 45-day horizon. A failed source keeps its previous rows — a broken
   parser never empties the site.

## Constraints
- Framework-light. Vanilla is fine at this size and deploys as static files; only reach for
  Vite/React if the calendar view genuinely needs it.
- Freshness > coverage.
- The frontend only ever reads `data/events.json`. All gathering happens in the scraper.

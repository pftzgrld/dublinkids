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

## Tasks (roughly in order)
1. **Deploy** to my host (Netlify / GitHub Pages / Cloudflare Pages). I hold the account —
   scaffold it and give me the exact click-steps. A GitHub Action on a weekly cron pairs
   naturally with GitHub Pages for the scraper.
2. **Calendar view** — a month-grid toggle alongside the existing list.
3. **Pull ALL branches, not a whitelist.** The current dataset only has the handful of
   branches originally flagged — that's a prototype shortcut and must be replaced with full
   coverage. The council calendars are already all-branch central listings: ingest the whole
   family/children programme from `dublincity.ie/events`, `libraries.dlrcoco.ie/events-listing`
   (category filters in SCRAPING.md), and the SDCC/Eventbrite system. Tag every event by
   branch + area so the UI narrows by area. Also add non-library venues missed in the first pass.
   Scope to decide with me: which councils (default Dublin City + dlr + South Dublin; add
   Fingal / north side only if wanted).
4. **Booking links** — audit each so it lands on the *actual* booking step, not a landing page.
5. **Booking status (broad)** — for *every* event that needs booking, poll its source each run
   and surface current availability (Available / Limited / Waitlisted / Full / Sold out) on the
   card. Drop-ins show "No booking needed." "Hide booked-out" filters on this.
6. **Scraper** — the real work. Refresh `data/events.json` weekly. Sources + behaviour in
   `SCRAPING.md`. Store recurring events as rules and expand at build; don't hand-embed data.

## Constraints
- Framework-light. Vanilla is fine at this size and deploys as static files; only reach for
  Vite/React if the calendar view genuinely needs it.
- Freshness > coverage.
- The frontend only ever reads `data/events.json`. All gathering happens in the scraper.

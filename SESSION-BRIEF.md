# Dublin Kids — session brief

A browsable, filterable finder for children's activities across Dublin and
north Wicklow. A parent opens it, filters by type / age / area, and clicks
straight through to the specific booking page.

## Where everything is

- **Live:** https://dublinkids.com (custom domain, HTTPS enforced)
- **Repo:** `github.com/pftzgrld/dublinkids` — GitHub Pages from `main` root.
  This project folder (`projects/kids-activities`) is its own git repo nested
  inside claude-os; commit/push from here, not the parent.
- **Old link redirect:** `pftzgrld/dublin-kids-summer` is a stub repo that
  301s the old github.io URL to dublinkids.com (people had the old link).
- **DNS:** bought on Squarespace; five records point the apex + www at GitHub
  Pages. Set up and working — don't touch unless the domain moves.
- **Analytics:** GoatCounter is wired in (pageviews + per-venue booking-click
  events). NB: that commit wasn't part of the main build thread — confirm with
  Patrick what account it reports to.

## How it's built

- **`index.html`** — the whole frontend. Vanilla HTML/CSS/JS, no build step,
  Google-style light-only design (Roboto, primary-colour category chips).
  Reads `data/events.json` and renders a date-grouped list + a month calendar
  panel. Installable as a home-screen web app (manifest + icons). The frontend
  **only ever reads events.json** — all gathering happens in the scraper.
- **`data/events.json`** — the built dataset (~413 rows). Regenerated each run.
- **`scraper/`** — one module per source, orchestrated by `build.py`:
  - `common.py` — shared helpers: `fetch` (browser-UA + retry), `event_row`
    (the schema + derives `ageTags`/`free`/`dropin`/`ok`), `age_tags`,
    `parse_time_range`, `parse_day_month`, `expand_rule`, `status_from_text`,
    `clean_summary` (dormant — summaries are stripped at build, see below).
  - `src_dcc.py` `src_dlr.py` `src_nmi.py` `src_sdcc.py` (Ballyroan + Fingal
    Eventbrite) `src_wicklow.py` `src_imma.py` `src_ark.py` — the scrapers.
  - `status.py` — re-polls booking status for the manual-seed venues.
  - `build.py` — runs every source, expands `data/recurring.json` (always-on
    museum drop-ins), merges `data/manual-events.json`, de-dups, drops
    pre-season rows, **strips `summary`**, **re-derives `ageTags`** from
    ages+title, writes events.json.
- **`data/recurring.json`** — hand-maintained always-on drop-ins (IMMA daily
  tour, National Gallery atrium, Dead Zoo Lab), expanded to dated rows.
- **`data/manual-events.json`** — seed for venues without a scraper yet
  (Mermaid, Pavilion, Hugh Lane, RHA, National Gallery, Print Museum). Booking
  status re-polled each run.
- **Weekly refresh:** `.github/workflows/refresh.yml`, Mondays 10:30 Irish —
  installs Playwright, runs `build.py`, commits events.json, Pages redeploys.

## Run / rebuild / deploy

```
python3 scraper/build.py            # rebuild data/events.json (needs playwright for imma/ark)
python3 -m http.server 8101         # then open localhost:8101 (serve, not file://)
git add -A && git commit && git push # Pages redeploys in ~1 min
```
Per-source failure guard: if a scraper errors or returns nothing, the previous
rows for it are kept — a broken parser never empties the site.

## Sources & coverage (current)

| src | venue(s) | method | notes |
|-----|----------|--------|-------|
| dcc | all Dublin City libraries incl. Central | `dublincity.ie/events?type=184/223`, paginated, server-rendered | per-date booking links ("Book for Tue 21 July" → DCC Spydus RNI page) captured per date |
| dlr | all DLR library branches | events-listing **views AJAX** paginated (use the page's `view_dom_id`) + event-calendar page | the "of 131" counter is all-time; only ~35 are actually served. Deep-link via **IRN** (`QRY=IRN(<id>)`) — session-scoped FULL urls resolve to the WRONG event |
| nmi | NMI Archaeology + Collins Barracks | browser-UA curl of the events pages | excludes the adult "Dublin by Dusk" evening series |
| sdcc | Ballyroan Library | Eventbrite org + `org/<id>/showmore` JSON | |
| fingal | Fingal County Libraries | same Eventbrite showmore (in `src_sdcc.py`) | mostly Blanchardstown; kid-signal filter |
| wicklow | Bray/Ballywaltrim/Greystones/Enniskerry + Whale Theatre | Wicklow **Spydus** ENQ search (server-rendered over a session) | deep-link via **IRN**; Whale needs Playwright (currently comedy/adult only) |
| imma | IMMA family workshops/tours | Playwright render of the summer pages | Ticketsolve deep-links for bookable; excludes adult workshops |
| ark | The Ark, Temple Bar | browser-UA curl of `ark.ie/events/view/<slug>` | irregular dates (camp blocks, exhibition runs, one-offs); most of its programme is autumn (out of the 45-day horizon) and rolls in later |

Areas: Dublin City · Fingal · DLR · South Dublin · North Wicklow.

## Hard-won conventions (don't relearn these)

- **Deep-link to the specific event, never a landing/list page.** Every scraper
  does this. The stable-id tricks: Wicklow/DLR Spydus = **IRN**; DCC per-date
  booking = **RNI** page; Ark/IMMA/Whale = **Ticketsolve** show; Eventbrite =
  the ticket URL. Session-scoped urls (Spydus FULL, views AJAX) are NOT stable.
- **Browser-UA curl** gets 200 where the built-in fetchers get 403. Cloudflare/
  JS holdouts (IMMA, Ticketsolve, Ticket Tailor, Hugh Lane) need Playwright.
- **Age filter = 4 buckets** (under5/5to8/9to12/teen). `age_tags` parses a
  numeric span and returns the buckets it overlaps; activity WORDS cap the top
  (storytime/colouring → 8, sensory/baby/toddler → 4) so "3+ storytime" isn't
  tagged teen. The card **badge is derived from ageTags** (Under 5 / 5–8 /
  9–12 / Teens / Up to 8 / 5–12 / 9+ / All ages) — never show raw "Families".
- **Summaries are OFF.** Extraction code is dormant; `build.py` strips the
  field; the card shows none. Titles are self-evident. (Decision after a live
  sample — see chat history.) Re-enable = stop stripping + render the line.
- **Adult events leak in** via craft/workshop keywords — exclude by name
  (adult/yoga/needlework/book club/exhibition/teacher/schools/on-demand/18+).
- Horizon is **45 days** (`HORIZON_DAYS`). Recurring rules and open-ended runs
  expand only within it; autumn events appear as the window advances.

## Open questions Patrick is bringing in

**1. "Is there a way to scrape all of a website to find buried content?"**
(e.g. `dlrcoco.ie/arts/municipal-gallery-dlr-lexicon/.../kcat-exhibition-learning-programme#learning-programme-calendar`
— note this is the **main dlrcoco.ie council site, a different host** from the
libraries subsite, and looks to have its own gallery-education calendar.)
- Don't blind-crawl (too noisy). The efficient move is **sitemap-driven
  discovery**: fetch `/sitemap.xml` for each host (dlrcoco.ie, dublincity.ie,
  fingal.ie, wicklow.ie, museum.ie…), enumerate every URL, filter by
  kid-relevant keywords in the path/title (child/family/kids/junior/gallery-
  learning/storytime/camp/workshop), and produce a **candidate list** to
  hand-review. Also worth: each site's own search, and `site:` web searches.
- Recommended next step: write a one-off `discover.py` that pulls the sitemaps,
  keyword-filters, and prints candidate URLs grouped by host. Patrick reviews,
  we promote the good ones to real sources. The dlr gallery learning programme
  is likely the first new source out of that (it's a real venue we don't cover:
  the Municipal Gallery / LexIcon exhibition-learning calendar).

**2. Clubs-and-groups — include the ones with clear schedules.**
`libraries.dlrcoco.ie/news-events/clubs-and-groups` — category pages (Lego &
Builder Clubs, Storytime, Junior Book Clubs, Parent & Toddler Groups, Board
Game/Gaming Clubs). Each lists per-branch clubs with a prose schedule.
- Reality: some are vague ("one Saturday a month", "alternating Saturdays,
  check here") → skip. **Many are clear** ("every Tuesday 3.30pm", "first
  Saturday 11am") → Patrick wants these **in**. It's just laborious.
- Recommended approach: a **`src_dlr_clubs.py`** that fetches the kid category
  pages, parses each club block into a rule (branch + weekday/nth-weekday +
  time + link), and expands with `expand_rule`/an nth-weekday helper within the
  horizon. Drop the ones whose schedule can't be parsed to concrete dates
  (don't invent dates). Same pattern as `recurring.json` but scraped. Book-by-
  email clubs → book="Contact branch", link to the clubs page section.
- This generalises: DCC and other councils have similar "regular clubs" pages;
  the nth-weekday expansion helper would serve all of them.

## Backlog / smaller threads

- Wicklow **Whale Theatre**: scraper is in place but their listing is currently
  comedy/adult; family shows/panto will flow in when listed.
- Map view (a third toggle) — geocode the ~40 venues once, Leaflet pins. Not
  started; nothing blocks it.
- Recurring museum drop-ins repeat once per day in the list — could collapse to
  a single "on most days" entry if the repetition grates.
- Spot-checking age tags is ongoing — each miss becomes a rule in `age_tags`.

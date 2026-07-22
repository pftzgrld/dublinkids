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
- **`data/events.json`** — the built dataset (~515 rows). Regenerated each run.
- **`scraper/`** — one module per source, orchestrated by `build.py`:
  - `common.py` — shared helpers: `fetch` (browser-UA + retry), `event_row`
    (the schema + derives `ageTags`/`free`/`dropin`/`ok`), `age_tags`,
    `parse_time_range`, `parse_day_month`, `expand_rule`, `status_from_text`,
    `clean_summary` (dormant — summaries are stripped at build, see below).
  - `src_dcc.py` `src_dlr.py` `src_nmi.py` `src_sdcc.py` (Ballyroan + Fingal
    Eventbrite) `src_wicklow.py` `src_imma.py` `src_ark.py`
    `src_dlr_clubs.py` (dlr recurring clubs from prose schedules) — the
    scrapers.
  - `discover.py` — one-off sitemap sweep across the council/museum hosts;
    writes keyword-filtered candidate URLs to `DISCOVERY.md` for hand review.
    Not part of build.py.
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
| dlrclubs | dlr branches' regular clubs (junior book, Lego, gaming, board games, parent & toddler, storytime) | clubs-and-groups + children-and-families category pages; prose schedules parsed to weekly / nth-weekday rules, expanded within the horizon | only CONCRETE schedules become rows — 'one Saturday a month' / 'alternating' / 'fortnightly' are dropped, never guessed; see SCRAPING.md '22 Jul' section |
| sdccevents | SDCC council events (fun days, cinema days, sports camps, parks) | sitemap-driven: fresh /en/events/*.html detail pages; Eventbrite JSON-LD date fallback | the /en/events/ search is JS — don't fight it, the sitemap has everything |
| dccblog | DCC 'Children's Summer Programme' blog post | h2 branch / li 'Title, Weekday D Month at time' | carries events MISSING from the events listing; src_dcc must stay before it in SOURCES so listing rows win de-dup |
| hughlane | Hugh Lane Gallery (offsite programme — gallery shut for refurb) | Eventbrite org 10755329962 via src_sdcc ORGS | 0 rows until the autumn programme lists — that's correct, not broken |
| fingalevents | Fingal council events (BlanchFest etc.) | /events/browse cards | explicit family signal required; concerts excluded |

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

## Done 22 Jul (were the open questions)

**1. Buried-content discovery — built.** `scraper/discover.py` sweeps the
sitemaps of 11 hosts and writes `DISCOVERY.md` (~445 candidates, grouped by
host, freshest first) for Patrick to review. It found the trigger example —
the Municipal Gallery / LexIcon **KCAT exhibition-learning programme** on
dlrcoco.ie (fresh, updated Jul 2026) — plus promising SDCC finds (family fun
days, sports camps under `/en/imeachtai`, Clondalkin kids-events PDFs): SDCC
proper is barely covered today (Ballyroan Eventbrite only). wicklow.ie,
museum.ie, ark.ie, nationalgallery.ie expose no XML sitemap (the latter three
are covered by scrapers/manual seed anyway).
**Next:** Patrick reviews DISCOVERY.md; promote winners to sources — the KCAT
gallery-learning calendar and the SDCC events pages look like the first two.

**2. Clubs with clear schedules — built.** `src_dlr_clubs.py` is live in
build.py (src `dlrclubs`, ~101 rows): 16 clubs parsed to concrete dates
(weekly + nth-weekday incl. Irish 'Gach Déardaoin'), 11 vague/adult ones
correctly dropped. Break notes ('until September'), bank-holiday-weekend
exclusions, and months-vs-years age units all handled — details in
SCRAPING.md. The nth-weekday machinery lives in the module and can be lifted
for other councils' clubs pages (DCC has similar) when we do them.

## Backlog / smaller threads

- Wicklow **Whale Theatre**: scraper is in place but their listing is currently
  comedy/adult; family shows/panto will flow in when listed.
- Map view (a third toggle) — geocode the ~40 venues once, Leaflet pins. Not
  started; nothing blocks it.
- Recurring museum drop-ins repeat once per day in the list — could collapse to
  a single "on most days" entry if the repetition grates.
- Spot-checking age tags is ongoing — each miss becomes a rule in `age_tags`.

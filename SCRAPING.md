# Scraping notes — sources & gotchas (proven 21 Jul 2026)

The golden rule: **send a real browser User-Agent with `curl` and most sites return 200.**
The built-in fetch/WebFetch tools get 403 — they advertise themselves as bots.

```
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
curl -sSL -A "$UA" "<url>"
```

## Per source

**museum.ie (National Museum of Ireland — Archaeology, Collins Barracks/Dead Zoo Lab)**
- Browser-UA curl works. Listing pages: `/en-ie/museums/archaeology/events`,
  `/en-ie/museums/decorative-arts-history/events`.
- Event detail pages live under `/en-IE/Museums/<branch>/Events/2026/Q3-.../<slug>`;
  the visible text carries exact **date, time, ages**. Drop-in workshops are free / no booking.
- The "Let's Explore…" family drop-ins run many dates, two sessions/day (11:00–13:00 & 14:00–16:00).

**Eventbrite (Ballyroan library, SDCC)**
- Org page: `https://www.eventbrite.ie/o/ballyroan-library-2184216231`. Extract
  `/e/<slug>-tickets-<id>` links; each event page has **JSON-LD** with `startDate` (clean).
  Availability is in the Eventbrite data too. Events are added weekly (booking opens Mon 10am).

**dlr Libraries (LexIcon, Dundrum, Blackrock, Ballyogan, Shankill, Deansgrange, Dalkey)**
- `https://libraries.dlrcoco.ie/events-listing` is Drupal. Filter by category term id:
  `?field_event_category_target_id=90` (Family & Children), `120` (Events for the Young),
  `117` (Storytime), `607` (Sensory), `116` (Library Services for the Young).
- Detail pages `/events-and-news/event-calendar/<slug>` carry **time + ages** in the text,
  and often the booking status inline (e.g. "*Event Fully Booked*").
- Ticketed ones book via **Ticket Tailor** (`tickettailor.com/events/dlrlibraries`) — Cloudflare
  protected → needs a **headless browser**. But the detail page usually already has the time.

**Dublin City libraries (Rathmines, Kevin St, Terenure, Pembroke, + Central/Ilac to add)**
- Central calendar: `https://www.dublincity.ie/events` (per-event `/events/<slug>`). Branch
  pages only show the next 2–3. Recurring clubs (storytime, Lego, toddler) are here too.

**National Print Museum**
- Site loads, but tour/workshop times & prices live in a **FareHarbor** widget
  (`fareharbor.com/embeds/book/nationalprintmuseum/`) → **headless browser**. Categories:
  "Tours and Demos", "Workshops for Children & Young People".

**Normal sites (browser-UA curl fine):** IMMA, National Gallery, RHA, Mermaid Arts, Pavilion, The Ark.
**Cloudflare / JS holdouts (need headless browser):** Ticket Tailor, Hugh Lane (403 even with UA), FareHarbor.

## Booking status (the important one)
For **every event that requires booking**, fetch its booking source each run and record the
current availability into `status`: `Available` / `Limited` / `Waitlisted` / `Full` / `Sold out`.
Drop-ins get `No booking needed`. Sources: dlr detail pages (inline text), Eventbrite (JSON),
FareHarbor (spaces remaining), Ticketsolve/Ticket Tailor (headless). Surface it on every
bookable card in the UI.

## Recurring events
Store as **rules** (venue + weekday + time + date-range + link), expand to dated rows at build
time. Do NOT store 42 duplicate rows — that was a prototype shortcut.

## Learned in the 21 Jul build (v1 scraper)

- **dublincity.ie/events** is server-rendered after all — event links are ABSOLUTE
  (`https://www.dublincity.ie/events/<slug>`), which is why relative-href greps miss them.
  Filter with `?type=184` (Kids & Family Fun) and `?type=223` (Library Event, keyword-filter
  to kids), paginate `&page=N`. Detail pages: venue sits between the H1 and "Times & Dates";
  the schedule is prose ("Every Friday in July at 11am") — parse as a rule and expand.
- **Eventbrite JSON-LD** script tags carry `data-next-head=""` — match
  `<script type="application/ld+json"[^>]*>`, not the bare tag. Plain `requests` with a
  browser UA is fine (no TLS blocking). Availability: `offers[].availability` SoldOut /
  LimitedAvailability.
- **dlr detail pages** are noisy: phone numbers ("01 280 1147") and map coordinates
  ("53.292419") look like times. Only accept times with an explicit am/pm marker there
  (`parse_time_range(..., require_ampm=True)`).
- **Time-range parsing generally:** require `:`/`.` between hour and minutes, validate
  h≤23 m≤59, and only join two times with "&" when the "&" literally sits between them
  in the source text (else "2pm & 3pm shows" logic corrupts plain ranges).
- **Adult events leak** into the children's category listings on both dlr and Eventbrite —
  exclude on title keywords (adult, 18+).
- Hugh Lane 403s curl but works in a real browser — status polling for it must go through
  the Playwright pass (CI only).

## dlr correction (21 Jul, afternoon)

The category term ids above are DEAD — the vocabulary changed (no more Family & Children
90 / Events for the Young 120 / Services for the Young 116; current terms include 117
Storytime, 607 Sensory Session, 599 Arts & Crafts). An unknown term id silently returns
the UNFILTERED listing, which is what broke coverage. Also:
- `/events-listing?page=N` does NOT paginate — the pager is a Drupal views "Load More"
  (view `bones_page_listing_blocks`, display `block_2`, POST /views/ajax) and even that
  ignores the page param (single page of results).
- The fullest link source is `/events-and-news/event-calendar` itself; the scraper unions
  it with the listing node and the views/ajax block (each surfaces events the others miss).
- Kid-filtering now happens by keyword on the detail page, not by category term.
- dlr staff append "*Event is Fully Booked*" to the TITLE — strip it, keep the status,
  and treat such events as bookable (Contact branch), never drop-in.

## Fingal (added 21 Jul, evening)

- Fingal Libraries book via **Eventbrite**, organiser `fingal-county-libraries-19927793883`
  (heavy on Blanchardstown, their maker-space branch). The static org page shows only the
  first batch of events — the full future list comes from the JSON endpoint
  `eventbrite.ie/org/<org_id>/showmore/?page_size=50&type=future&page=N`
  (`data.events[].url`, paginate until `has_next_page` is false). Works for Ballyroan too.
- Fingal's org mixes adult and kids events — require a kid signal in name+description
  (ages, "7-10 years old", teen, family...) before keeping; Ballyroan stays exclude-adult-only.
- `fingal.ie/events/browse` exists (filters: type 345 = Libraries, location per town) but is
  mostly festivals/one-offs; not scraped yet — BlanchFest-type events would come from there.

## North Wicklow (added 21 Jul, late)

- **Wicklow Libraries = Spydus** (wicklow.spydus.ie). The events home is a JS shell but the
  ENQ search URLs are server-rendered over a plain requests session:
  `ENQ/WPAC/EVSESENQ?QRY=EVSCFLG:0 + EVSEDTE:">= TODAY"&NRECS=300` (URL-encoded) returns one
  date-sorted page reaching past the horizon; recurring events arrive pre-expanded, one dated
  record each. Cards: title anchor, `.d-block` date/time + `Wicklow <Branch>` location,
  `.event-free` / `.event-noregistration` flags. Record detail URLs are session-scoped — link
  to the stable events home instead. Facet-URL filtering (EVSESLOC) exists in the UI but the
  QRY syntax isn't guessable; client-side branch filtering is easier.
- Branch reality check: Ballywaltrim (Bray) has the big children's programme; Bray Library a
  few; Greystones is currently all adult groups (their YA Manga Club starts 5 Sep); Enniskerry
  is tiny. No Delgany branch — Greystones is the catchment.
- **Whale Theatre** (Greystones) = Ticketsolve behind Cloudflare → Playwright render of
  `/ticketbooth/shows`, kid-filter by title/category. Currently comedy/concerts only; the
  scraper is in place for when family shows/panto list. Playwright is now installed locally
  as well as in CI.
- 'Young adult' must not trip the adult filter — lookbehind `(?<!young )\badults?\b`.

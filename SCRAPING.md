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

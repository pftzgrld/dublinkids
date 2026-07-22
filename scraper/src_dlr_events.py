"""dlr county events (dlrcoco.ie/dlr-events) — the MAIN council site's own
events system, separate from the libraries subsite.

Found 22 Jul via the KCAT litmus test: the arts/heritage/parks family
programme (clown shows, Harry Potter science, Bricks4Kidz, Dalkey Castle
living history, biodiversity walks) lives here and nowhere else. Listing
paginates with ?page=N; detail pages carry 'Saturday 29 August 2026', a
venue name, category labels ('Events for the Young', 'Family & Children'),
time ('3.00 - 4.00 pm'), 'Cost | Free' and booking prose. Library events
also appear here — src_dlr must stay BEFORE this module in SOURCES so the
libraries rows (with booked-out detection) win the de-dup where titles
match. Date-RANGE pages ('13 July - 6 September' festival containers) are
skipped rather than expanded — the dated child events carry the rows.
"""
import re
from bs4 import BeautifulSoup

from common import (fetch, event_row, parse_day_month, parse_time_range,
                    status_from_text, today)

BASE = "https://www.dlrcoco.ie"

KID_CAT_RX = re.compile(r"Events for the Young|Family & Children", re.I)
KID_RX = re.compile(r"child|kids?\b|famil|junior|teen|toddler|baby|lego|"
                    r"storytime|young audiences|ages?\s*\d", re.I)
# NOT a bare \badult — kids' pages say 'accompanied by an adult'
ADULT_RX = re.compile(r"for adults|adults? only|adult event|18\+|over 18|"
                      r"camera club|decoupage|repair cafe|entrepreneur", re.I)
VENUE_RX = re.compile(
    r"\b(dlr Lexicon|dlr LexIcon|Blackrock Library|Deansgrange Library|"
    r"Dundrum Library|Dalkey Library|Shankill Library|Cabinteely Library|"
    r"Stillorgan Library|Ballyogan Library|Sallynoggin Library|"
    r"Dalkey Castle|Fernhill Park|County Hall|Deansgrange Cemetery|"
    r"National Maritime Museum|Marlay House|Marlay Park|Cabinteely Park|"
    r"The Oratory|Killiney Hill|Peoples Park|dlr County)\b")


def listing_links():
    links, page = set(), 0
    while page < 12:
        r = fetch(f"{BASE}/dlr-events?page={page}")
        if not r:
            break
        new = set(re.findall(r"/dlr-events/event/[a-z0-9-]+", r.text))
        if not new - links:
            break
        links |= new
        page += 1
    return sorted(links)


def parse_detail(url):
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup.body
    text = main.get_text(" | ", strip=True)
    h1 = soup.select_one("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    # filter on the event's own description only — the page footer promotes
    # OTHER events ('Napkin Decoupage') that poison whole-page matching
    desc = text.split("Event Description", 1)[-1].split("| Share")[0]
    head = text[:400]
    if not title or ADULT_RX.search(title + " " + desc):
        return None
    if not (KID_CAT_RX.search(head) or KID_RX.search(title + desc)):
        return None

    if re.search(r"\d{1,2}\s+\w+\s*[-–]\s*\d{1,2}\s+\w+", head):
        return None                      # festival container with a range
    dm = re.search(r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\s+"
                   r"(\d{1,2}\s+\w+\s+\d{4})", head)
    # some events show just '26 July' with no weekday/year (the walks)
    iso = parse_day_month(dm.group(1) if dm else head)
    if not iso or iso < today().isoformat():
        return None

    status = status_from_text(title + " | " + text)
    title = re.sub(r"\s*\*+\s*Event (is )?Fully Booked\s*\*+", "", title,
                   flags=re.I).strip()
    vm = VENUE_RX.search(text)
    venue = vm.group(1) if vm else "dlr County"
    if venue.lower() == "dlr lexicon":
        venue = "dlr LexIcon"

    online = main.select_one('a[href*="eventbrite"], a[href*="tickettailor"]')
    if online:
        book, link = "Book online", online["href"].split("?")[0]
    elif re.search(r"booking is (needed|required)|to book|booking essential",
                   text, re.I) or status != "Available":
        book, link = "Contact branch", BASE + url if url.startswith("/") \
            else url
    else:
        book, link = "Drop-in", BASE + url if url.startswith("/") else url
        status = "No booking needed"

    if re.search(r"workshop|craft|doodle|lego|writing", title, re.I):
        cat = "Workshop"
    elif re.search(r"show|film|clown|magic|music|storytell", title, re.I):
        cat = "Show"
    elif re.search(r"tour|heritage|history|castle|museum", title, re.I):
        cat = "Museum"
    elif "librar" in venue.lower():
        cat = "Library"
    else:
        cat = "Park"
    ages_m = re.search(r"ages?\s*:?\s*(\d{1,2}\s*(?:years?\s*)?\+|"
                       r"\d{1,2}\s*[-–]\s*\d{1,2})", text, re.I)
    ages = re.sub(r"\s|years?", "", ages_m.group(1)) if ages_m else "Children"
    cost = "Free" if re.search(r"Cost \| Free|\bfree\b", text, re.I) \
        else "See link"
    # the time sits in its own field two segments before 'Cost'
    # ('… | 3.00 - 4.00 pm | dlr Lexicon | Cost | Free | …'); ranges there
    # often mark only the end with pm ('3.00 - 4.00 pm')
    time_str = None
    segs = [s.strip() for s in text.split(" | ")]
    if "Cost" in segs:
        i = segs.index("Cost")
        time_str = parse_time_range(" | ".join(segs[max(0, i - 3):i]))
        tm = re.match(r"(\d{2}):(\d{2})–(\d{2}):(\d{2})$", time_str or "")
        if tm and int(tm.group(1)) < 8 and int(tm.group(3)) >= 12:
            time_str = f"{int(tm.group(1)) + 12}:{tm.group(2)}" \
                       f"–{tm.group(3)}:{tm.group(4)}"
    if not time_str:
        time_str = parse_time_range(text, require_ampm=True)

    return event_row(iso=iso, time_str=time_str, venue=venue, activity=title,
                     cat=cat, ages=ages, status=status, book=book, cost=cost,
                     link=link, area="DLR", source="dlrevents")


def scrape():
    rows = []
    for url in listing_links():
        row = parse_detail(BASE + url)
        if row:
            rows.append(row)
    return rows

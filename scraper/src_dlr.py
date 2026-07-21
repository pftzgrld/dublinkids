"""dlr Libraries (all branches) via the central Drupal events listing.

Listing: libraries.dlrcoco.ie/events-listing?field_event_category_target_id=N
for each children's category. Detail pages carry date, time, venue, cost and
often the booking state inline ('Event Fully Booked').
"""
import re
from bs4 import BeautifulSoup

from common import (fetch, event_row, expand_rule, parse_day_month,
                    parse_time_range, status_from_text, today)

BASE = "https://libraries.dlrcoco.ie"
CATEGORIES = {90: "Family & Children", 120: "Events for the Young",
              117: "Storytime", 607: "Sensory",
              116: "Library Services for the Young"}
AGES_BY_CAT = {117: "Toddlers", 607: "Families"}


def listing_links():
    seen = {}
    for term in CATEGORIES:
        for page in range(0, 10):
            r = fetch(f"{BASE}/events-listing"
                      f"?field_event_category_target_id={term}&page={page}")
            if not r:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select(".views-row")
            if not rows:
                break
            for row in rows:
                a = row.select_one("a[href]")
                if not a:
                    continue
                url = a["href"]
                if not url.startswith("http"):
                    url = BASE + url
                if "/event-calendar/" in url and url not in seen:
                    seen[url] = term
            if len(rows) < 10:
                break
    return seen


def parse_detail(url, term):
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup.body
    text = main.get_text(" | ", strip=True)
    title = (soup.select_one("h1") or soup.title).get_text(" ", strip=True)

    # Venue: first branch-looking token; the field appears twice in the text
    vm = re.search(r"\b(dlr LexIcon|dlr Lexicon|Dundrum|Blackrock|Ballyogan|"
                   r"Shankill|Deansgrange|Dalkey|Cabinteely|Stillorgan|"
                   r"Sallynoggin|Glencullen)\b", text)
    venue = vm.group(1) if vm else "dlr library"
    if venue.lower() == "dlr lexicon":
        venue = "dlr LexIcon"
    elif "dlr" not in venue:
        venue += " Library"

    if re.search(r"\badult", title, re.I):
        return None
    time_str = parse_time_range(text, require_ampm=True)

    dates = []
    # Date line sits between the title and the venue, e.g.
    # 'Saturday 25th July 2026' or 'Every Tuesday, 2026'
    head = text.split("Event Description")[0]
    if re.search(r"\bevery\b", head, re.I):
        dates = expand_rule(head)
    if not dates:
        iso = parse_day_month(head)
        if iso:
            dates = [iso]

    status = status_from_text(text)
    booked_online = main.select_one('a[href*="tickettailor"], '
                                    'a[href*="eventbrite"]')
    if booked_online:
        book, link = "Book online", booked_online["href"]
    elif re.search(r"booking (is )?(required|essential)|book (a place|now)|"
                   r"registration required", text, re.I):
        book, link = "Contact branch", url
    else:
        book, link = "Drop-in", url
        status = "No booking needed"

    cost = "Free" if re.search(r"Cost \| Free", text) else \
        ("Free" if re.search(r"\bfree\b", text, re.I) else "See link")
    ages_m = re.search(r"ages?\s*:?\s*(\d+\s*[-–]\s*\d+|\d+\+)", text, re.I)
    ages = ages_m.group(1).replace(" ", "") if ages_m \
        else AGES_BY_CAT.get(term, "Children")
    return {"title": title, "venue": venue, "dates": dates, "time": time_str,
            "book": book, "link": link, "ages": ages, "status": status,
            "cost": cost}


def scrape():
    rows = []
    for url, term in listing_links().items():
        d = parse_detail(url, term)
        if not d or not d["dates"]:
            continue
        for iso in d["dates"]:
            if iso < today().isoformat():
                continue
            rows.append(event_row(
                iso=iso, time_str=d["time"], venue=d["venue"],
                activity=d["title"], cat="Library", ages=d["ages"],
                status=d["status"], book=d["book"], cost=d["cost"],
                link=d["link"], area="dlr", source="dlr"))
    return rows

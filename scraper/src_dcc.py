"""Dublin City Council central events calendar — all branches.

Listing: dublincity.ie/events?type=<term>&page=N (server-rendered Drupal).
Type 184 = Kids & Family Fun (take everything), 223 = Library Event (keep
child-flavoured ones only). Detail pages carry 'Times & Dates' as either a
concrete date or a recurring-rule phrase, which we expand at build time.
"""
import re
from bs4 import BeautifulSoup

from common import (fetch, event_row, expand_rule, parse_day_month,
                    parse_time_range, status_from_text)

BASE = "https://www.dublincity.ie"
TYPES = {184: "kids", 223: "library"}
KID_RX = re.compile(
    r"child|kids?\b|famil|toddler|story\s*time|storytime|lego|teen|baby|"
    r"junior|youth|boardgame|board game|colouring|schoolchildren", re.I)
CAT_RULES = [
    ("Camp", re.compile(r"\bcamp\b", re.I)),
    ("Show", re.compile(r"\bfilm|cinema|theatre|concert|puppet|magic show|"
                        r"panto", re.I)),
    ("Park", re.compile(r"\bpark\b|outdoor|playground", re.I)),
]


def categorise(title, venue, text):
    for cat, rx in CAT_RULES:
        if rx.search(title) or rx.search(text[:400]):
            return cat
    if "library" in venue.lower() or "librar" in text[:200].lower():
        return "Library"
    return "Workshop"


def listing_events():
    """Yield (url, teaser_text) for every kid-relevant event."""
    seen = set()
    for type_id, flavour in TYPES.items():
        for page in range(0, 12):
            r = fetch(f"{BASE}/events?type={type_id}&page={page}")
            if not r:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("main .base-card__title a[href]")
            if not cards:
                break
            for a in cards:
                url = a["href"]
                if not url.startswith("http"):
                    url = BASE + url
                if "/events/" not in url or url in seen:
                    continue
                card = a.find_parent(class_=re.compile("base-card")) or a
                outer = card.parent.get_text(" ", strip=True) if card.parent \
                    else a.get_text(" ", strip=True)
                if flavour == "library" and not KID_RX.search(outer):
                    continue
                seen.add(url)
                yield url, outer


def parse_detail(url):
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup.body
    text = main.get_text(" | ", strip=True)
    title = (soup.select_one("h1") or soup.title).get_text(" ", strip=True)

    # 'Times & Dates' block holds the schedule phrase
    m = re.search(r"Times & Dates \| ([^|]+)", text)
    when = m.group(1).strip() if m else ""
    # Venue is usually the field right after the title; failing that, a
    # branch name is often embedded in the title or body text
    m = re.search(re.escape(title) + r" \| ([^|]+) \| Times & Dates", text)
    venue = m.group(1).strip() if m else ""
    if not venue or len(venue) > 45:
        vm = (re.search(r"([A-Z][\w'’-]+(?: [A-Z][\w'’-]+)? Library)", title)
              or re.search(r"([A-Z][\w'’-]+(?: [A-Z][\w'’-]+)? Library)",
                           text))
        venue = vm.group(1) if vm else "Dublin City venue"

    time_str = parse_time_range(when) or parse_time_range(text[:1500])

    dates = []
    if re.search(r"\bevery\b|\bweekly\b|days\b", when, re.I):
        dates = expand_rule(when)
    if not dates:
        iso = parse_day_month(when) or parse_day_month(text[:800])
        if iso:
            dates = [iso]

    # Booking: an external ticketing link if present, else the event page
    book, link = "Contact branch", url
    for a in main.select("a[href]"):
        h = a["href"]
        if re.search(r"eventbrite|ticket|bookwhen|forms\.", h, re.I):
            book, link = "Book online", h
            break
    if re.search(r"drop.?in|no booking (needed|required)|just (turn up|drop)",
                 text, re.I):
        book, link = "Drop-in", url

    ages_m = re.search(r"(?:suitable for )?ages?[sd]?\s*:?\s*([\d]+\s*[-–+]\s*"
                       r"[\d]*\+?|[\d]+\+)", text, re.I)
    ages = ages_m.group(1).replace(" ", "") if ages_m else \
        ("Families" if KID_RX.search(text) else "All ages")

    status = status_from_text(text)
    cost = "Free" if re.search(r"\bfree\b", text, re.I) else "See link"
    return {
        "title": title, "venue": venue, "dates": dates, "time": time_str,
        "book": book, "link": link, "ages": ages, "status": status,
        "cost": cost, "cat": categorise(title, venue, text),
    }


def scrape():
    rows = []
    for url, _teaser in listing_events():
        d = parse_detail(url)
        if not d or not d["dates"]:
            continue
        status = d["status"] if d["book"] != "Drop-in" else "No booking needed"
        for iso in d["dates"]:
            rows.append(event_row(
                iso=iso, time_str=d["time"], venue=d["venue"],
                activity=d["title"], cat=d["cat"], ages=d["ages"],
                status=status, book=d["book"], cost=d["cost"], link=d["link"],
                area="Dublin City", source="dcc"))
    return rows

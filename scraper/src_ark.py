"""The Ark — children's cultural centre, Temple Bar (ark.ie/events).

Listing links are /events/view/<slug>; browser-UA curl works. Detail pages
carry a 'Dates & Times' block, an age range, a price, and (for ticketed
events) a Ticketsolve booking link. The Ark's date phrasing is irregular —
camp blocks ('13-17 Jul or 20-24 July'), exhibition runs open Wed-Sat, and
one-off dated performances ('Sat 3 Oct @ 1.30pm') — so the date reader covers
each shape and keeps only what lands in the build horizon. School / online /
teacher-course events are filtered out.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from common import (fetch, event_row, parse_time_range, today, HORIZON_DAYS,
                    MONTHS)

BASE = "https://ark.ie"
MON3 = {m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)}
# not public children's events
EXCLUDE_RX = re.compile(
    r"school|teacher|on-?demand|streaming|broadband|connection point|"
    r"\bcpd\b|online workshop|classroom|christmas carol", re.I)


WD = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _iso(day, mon, year):
    try:
        return dt.date(year, mon, day).isoformat()
    except ValueError:
        return None


def _year_for(mon):
    t = today()
    return t.year + 1 if mon < t.month - 1 else t.year


def extract_dates(text):
    """Return the iso dates an event runs on, within the horizon. Handles
    camp blocks ('13-17 Jul'), open-day runs ('Open Wed – Sat' across a run),
    and one-off dated performances."""
    t = re.sub(r"\s+", " ", text)
    lo, hi = today(), today() + dt.timedelta(days=HORIZON_DAYS)
    found = set()

    def add(iso):
        if iso and lo.isoformat() <= iso <= hi.isoformat():
            found.add(iso)

    # every explicit 'D Month' — used both as one-off dates and to find the
    # run's end
    explicit = []
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
                         r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
                         t, re.I):
        iso = _iso(int(m.group(1)), MON3[m.group(2)[:3].lower()],
                   _year_for(MON3[m.group(2)[:3].lower()]))
        if iso:
            explicit.append(iso)

    # consecutive-day blocks '13-17 Jul' (camps), incl. 'A-B or C-D'
    for m in re.finditer(r"\b(\d{1,2})\s*[–-]\s*(\d{1,2})\s+"
                         r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
                         t, re.I):
        mon = MON3[m.group(3)[:3].lower()]
        for d in range(int(m.group(1)), int(m.group(2)) + 1):
            add(_iso(d, mon, _year_for(mon)))

    # open-day run: 'Open[ing] [Every] Wed [– Sat]' across the run's span
    om = re.search(r"Open(?:ing)?\s+(?:Every\s+)?"
                   r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*"
                   r"(?:\s*[–-]\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*)?",
                   t, re.I)
    if om and explicit:
        a = WD[om.group(1)[:3].lower()]
        b = WD[om.group(2)[:3].lower()] if om.group(2) else a
        days = list(range(a, b + 1)) if a <= b else [a]
        end = dt.date.fromisoformat(max(explicit))
        d = lo
        while d <= min(end, hi):
            if d.weekday() in days:
                add(d.isoformat())
            d += dt.timedelta(days=1)
    else:
        for iso in explicit:
            add(iso)
    return sorted(found)


def parse_detail(url):
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup.body
    raw_title = re.sub(r"\s+", " ",
                       (soup.select_one("h1") or soup.title)
                       .get_text(" ", strip=True))
    # the Ark appends the date span to the H1 — drop it
    title = re.sub(r"\s+\d{1,2}(st|nd|rd|th)?\s+"
                   r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                   r"\w*.*$", "", raw_title, flags=re.I).strip(" :–-")
    text = main.get_text(" | ", strip=True)
    if EXCLUDE_RX.search(title) or EXCLUDE_RX.search(text[:600]):
        return None

    is_run = bool(re.search(r"exhibition|installation", title, re.I)) \
        or bool(re.search(r"Open(?:ing)?\s+(?:Every\s+)?(Mon|Tue|Wed|Thu|Fri|"
                          r"Sat|Sun)", text, re.I))
    m = re.search(r"Dates?\s*&?\s*(Times?|Age)[^|]*((\s*\|\s*[^|]+){0,12})",
                  text)
    dates_sec = (m.group(0) if m else text[:600]).replace("|", " ")
    dates = extract_dates(dates_sec)
    if not dates:
        return None

    time_str = parse_time_range(dates_sec)
    if is_run:
        tm = re.search(r"(\d{1,2}[:.]\d{2}\s*[ap]m?\s*[–-]\s*\d{1,2}[:.]?"
                       r"\d{0,2}\s*[ap]m)", text)
        time_str = parse_time_range(tm.group(1)) if tm else "See times"

    ages_m = re.search(r"(?:for )?ages?\s*:?\s*(\d+\s*[-–+]\s*\d*\+?|\d+\+)",
                       text, re.I)
    ages = ages_m.group(1).replace(" ", "") if ages_m else "Families"
    price_m = re.search(r"€\s?\d+(?:/€?\d+)?", text)
    free = bool(re.search(r"\bfree\b", text, re.I)) and not price_m
    cost = "Free" if free else (price_m.group(0).replace(" ", "")
                                if price_m else "See link")

    book_a = main.select_one('a[href*="ticketsolve"]')
    if book_a:
        book, link = "Book online", book_a["href"]
    elif is_run or re.search(r"drop.?in|no booking|self-guided", text, re.I):
        book, link = "Drop-in", url
    else:
        book, link = "Book online", url

    cat = ("Camp" if re.search(r"camp", title, re.I)
           else "Show" if re.search(r"performance|show|concert|theatre|"
                                    r"exhibition|installation|film",
                                    title + text[:300], re.I)
           else "Workshop")
    return {"title": title, "dates": dates, "time": time_str, "ages": ages,
            "cost": cost, "book": book, "link": link, "cat": cat}


def scrape():
    r = fetch(f"{BASE}/events")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    urls = sorted({(a["href"] if a["href"].startswith("http")
                    else BASE + a["href"])
                   for a in soup.select('a[href*="/events/view/"]')})
    rows = []
    for url in urls:
        d = parse_detail(url)
        if not d:
            continue
        for iso in d["dates"]:
            rows.append(event_row(
                iso=iso, time_str=d["time"], venue="The Ark",
                activity=d["title"], cat=d["cat"], ages=d["ages"],
                status="Available", book=d["book"], cost=d["cost"],
                link=d["link"], area="Dublin City", source="ark"))
    return rows

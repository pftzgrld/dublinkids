"""National Museum of Ireland — Archaeology (Kildare St) and Decorative
Arts & History (Collins Barracks).

Listing anchors carry '22nd Jul Drop-in Activity <title>'; detail pages carry
exact date, time and ages in the visible text. Family drop-ins are free with
no booking; 'WAIT LIST' events are flagged.
"""
import re
from bs4 import BeautifulSoup

from common import (fetch, event_row, parse_day_month, parse_time_range,
                    status_from_text, today, clean_summary)

BASE = "https://www.museum.ie"
BRANCHES = [
    ("/en-ie/museums/archaeology/events", "NMI Archaeology, Kildare St"),
    ("/en-ie/museums/decorative-arts-history/events",
     "NMI Collins Barracks"),
]
KID_RX = re.compile(r"drop-?in|family|families|child|kids|craft|workshop|"
                    r"explore|junior", re.I)


def scrape():
    rows = []
    seen = set()
    for path, venue in BRANCHES:
        r = fetch(BASE + path)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select('a[href*="/Events/"], a[href*="/events/"]'):
            href = a["href"]
            if not re.search(r"/Events/\d{4}/", href, re.I):
                continue
            url = href if href.startswith("http") else BASE + href
            label = a.get_text(" ", strip=True)
            if not label or url in seen:
                continue
            seen.add(url)
            if not KID_RX.search(label):
                continue
            iso = parse_day_month(label)
            dr = fetch(url)
            text = ""
            if dr:
                dmain = BeautifulSoup(dr.text, "html.parser")
                body = dmain.select_one("main") or dmain.body
                text = body.get_text(" ", strip=True)
                iso = parse_day_month(text) or iso
            if not iso or iso < today().isoformat():
                continue
            title = re.sub(r"^\d{1,2}(st|nd|rd|th)?\s+\w+\s+", "", label)
            title = re.sub(r"^(Drop-?in Activity|Tour|Workshop|Talk)\s+", "",
                           title).strip() or label
            time_str = parse_time_range(text) or "See link"
            # Two-session family drop-ins run 11-1 and 2-4
            if re.search(r"11[:.]?00.{0,30}13[:.]?00.{0,80}14[:.]?00", text):
                time_str = "11:00–13:00 & 14:00–16:00"
            dropin = bool(re.search(r"drop-?in", label + " " + text[:600],
                                    re.I))
            wait = "WAIT LIST" in label.upper() or "WAIT LIST" in text.upper()
            status = ("Waitlisted" if wait else
                      "No booking needed" if dropin else
                      status_from_text(text))
            ages_m = re.search(r"ages?\s*:?\s*(\d+\s*[-–+]\s*\d*\+?|\d+\+)",
                               text, re.I)
            ages = ages_m.group(1).replace(" ", "") if ages_m else "Families"
            # description: strip the leading date/type/title label off body
            desc = re.split(r"(Booking|Suitable for|Please note|Meeting)",
                            text, maxsplit=1)[0]
            desc = desc[len(title):] if desc.startswith(title) else desc
            rows.append(event_row(
                iso=iso, time_str=time_str, venue=venue,
                activity=title, cat="Museum", ages=ages, status=status,
                book="Drop-in" if dropin else "Book online",
                cost="Free" if "free" in text.lower() else "See link",
                link=url, area="Dublin City", source="nmi",
                summary=clean_summary(desc)))
    return rows

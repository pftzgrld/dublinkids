"""Fingal County Council events (fingal.ie/events/browse).

The council's own events section — small (a handful of items) but it's
where the family festivals live (BlanchFest). Cards on /events/browse carry
date + title + link + teaser; only cards with an explicit family/kid signal
are kept (the concert series and seniors' choir sessions are not kid
events). Library events stay with the Fingal Eventbrite org in src_sdcc.
"""
import re
from bs4 import BeautifulSoup

from common import event_row, fetch, parse_day_month, today

BASE = "https://www.fingal.ie"
KID_RX = re.compile(r"famil|kids?\b|child|fun.?day|festival", re.I)
# 'audiences of all ages' on a concert series is not a kid event — needs an
# explicit family/kid signal, and concert/choir/seniors content is out
ADULT_RX = re.compile(r"choir|seniors?|older people|virtual|concert", re.I)
TOWN_RX = re.compile(r"\b(Blanchardstown|Swords|Malahide|Howth|Balbriggan|"
                     r"Skerries|Donabate|Portmarnock|Castleknock|Rush|Lusk|"
                     r"Baldoyle|Santry)\b")


def scrape():
    r = fetch(f"{BASE}/events/browse")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for card in soup.select("article.card"):
        a = card.select_one('a[href^="/events/"]')
        title_el = card.select_one("h3, .field--name-title")
        date_el = card.select_one("time") or \
            card.find(class_=lambda c: c and "date" in c)
        if not (a and title_el and date_el):
            continue
        title = title_el.get_text(" ", strip=True)
        teaser = card.get_text(" ", strip=True)
        if ADULT_RX.search(title) or not KID_RX.search(teaser):
            continue
        iso = parse_day_month(date_el.get_text(" ", strip=True))
        if not iso or iso < today().isoformat():
            continue
        town = TOWN_RX.search(teaser)
        free = bool(re.search(r"\bfree\b", teaser, re.I))
        rows.append(event_row(
            iso=iso, time_str=None, venue=town.group(1) if town else "Fingal",
            activity=title, cat="Park", ages="All ages",
            status="No booking needed", book="Drop-in",
            cost="Free" if free else "See link", link=BASE + a["href"],
            area="Fingal", source="fingalevents"))
    return rows

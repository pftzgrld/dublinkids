"""DCC libraries 'Children's Summer Programme' blog post.

A hand-curated per-branch list that carries dated events MISSING from the
events listing src_dcc scrapes (verified 22 Jul: Cabra's manga workshop,
'Screen Print Your Style'). Structure: h2 = branch, li = 'Title, Weekday
D Month at time'. Lines without a parseable date ('Creative Hubs Events',
'Throughout July and August') are skipped. Duplicates of listing events
('Greek Family Favourites') fall out in build.py's de-dup as long as
src_dcc runs first (its rows carry real booking links; keep it that way in
SOURCES order). The post is seasonal — when it 404s after summer, the
failure guard keeps nothing alive because past rows age out naturally.
"""
import re
from bs4 import BeautifulSoup

from common import (fetch, event_row, parse_day_month, parse_time_range,
                    today)

URL = "https://www.dublincity.ie/library/blog/childrens-summer-programme"


def scrape():
    r = fetch(URL)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup.body
    rows, venue = [], None
    for el in main.find_all(["h2", "li"]):
        txt = el.get_text(" ", strip=True)
        if el.name == "h2":
            venue = txt if "librar" in txt.lower() else None
            continue
        if not venue:
            continue
        m = re.match(r"(.{4,}?),\s*(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day"
                     r"\s+(\d{1,2}\s+\w+)\s+at\s+(.+)$", txt, re.I)
        if not m:
            continue
        iso = parse_day_month(m.group(2))
        time_str = parse_time_range(m.group(3))
        if not iso or iso < today().isoformat():
            continue
        rows.append(event_row(
            iso=iso, time_str=time_str, venue=venue,
            activity=m.group(1).strip(), cat="Library", ages="Children",
            status="Available", book="Contact branch", cost="Free",
            link=URL, area="Dublin City", source="dccblog"))
    return rows

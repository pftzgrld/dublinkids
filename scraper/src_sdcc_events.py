"""SDCC council events (sdcc.ie/en/events/) — sitemap-driven.

The /en/events/ search page is JS-rendered and the per-branch listing pages
are inconsistent (some empty, some showing 2020 events), but the sitemap
lists every /en/events/*.html detail page with a lastmod. We fetch the
recently-touched pages and parse each detail. Two page shapes:
- structured: `.date-time-area` (`.date` dd/mm/yy + `.time`), `.tag-area`
  (SDCC area link), h1 title, `.content` description;
- prose: dates written in the body ('27th July - Frisbee & Cricket'),
  sometimes an Eventbrite booking link. Every distinct future date becomes
  a row (the sports camps run Mon/Wed/Fri).
Family fun days / cinema days count as kid events by nature; everything
else needs a kid signal. Civic noise (mattress amnesty, park yoga,
songwriter residencies, schedule pages) is excluded.
"""
import re
import datetime as dt
from bs4 import BeautifulSoup

from common import (fetch, event_row, parse_time_range, parse_day_month,
                    today, HORIZON_DAYS)

BASE = "https://www.sdcc.ie"
LASTMOD_DAYS = 120          # only parse pages touched in the last ~4 months

KID_RX = re.compile(
    r"child|kids?\b|famil|toddler|baby|teen|junior|camp\b|fun.?day|"
    r"cinema day|storytime|story time|lego|ages?\s*\d|\d+\s*[-–]\s*\d+\s*ye",
    re.I)
NOISE_RX = re.compile(
    r"amnesty|yoga|park.?fit|songwriter|residen|lunchtime|market|"
    r"schedule|heating|council chamber|comhairle|cemetery|choir|"
    r"for adults|adults? only|over 18|18\+", re.I)

VENUE_RX = re.compile(
    r"\b(County Library|Castletymon Library|Clondalkin Library|"
    r"North Clondalkin Library|Lucan Library|Palmerstown Library|"
    r"Whitechurch Library|Ballyroan Library|Corkagh Park|Tymon Park|"
    r"Sean Walsh Park|Dodder Valley Park|Jobstown Park|Rathfarnham Castle|"
    r"Rua Red|Civic Theatre|Collinstown Sports Complex|"
    r"[A-Z][a-z]+ Community Centre)\b")


def event_pages():
    """(url, lastmod) for every fresh /en/events/*.html page in the sitemap."""
    r = fetch(f"{BASE}/sitemap.xml", timeout=60)
    if not r:
        return []
    cutoff = (today() - dt.timedelta(days=LASTMOD_DAYS)).isoformat()
    out = []
    for m in re.finditer(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>",
                         r.text):
        url, lm = m.group(1).strip(), m.group(2).strip()[:10]
        if re.search(r"/en/events/.*\.html$", url) and lm >= cutoff:
            out.append((url, lm))
    return out


def parse_detail(url):
    r = fetch(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    h1 = soup.select_one("h1")
    if not h1:
        return []
    title = h1.get_text(" ", strip=True)
    content = soup.select_one(".content")
    main = soup.select_one("main") or soup.body
    text = (content or main).get_text(" | ", strip=True)
    blurb = title + " | " + text[:1500]
    if NOISE_RX.search(blurb) or not KID_RX.search(blurb):
        return []

    dates, time_str = [], None
    dta = soup.select_one(".date-time-area")
    if dta:
        dm = re.search(r"(\d{2})/(\d{2})/(\d{2})",
                       dta.get_text(" ", strip=True))
        if dm:
            dates = [f"20{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"]
        tspan = dta.select_one(".time")
        if tspan:
            t = parse_time_range(tspan.get_text(strip=True))
            if t:                       # '14:00 - 00:00' end means unknown
                time_str = t.split("–")[0] if t.endswith("00:00") else t
    if not dates:                       # prose page: every distinct date
        seen = set()
        for m in re.finditer(r"\d{1,2}(?:st|nd|rd|th)?\s+"
                             r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|"
                             r"Nov|Dec)[a-z]*(?:\s+\d{4})?", text):
            iso = parse_day_month(m.group(0))
            if iso and iso not in seen:
                seen.add(iso)
                dates.append(iso)
        time_str = parse_time_range(text, require_ampm=True)
    eb_a = soup.select_one('a[href*="eventbrite"]')
    if not dates and eb_a:              # dates only on the Eventbrite page
        from src_sdcc import jsonld_events
        er = fetch(eb_a["href"].split("?")[0])
        for ev in jsonld_events(er.text) if er else []:
            start = ev.get("startDate", "")
            if len(start) >= 10 and start[:10] not in dates:
                dates.append(start[:10])
                if len(start) >= 16 and not time_str:
                    time_str = start[11:16]

    horizon = (today() + dt.timedelta(days=HORIZON_DAYS)).isoformat()
    dates = [d for d in sorted(dates)
             if today().isoformat() <= d <= horizon]
    if not dates:
        return []

    vm = VENUE_RX.search(title + " | " + text)
    area_a = soup.select_one(".tag-area a")
    venue = vm.group(1) if vm else \
        (f"{area_a.get_text(strip=True)} area" if area_a else "South Dublin")

    if eb_a:
        book, link, status = "Book online", eb_a["href"].split("?")[0], \
            "Available"
    elif re.search(r"\bbook|register", text, re.I):
        book, link, status = "Contact branch", url, "Available"
    else:
        book, link, status = "Drop-in", url, "No booking needed"

    if re.search(r"camp\b", title, re.I):
        cat = "Camp"
    elif re.search(r"cinema|movie|performance|concert", blurb, re.I):
        cat = "Show"
    elif "librar" in (venue + title).lower():
        cat = "Library"
    else:
        cat = "Park"
    cost = "Free" if not re.search(r"€\s*\d", text) else "See link"
    ages_m = re.search(r"ages?\s*:?\s*(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\+)",
                       blurb, re.I)
    ages = ages_m.group(1).replace(" ", "") if ages_m else "All ages"

    return [event_row(iso=d, time_str=time_str, venue=venue, activity=title,
                      cat=cat, ages=ages, status=status, book=book, cost=cost,
                      link=link, area="South Dublin", source="sdccevents")
            for d in dates]


def scrape():
    rows = []
    for url, _ in event_pages():
        rows.extend(parse_detail(url))
    return rows

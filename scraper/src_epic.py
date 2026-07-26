"""EPIC The Irish Emigration Museum (epicchq.com/whats-on).

Server-rendered WordPress; event pages live at /event/<slug>/. Detail pages
carry labelled 'Date:' / 'Time:' / 'Cost:' fields plus (for series) an
'Event Schedule' day list. No Event JSON-LD. The programme is mixed —
evening author talks and Dublin by Dusk lates are adult — so events need a
kid/family/storytelling signal to be kept. In-gallery sessions are usually
'included in general admission' rather than free: cost shows 'With admission'
so the free filter stays honest. The Kids Go Free date-range offer is an
admission deal, not an event — excluded by the offer/deal guard.
"""
import datetime as dt
import re
import html as H

from common import (fetch, event_row, parse_time_range, parse_day_month,
                    today, HORIZON_DAYS, MONTHS)

BASE = "https://epicchq.com"

KID_RX = re.compile(
    r"\bkids?\b|child|famil(y|ies)|all ages|storytell|puppet|treasure hunt|"
    r"\blego\b|craft (month|workshop)|demonstration", re.I)
ADULT_RX = re.compile(
    r"by dusk|late opening|18\+|adults? only|wine|whiskey|in conversation|"
    r"book (club|launch)|lecture", re.I)
OFFER_RX = re.compile(r"go free|discount|offer|sale\b|voucher", re.I)

MON_RX = "|".join(MONTHS)


def extract_dates(text):
    """Dates within the horizon from EPIC's phrasing: a 'D Month – D Month
    [YYYY]' range expands day-by-day; otherwise every explicit 'D Month'
    mention (schedule lists) becomes a date."""
    lo, hi = today(), today() + dt.timedelta(days=HORIZON_DAYS)
    found = set()

    def add(iso):
        if iso and lo.isoformat() <= iso <= hi.isoformat():
            found.add(iso)

    t = re.sub(r"\s+", " ", text)
    rng = re.search(
        rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MON_RX})\s*[–-]\s*"
        rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MON_RX})(?:\s+(\d{{4}}))?",
        t, re.I)
    if rng:
        mons = [x.lower() for x in MONTHS]
        m1 = mons.index(rng.group(2).lower()) + 1
        m2 = mons.index(rng.group(4).lower()) + 1
        year = int(rng.group(5)) if rng.group(5) else today().year
        try:
            a = dt.date(year, m1, int(rng.group(1)))
            b = dt.date(year, m2, int(rng.group(3)))
        except ValueError:
            a = b = None
        if a and b and a <= b:
            d = max(a, lo)
            while d <= min(b, hi):
                found.add(d.isoformat())
                d += dt.timedelta(days=1)
            return sorted(found)
    for m in re.finditer(rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MON_RX})"
                         rf"(?:\s+\d{{4}})?", t, re.I):
        add(parse_day_month(m.group(0)))
    return sorted(found)


def field(text, label):
    m = re.search(rf"{label}:\s*\|\s*([^|]+)", text)
    return m.group(1).strip() if m else ""


def scrape():
    r = fetch(f"{BASE}/whats-on/")
    if not r:
        return []
    urls = sorted(set(re.findall(rf'href="({BASE}/event/[^"]+)"', r.text)))
    rows = []
    for url in urls:
        er = fetch(url)
        if not er:
            continue
        body = re.sub(r"<script.*?</script>|<style.*?</style>", "", er.text,
                      flags=re.S)
        main = re.search(r"<main[^>]*>(.*?)</main>", body, re.S)
        text = re.sub(r"(\| *)+", "| ", re.sub(
            r"\s+", " ", re.sub(r"<[^>]+>", " | ",
                                H.unescape(main.group(1) if main else body))))
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", er.text, re.S)
        title = re.sub(r"\s+", " ", re.sub(
            r"<[^>]+>", "", H.unescape(title_m.group(1)))).strip() \
            if title_m else url.rstrip("/").split("/")[-1].replace("-", " ")
        title = title.replace(" | ", " — ")

        blurb = title + " " + text[:1500]
        if ADULT_RX.search(blurb) or OFFER_RX.search(title):
            continue
        if not KID_RX.search(blurb):
            continue

        date_f = field(text, "Date")
        sched = re.search(r"Event Schedule\s*\|(.{0,400})", text)
        dates = extract_dates(date_f + " " +
                              (sched.group(1) if sched else ""))
        if not dates:
            continue

        time_f = field(text, "Time")
        time_str = parse_time_range(time_f) if time_f else None

        cost_f = field(text, "Cost")
        if re.search(r"included|general admission", cost_f + text[:1200],
                     re.I):
            cost = "With admission"
        elif re.search(r"\bfree\b", cost_f, re.I) or \
                re.search(r"free to (enter|visit)|free entry", text, re.I):
            cost = "Free"
        else:
            eur = re.search(r"€\s?\d+(?:\.\d{2})?", cost_f)
            cost = eur.group(0).replace(" ", "") if eur else "See link"

        for iso in dates:
            rows.append(event_row(
                iso=iso, time_str=time_str, venue="EPIC (CHQ)",
                activity=title, cat="Museum", ages="All ages",
                status="Available", book="Book online", cost=cost,
                link=url, area="Dublin City", source="epic"))
    return rows


if __name__ == "__main__":
    for row in scrape():
        print(row["iso"], row["venue"], "|", row["activity"][:55], "|",
              row["time"], "|", row["cost"], "|", row["link"][:70])

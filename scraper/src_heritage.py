"""OPW heritage sites (heritageireland.ie/whats-on) — Dublin + Wicklow.

One feed covers every OPW venue: Pearse Museum, Rathfarnham Castle, the
Botanic Gardens (whose own site 403s bots — this is the reliable route to
their events), Custom House, Royal Hospital Kilmainham, Kilmainham Gaol,
Glendalough, and — when they reopen — Casino Marino, Dublin Castle and
Farmleigh. The listing is fully server-rendered (all ~117 events in the DOM,
no pagination). Cards carry title/site/dates/cost; the kid decision needs the
detail page: a `?tag=family-fun` Event Tag is the strong signal, otherwise an
explicit kid/family word in title+description. Ticketed events link
Eventbrite from the detail page; email-booked ones only show a mailto, so the
row links the detail page itself.
"""
import datetime as dt
import re
import html as H

from common import (fetch, event_row, parse_time_range, today, HORIZON_DAYS,
                    MONTHS)

LISTING = "https://heritageireland.ie/whats-on/"

# OPW site name (as shown in the card's <em>) -> display venue, area
SITES = [
    (re.compile(r"Kilmainham Gaol", re.I), "Kilmainham Gaol", "Dublin City"),
    (re.compile(r"Rathfarnham Castle", re.I), "Rathfarnham Castle",
     "South Dublin"),
    (re.compile(r"Pearse Museum", re.I), "Pearse Museum, Rathfarnham",
     "South Dublin"),
    (re.compile(r"Botanic Garden", re.I), "Botanic Gardens", "Dublin City"),
    (re.compile(r"Custom House", re.I), "Custom House", "Dublin City"),
    (re.compile(r"Royal Hospital Kilmainham", re.I),
     "Royal Hospital Kilmainham", "Dublin City"),
    (re.compile(r"Glendalough", re.I), "Glendalough Visitor Centre",
     "North Wicklow"),
    (re.compile(r"Casino,? Marino", re.I), "Casino Marino", "Dublin City"),
    (re.compile(r"Phoenix Park|Ashtown", re.I), "Phoenix Park Visitor Centre",
     "Dublin City"),
    (re.compile(r"Farmleigh", re.I), "Farmleigh", "Dublin City"),
    (re.compile(r"Dublin Castle", re.I), "Dublin Castle", "Dublin City"),
    (re.compile(r"St\.? Audoen", re.I), "St Audoen's Church", "Dublin City"),
]

# 'family' only counts in an event-framing phrase — historical prose is full
# of "the Hudson family"; 'child' is vetoed outright by NOT_KIDS_RX below
KID_RX = re.compile(
    r"\bkids?\b|child|family[ -]friendly|for (all the |the whole )?famil|"
    r"famil(y|ies) (fun|day|event|tour|workshop|welcome)|all the family|"
    r"\blego\b|big dig|safari|trail|teddy|puppet|storytim|treasure hunt|"
    r"junior|young people|teen\b|beekeeper|bumblebee|ages?\s*\d", re.I)
NOT_KIDS_RX = re.compile(
    r"not (suitable|recommended) for (young )?child|adults? only|18\+", re.I)
ADULT_RX = re.compile(
    r"lecture|choir|quartet|recital|yoga|lacemakers|photograph(y|ic) "
    r"exhibition|cemetery|famine|workhouse|dark side|by dusk|"
    r"launch|reception", re.I)

MON_RX = "|".join(MONTHS)


def _year_for(mon):
    t = today()
    return t.year + 1 if mon < t.month - 1 else t.year


def extract_dates(text):
    """All iso dates an event runs on, within the horizon.

    Handles: 'DD/MM/YYYY - DD/MM/YYYY' ranges (expanded day-by-day inside the
    horizon — long exhibition runs behave like the recurring drop-ins),
    single 'DD/MM/YYYY', prose day-lists ('1st, 8th, 15th and 29th July'),
    and single 'Monday 17th August' mentions."""
    lo, hi = today(), today() + dt.timedelta(days=HORIZON_DAYS)
    found = set()

    def add(d):
        if lo <= d <= hi:
            found.add(d.isoformat())

    slashed = [dt.date(int(y), int(m), int(d))
               for d, m, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})", text)
               if 1 <= int(m) <= 12 and 1 <= int(d) <= 31]
    if len(slashed) >= 2:
        a, b = min(slashed), max(slashed)
        d = max(a, lo)
        while d <= min(b, hi):
            add(d)
            d += dt.timedelta(days=1)
        return sorted(found)
    if len(slashed) == 1:
        add(slashed[0])
        return sorted(found)

    # prose: every 'D(st) ... Month' day-list, e.g. '1st, 8th and 15th July'
    for m in re.finditer(rf"((?:\d{{1,2}})(?:st|nd|rd|th)?"
                         rf"(?:\s*,\s*\d{{1,2}}(?:st|nd|rd|th)?)*"
                         rf"(?:\s*and\s+\d{{1,2}}(?:st|nd|rd|th)?)?)\s+"
                         rf"(?:of\s+)?({MON_RX})", text, re.I):
        mon = [x.lower() for x in MONTHS].index(m.group(2).lower()) + 1
        for day in re.findall(r"\d{1,2}", m.group(1)):
            try:
                add(dt.date(_year_for(mon), mon, int(day)))
            except ValueError:
                pass
    return sorted(found)


def parse_cards(html_text):
    for c in re.findall(r'<li id="infobox\d+">(.*?)</li>', html_text, re.S):
        href = re.search(r'href="(https://heritageireland\.ie/whats-on/'
                         r'[^"]+)"', c)
        title = re.search(r"<h3>(.*?)</h3>", c)
        site = re.search(r"<em>(.*?)</em>", c)
        if not (href and title and site):
            continue
        datep = re.search(r"</em></p><p>(.*?)</p>", c, re.S)
        cost = re.search(r"<span>(.*?)</span>", c)
        yield {"url": href.group(1),
               "title": H.unescape(title.group(1)).strip(" ."),
               "site": H.unescape(site.group(1)),
               "dates_text": H.unescape(datep.group(1)) if datep else "",
               "card_cost": (cost.group(1) if cost else "").strip()}


def scrape():
    r = fetch(LISTING)
    if not r:
        return []
    rows = []
    for card in parse_cards(r.text):
        match = next(((venue, area) for rx, venue, area in SITES
                      if rx.search(card["site"])), None)
        if not match:
            continue
        venue, area = match
        dr = fetch(card["url"])
        if not dr:
            continue
        detail = dr.text
        main = re.search(r"<main[^>]*>(.*?)</main>", detail, re.S)
        body = re.sub(r"<script.*?</script>", "",
                      main.group(1) if main else detail, flags=re.S)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", H.unescape(body)))
        tags = re.findall(r"\?tag=([a-z0-9-]+)", detail)

        blurb = card["title"] + " " + text[:1200]
        if NOT_KIDS_RX.search(blurb) or ADULT_RX.search(blurb):
            continue
        if "family-fun" not in tags and not KID_RX.search(blurb):
            continue

        dates_src = card["dates_text"] or ""
        m = re.search(r"Dates\s*(.{0,300}?)\s*Location", text)
        if not extract_dates(dates_src) and m:
            dates_src = m.group(1)
        dates = extract_dates(dates_src)
        if not dates:
            continue

        time_str = parse_time_range(dates_src, require_ampm=True)

        price_m = re.search(r"Price\s*(.{0,200}?)\s*Dates", text)
        price_text = price_m.group(1) if price_m else ""
        eur = re.search(r"€\s?\d+(?:\.\d{2})?", price_text)
        if card["card_cost"].lower() == "free" or \
                (not eur and re.search(r"\bfree\b", price_text, re.I)):
            cost = "Free"
        elif eur:
            cost = eur.group(0).replace(" ", "")
        else:
            cost = "See link"

        ages_m = re.search(r"ages?\s*(\d{1,2}\s*(?:[-–]\s*\d{1,2}|\+|"
                           r"and (?:up|over|older)))", blurb, re.I)
        ages = (re.sub(r"\s*and (?:up|over|older)", "+",
                       ages_m.group(1)).replace(" ", "")
                if ages_m else "Families")

        eb = re.search(r'href="(https://www\.eventbrite\.[a-z.]+/e/[^"]+)"',
                       detail)
        if eb:
            book, link = "Book online", eb.group(1).split("?")[0]
        elif re.search(r"drop.?in|no booking|booking not required|"
                       r"just turn up|just stop by", text, re.I):
            book, link = "Drop-in", card["url"]
        else:
            book, link = "Book online", card["url"]

        cat = ("Workshop" if re.search(r"workshop|lego|dig|craft|safari",
                                       blurb, re.I) else "Museum")
        for iso in dates:
            rows.append(event_row(
                iso=iso, time_str=time_str, venue=venue,
                activity=card["title"], cat=cat, ages=ages,
                status="Available", book=book, cost=cost, link=link,
                area=area, source="heritage"))
    return rows


if __name__ == "__main__":
    for row in scrape():
        print(row["iso"], row["venue"], "|", row["activity"][:55], "|",
              row["time"], row["cost"], row["ages"], row["link"][:60])

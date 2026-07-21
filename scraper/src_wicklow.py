"""North Wicklow — Bray, Ballywaltrim, Greystones, Enniskerry (+ the Whale).

Wicklow Libraries publish events through their Spydus catalogue. The events
home is a JS shell, but the ENQ search URLs are fully server-rendered over a
plain session: one date-sorted page of 300 records reaches well past the
build horizon, each recurring session already expanded to its own dated
record. Cards carry date/time, a 'Wicklow <Branch>' location line, and
free/registration flags.

The Whale Theatre (Greystones) is Ticketsolve behind Cloudflare — rendered
with Playwright when available (CI always; locally if installed), skipped
gracefully otherwise.
"""
import re
import urllib.parse

from bs4 import BeautifulSoup

from common import (_session, event_row, parse_day_month, parse_time_range,
                    status_from_text, today, HORIZON_DAYS, MONTHS,
                    clean_summary)
import datetime as dt

BASE = "https://wicklow.spydus.ie"
EVENTS_HOME = (f"{BASE}/cgi-bin/spydus.exe/MSGTRN/WPAC/EVENTS"
               f"?HOMEPRMS=EVSESPARAMS")
BRANCHES = {
    "Wicklow Bray": "Bray Library",
    "Wicklow Ballywaltrim": "Ballywaltrim Library, Bray",
    "Wicklow Greystones": "Greystones Library",
    "Wicklow Enniskerry": "Enniskerry Library",
}
AREA = "North Wicklow"
KID_RX = re.compile(
    r"child|kids?\b|famil|toddler|tummy time|baby|babies|storytime|"
    r"story\s*time|teen|junior|lego|sensory|age[sd]?\s*\d|"
    r"\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:year|yr)|years?\s*old|school", re.I)
ADULT_RX = re.compile(r"(?<!young )\badults?\b|knitters|writers group|"
                      r"book club|18\+|family history|genealog|crochet",
                      re.I)


def scrape_spydus():
    _session.get(EVENTS_HOME, timeout=30)
    qry = 'EVSCFLG:0 + EVSEDTE:">= TODAY"'
    url = (f"{BASE}/cgi-bin/spydus.exe/ENQ/WPAC/EVSESENQ"
           f"?QRY={urllib.parse.quote(qry)}&QRYTEXT=All%20events&NRECS=300")
    r = _session.get(url, timeout=60)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    horizon = (today() + dt.timedelta(days=HORIZON_DAYS)).isoformat()
    rows = []
    for card in soup.select("fieldset.card.card-list"):
        # the event's IRN (internal record number) is the one stable id — the
        # session number in the FULL url changes every visit, but QRY=IRN(id)
        # resolves to this exact event in any fresh session. Grab it before
        # stripping the card's buttons.
        irn = None
        full = card.select_one('a[href*="/FULL/WPAC/EVSESENQ/"]')
        if full:
            m = re.search(r"/EVSESENQ/\d+/(\d+)", full["href"])
            irn = m.group(1) if m else None
        event_link = (f"{BASE}/cgi-bin/spydus.exe/ENQ/WPAC/EVSESENQ"
                      f"?QRY=IRN({irn})") if irn else EVENTS_HOME
        for el in card.select(".sr-only, .btn, .btn-group, .form-check"):
            el.decompose()
        blocks = [d.get_text(" ", strip=True) for d in card.select(".d-block")]
        loc = next((b for b in blocks if b in BRANCHES), None)
        if not loc:
            continue
        text = card.get_text(" | ", strip=True)
        title = text.split(" | ")[0].strip()
        if ADULT_RX.search(title) or not KID_RX.search(text):
            continue
        when = next((b for b in blocks if re.match(r"\d{1,2} \w{3} \d{4}", b)),
                    "")
        iso = parse_day_month(when)
        if not iso or iso < today().isoformat() or iso > horizon:
            continue
        time_str = parse_time_range(when, require_ampm=True)
        free = bool(card.select_one(".event-free"))
        dropin = bool(card.select_one(".event-noregistration"))
        status = ("No booking needed" if dropin
                  else status_from_text(text))
        # description follows the 'Event' type marker in the card body
        desc = text.split("| Event |", 1)[-1] if "| Event |" in text else ""
        desc = re.split(r"\| (Registration|Free|Cost|Booking)\b", desc)[0]
        desc = desc.replace("|", " ")
        rows.append(event_row(
            iso=iso, time_str=time_str, venue=BRANCHES[loc],
            activity=title, cat="Library", ages="Children",
            status=status, book="Drop-in" if dropin else "Contact branch",
            cost="Free" if free else "See link",
            link=event_link, area=AREA, source="wicklow",
            summary=clean_summary(desc)))
    return rows


WHALE_KID_RX = re.compile(r"famil|kids?\b|child|panto|puppet|baby|toddler|"
                          r"junior|young", re.I)


def _whale_dates(text):
    """'Friday 24th July 2026' or '10:30am, Sat 11th, 18th & 25th July' ->
    iso dates."""
    mon = next((m for m in MONTHS if m.lower() in text.lower()), None)
    if not mon:
        return []
    days = re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)\b", text)
    out = []
    for d in days:
        iso = parse_day_month(f"{d} {mon[:3]}")
        if iso:
            out.append(iso)
    return out


def scrape_whale():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    rows = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page()
            page.goto("https://whaletheatre.ticketsolve.com/ticketbooth/"
                      "shows", timeout=60000)
            page.wait_for_timeout(6000)
            shows = page.eval_on_selector_all(
                "a[href*='/shows/']",
                "els => els.map(e => [e.innerText, e.href])")
            b.close()
    except Exception:
        return []
    seen = set()
    for text, href in shows:
        if not text or href in seen:
            continue
        seen.add(href)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0]
        if not WHALE_KID_RX.search(text):
            continue
        when = next((ln for ln in lines if re.search(r"\d", ln)), "")
        for iso in _whale_dates(when):
            if iso < today().isoformat():
                continue
            rows.append(event_row(
                iso=iso, time_str=parse_time_range(when, require_ampm=True),
                venue="Whale Theatre, Greystones", activity=title,
                cat="Show", ages="Families", status="Available",
                book="Book online", cost="See link", link=href,
                area=AREA, source="wicklow"))
    return rows


def scrape():
    return scrape_spydus() + scrape_whale()

"""IMMA — Irish Museum of Modern Art, summer family workshops.

imma.ie/whats-on/summer-at-imma-workshops/ (and the tours-and-activities
companion page) list the whole summer programme in an 'Upcoming Events'
block: each workshop is a heading carrying its dates + times, followed by
location / booking state / description. The programme is mostly adult art
workshops, so we keep only the ones whose title or description signals
family / kids / all-welcome. Needs a headless render (IMMA is JS + Cloudflare).
"""
import re

from bs4 import BeautifulSoup

from common import (event_row, parse_time_range, parse_day_month, today,
                    status_from_text, clean_summary, expand_rule, MONTHS)

PAGES = [
    "https://imma.ie/whats-on/summer-at-imma-workshops/",
    "https://imma.ie/whats-on/summer-at-imma-tours-and-activities/",
]
KID_RX = re.compile(
    r"\bfamil|\bkids?\b|\bchild|all welcome|all ages|young people|\bteen|"
    r"every age|with your family|for kids", re.I)
ADULT_ONLY_RX = re.compile(r"\b18\+|adults only|over 18s?\b", re.I)


def _dates_from_heading(head):
    """A heading like 'Gelli Plate for Kids Wed 5 Aug 2:30pm-3:30pm' or
    'Mornings at the Museum Wednesdays, 1 July – 19 Aug 11.30am' — return
    (title, [iso dates], time_str)."""
    # split title from the first date token
    m = re.search(r"\b(Mon|Tues?|Wed(nes)?|Thur?s?|Fri|Satur?|Sun)"
                  r"(day)?s?\b|\b\d{1,2}(st|nd|rd|th)?\s+"
                  r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
                  head)
    if not m:
        return head.strip(), [], None
    title = head[:m.start()].strip(" ,–-")
    tail = head[m.start():]
    time_str = parse_time_range(tail)
    if re.search(r"\b\w+days?\b", tail, re.I) and re.search(r"–|-|to", tail):
        dates = expand_rule(tail)
    else:
        dates = []
        for dm in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
                              r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|"
                              r"Nov|Dec)", tail):
            iso = parse_day_month(f"{dm.group(1)} {dm.group(2)}")
            if iso:
                dates.append(iso)
    return title, dates, time_str


def _render(url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            p = b.new_page()
            p.goto(url, timeout=60000, wait_until="domcontentloaded")
            p.wait_for_timeout(5000)
            html = p.inner_html("#pb-block-upcoming-events")
            b.close()
            return html
    except Exception:
        return None


def scrape():
    rows = []
    seen = set()
    for page in PAGES:
        html = _render(page)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for head in soup.find_all(re.compile("^h[2-5]$")):
            head_text = head.get_text(" ", strip=True)
            title, dates, time_str = _dates_from_heading(head_text)
            if not title or not dates:
                continue
            # gather the description/booking block that follows this heading
            ctx_parts, book_url = [], None
            for sib in head.find_all_next():
                if sib.name and re.match(r"^h[2-5]$", sib.name):
                    break
                if sib.name == "a" and sib.get("href") \
                        and "ticketsolve" in sib["href"] and not book_url:
                    book_url = sib["href"]
                if sib.name in ("p", "span", "div") \
                        and sib.get_text(strip=True):
                    ctx_parts.append(sib.get_text(" ", strip=True))
            ctx = " ".join(ctx_parts[:6])
            if ADULT_ONLY_RX.search(ctx) or not KID_RX.search(title + " " + ctx):
                continue
            key = title.lower()[:40]
            if key in seen:
                continue
            seen.add(key)
            dropin = bool(re.search(r"drop.?in|no booking", ctx, re.I))
            if book_url:
                book, link = "Book online", book_url
            elif dropin:
                book, link = "Drop-in", page
            else:
                book, link = "Book online", page
            for iso in dates:
                if iso < today().isoformat():
                    continue
                rows.append(event_row(
                    iso=iso, time_str=time_str, venue="IMMA",
                    activity=re.sub(r"^IMMA\s+", "", title),
                    cat="Workshop", ages="Families",
                    status="No booking needed" if dropin
                    else status_from_text(ctx),
                    book=book, cost="Free", link=link,
                    area="Dublin City", source="imma",
                    summary=clean_summary(ctx)))
    return rows

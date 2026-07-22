"""dlr Libraries (all branches) via the central Drupal events listing.

NOTE (21 Jul 2026): the category vocabulary changed — the old term ids in
SCRAPING.md (90 Family & Children, 120/116 Events for the Young) are gone,
and an unknown term id silently returns the UNFILTERED listing. The whole
listing is small (6 unique events per page), so we paginate it all, parse
every detail page, and keep child-relevant events by keyword. Detail pages
carry date, time, venue, cost and often the booking state inline
('Event Fully Booked').
"""
import re
from bs4 import BeautifulSoup

from common import (fetch, event_row, expand_rule, parse_day_month,
                    parse_time_range, status_from_text, today, clean_summary)

BASE = "https://libraries.dlrcoco.ie"
KID_RX = re.compile(
    r"child|kids?\b|famil|toddler|baby|babies|storytime|story\s*time|"
    r"sensory|teen|junior|lego|age[sd]?\s*\d|school\s*children|young\s*people",
    re.I)
ADULT_RX = re.compile(r"\badult|\b18\+|over\s*18", re.I)


def _collect(soup, seen):
    for a in soup.select('a[href*="/event-calendar/"]'):
        url = a["href"]
        if not url.startswith("http"):
            url = BASE + url
        if url.rstrip("/") != f"{BASE}/events-and-news/event-calendar" \
                and url not in seen:
            seen.append(url)


def _render_all():
    """The listing is a JS 'Load More' page whose AJAX pagination is
    session-bound (a plain fetch only sees the first ~14). Render it and
    click Load More to exhaustion to get the whole programme (~36)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    urls = set()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            p = b.new_page()
            p.goto(f"{BASE}/events-listing", timeout=60000,
                   wait_until="domcontentloaded")
            p.wait_for_timeout(3000)
            for _ in range(20):
                btn = p.query_selector("a:has-text('Load More'), "
                                       "button:has-text('Load More')")
                if not btn or not btn.is_visible():
                    break
                btn.click()
                p.wait_for_timeout(1500)
            for h in p.eval_on_selector_all(
                    'a[href*="/event-calendar/"]', "els=>els.map(e=>e.href)"):
                if h.rstrip("/").split("/")[-1] != "event-calendar":
                    urls.add(h)
            b.close()
    except Exception:
        return []
    return list(urls)


def listing_links():
    """Full listing via a rendered Load-More pass, unioned with the static
    event-calendar page as a fallback when Playwright isn't available."""
    seen = []
    for u in _render_all():
        if u not in seen:
            seen.append(u)
    for path in ("/events-and-news/event-calendar", "/events-listing"):
        r = fetch(BASE + path)
        if r:
            _collect(BeautifulSoup(r.text, "html.parser"), seen)
    return seen


def parse_detail(url):
    r = fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup.body
    text = main.get_text(" | ", strip=True)
    title = (soup.select_one("h1") or soup.title).get_text(" ", strip=True)

    if ADULT_RX.search(title):
        return None
    if not (KID_RX.search(title) or KID_RX.search(text)):
        return None

    vm = re.search(r"\b(dlr LexIcon|dlr Lexicon|Dundrum|Blackrock|Ballyogan|"
                   r"Shankill|Deansgrange|Dalkey|Cabinteely|Stillorgan|"
                   r"Sallynoggin|Glencullen)\b", text)
    venue = vm.group(1) if vm else "dlr library"
    if venue.lower() == "dlr lexicon":
        venue = "dlr LexIcon"
    elif "dlr" not in venue:
        venue += " Library"

    time_str = parse_time_range(text, require_ampm=True)

    dates = []
    head = text.split("Event Description")[0]
    if re.search(r"\bevery\b", head, re.I):
        dates = expand_rule(head)
    if not dates:
        iso = parse_day_month(head)
        if iso:
            dates = [iso]

    status = status_from_text(title + " | " + text)
    # dlr staff append the booked-out state to the title itself
    title = re.sub(r"\s*\*+\s*Event (is )?Fully Booked\s*\*+", "", title,
                   flags=re.I).strip()
    booked_online = main.select_one('a[href*="tickettailor"], '
                                    'a[href*="eventbrite"]')
    if booked_online:
        book, link = "Book online", booked_online["href"]
    elif re.search(r"booking (is )?(required|essential)|book (a place|now)|"
                   r"registration required", text, re.I) \
            or status != "Available":
        # a booked-out marker proves it was bookable, whatever the page says
        book, link = "Contact branch", url
    else:
        book, link = "Drop-in", url
        status = "No booking needed"

    cost = "Free" if re.search(r"Cost \| Free", text) else \
        ("Free" if re.search(r"\bfree\b", text, re.I) else "See link")
    ages_m = re.search(r"ages?\s*:?\s*(\d+\s*[-–]\s*\d+|\d+\+)", text, re.I)
    if ages_m:
        ages = ages_m.group(1).replace(" ", "")
    elif re.search(r"toddler|baby|babies", title + text[:400], re.I):
        ages = "Toddlers"
    elif re.search(r"sensory", title, re.I):
        ages = "Families"
    else:
        ages = "Children"
    desc = ""
    if "Event Description" in text:
        desc = text.split("Event Description", 1)[1]
        desc = re.split(r"\| (Share|Contact Details|Event Map|Cost)\b",
                        desc)[0].replace("|", " ")
    return {"title": title, "venue": venue, "dates": dates, "time": time_str,
            "book": book, "link": link, "ages": ages, "status": status,
            "cost": cost, "summary": clean_summary(desc)}


def scrape():
    rows = []
    for url in listing_links():
        d = parse_detail(url)
        if not d or not d["dates"]:
            continue
        for iso in d["dates"]:
            if iso < today().isoformat():
                continue
            rows.append(event_row(
                iso=iso, time_str=d["time"], venue=d["venue"],
                activity=d["title"], cat="Library", ages=d["ages"],
                status=d["status"], book=d["book"], cost=d["cost"],
                link=d["link"], area="DLR", source="dlr",
                summary=d.get("summary", "")))
    return rows

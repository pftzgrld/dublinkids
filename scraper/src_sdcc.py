"""Eventbrite library organisers — Ballyroan (SDCC) and Fingal County
Libraries.

Org pages list /e/<slug>-tickets-<id> links; each event page embeds JSON-LD
with clean startDate, venue (branch) name and offer availability. Ballyroan's
programme is mostly children's events (drop only explicit adult ones);
Fingal's is the whole county programme, so events must show a kid signal in
the name or description to be kept.
"""
import json
import re

from common import (fetch, event_row, parse_time_range, today,
                    clean_summary)

ORGS = [
    {"url": "https://www.eventbrite.ie/o/ballyroan-library-2184216231",
     "id": "2184216231", "area": "South Dublin", "venue": "Ballyroan Library",
     "require_kid_signal": False, "source": "sdcc"},
    {"url": "https://www.eventbrite.ie/o/fingal-county-libraries-19927793883",
     "id": "19927793883", "area": "Fingal", "venue": "Fingal library",
     "require_kid_signal": True, "source": "fingal"},
    # Hugh Lane is shut for refurbishment; its programme runs OFFSITE in 40+
    # locations and books through this org — JSON-LD location.name carries
    # the actual venue, so don't hardcode the gallery.
    {"url": "https://www.eventbrite.ie/o/hugh-lane-gallery-10755329962",
     "id": "10755329962", "area": "Dublin City", "venue": "Hugh Lane Gallery",
     "require_kid_signal": True, "source": "hughlane"},
]
EVENT_URL_RX = r'https://www\.eventbrite\.ie/e/[a-z0-9-]+-tickets-\d+'


def org_event_urls(org):
    """All future event URLs for an organiser: the static org page shows only
    the first batch, the rest come from the JSON 'showmore' endpoint."""
    urls = set()
    r = fetch(org["url"])
    if r:
        urls |= set(re.findall(EVENT_URL_RX, r.text))
    for page in range(1, 8):
        r = fetch(f"https://www.eventbrite.ie/org/{org['id']}/showmore/"
                  f"?page_size=50&type=future&page={page}")
        if not r:
            break
        try:
            data = r.json()["data"]
        except (ValueError, KeyError):
            break
        events = data.get("events") or []
        for e in events:
            m = re.match(EVENT_URL_RX, str(e.get("url", "")))
            if m:
                urls.add(m.group(0))
        if not data.get("has_next_page"):
            break
    return urls
KID_RX = re.compile(
    r"child|kids?\b|famil|toddler|baby|babies|storytime|story\s*time|teen|"
    r"junior|lego|age[sd]?\s*\d|young\s*people|school|"
    r"\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:year|yr)|years?\s*old", re.I)
ADULT_RX = re.compile(r"for adults|adults? only|adult event|18\+|over 18s?",
                      re.I)


def jsonld_events(html):
    out = []
    for m in re.finditer(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.S):
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        items = d if isinstance(d, list) else [d]
        for it in items:
            if isinstance(it, dict) and "Event" in str(it.get("@type", "")):
                out.append(it)
    return out


def availability(ev):
    offers = ev.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    avail = " ".join(str(o.get("availability", "")) for o in offers)
    if "SoldOut" in avail:
        return "Sold out"
    if "LimitedAvailability" in avail:
        return "Limited"
    return "Available"


def cost_from_offers(ev):
    offers = ev.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    prices = []
    for o in offers:
        try:
            prices.append(float(o.get("lowPrice", o.get("price", ""))))
        except (TypeError, ValueError):
            pass
    if ev.get("isAccessibleForFree") or (prices and max(prices) == 0):
        return "Free"
    if prices:
        p = min(x for x in prices if x > 0)
        return f"€{p:.2f}".rstrip("0").rstrip(".")
    return "See link"


def scrape():
    rows = []
    seen = set()
    for org in ORGS:
        for url in sorted(org_event_urls(org)):
            if url in seen:
                continue
            seen.add(url)
            er = fetch(url)
            if not er:
                continue
            for ev in jsonld_events(er.text):
                start = ev.get("startDate", "")
                if len(start) < 10:
                    continue
                iso = start[:10]
                if iso < today().isoformat():
                    continue
                name = ev.get("name", "").strip()
                blurb = name + " " + str(ev.get("description", ""))[:600]
                if ADULT_RX.search(blurb):
                    continue
                if org["require_kid_signal"] and not KID_RX.search(blurb):
                    continue
                t = start[11:16] if len(start) >= 16 else None
                end = ev.get("endDate", "")
                if t and len(end) >= 16 and end[:10] == iso:
                    t = f"{t}–{end[11:16]}"
                loc = ev.get("location") or {}
                venue = (loc.get("name") or org["venue"]).strip()
                if "ballyroan" in venue.lower():
                    venue = "Ballyroan Library"
                if org["source"] == "hughlane":
                    venue = re.sub(r"^(HLG|Hugh Lane Gallery)\s*[@at-]*\s*",
                                   "", venue).strip() or "Hugh Lane Gallery"
                ages_m = re.search(r"ages?\s*(\d+\s*[-–]\s*\d+|\d+\+)", name,
                                   re.I)
                if org["source"] == "hughlane":
                    cat = "Camp" if re.search(r"camp", name, re.I) \
                        else "Workshop"
                else:
                    cat = "Library"
                rows.append(event_row(
                    iso=iso, time_str=t or parse_time_range(name),
                    venue=venue, activity=name, cat=cat,
                    ages=ages_m.group(1).replace(" ", "") if ages_m
                    else "Children",
                    status=availability(ev), book="Book online",
                    cost=cost_from_offers(ev), link=url, area=org["area"],
                    source=org["source"],
                    summary=clean_summary(ev.get("description", ""))))
    return rows

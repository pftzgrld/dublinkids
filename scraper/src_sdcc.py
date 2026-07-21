"""South Dublin (SDCC) — Ballyroan Library's Eventbrite organiser page.

Org page lists /e/<slug>-tickets-<id> links; each event page embeds JSON-LD
with clean startDate and offer availability. New events appear weekly
(booking opens Monday 10am).
"""
import json
import re

from common import fetch, event_row, parse_time_range, today

ORG_URLS = ["https://www.eventbrite.ie/o/ballyroan-library-2184216231"]


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


def scrape():
    rows = []
    seen = set()
    for org in ORG_URLS:
        r = fetch(org)
        if not r:
            continue
        links = set(re.findall(
            r'https://www\.eventbrite\.ie/e/[a-z0-9-]+-tickets-\d+', r.text))
        for url in sorted(links):
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
                t = start[11:16] if len(start) >= 16 else None
                end = ev.get("endDate", "")
                if t and len(end) >= 16 and end[:10] == iso:
                    t = f"{t}–{end[11:16]}"
                name = ev.get("name", "").strip()
                if re.search(r"for adults|adults only|18\+", name, re.I):
                    continue
                loc = ev.get("location") or {}
                venue = (loc.get("name") or "Ballyroan Library").strip()
                if "ballyroan" in venue.lower():
                    venue = "Ballyroan Library"
                offers = ev.get("offers") or []
                if isinstance(offers, dict):
                    offers = [offers]
                prices = []
                for o in offers:
                    try:
                        prices.append(float(o.get("lowPrice",
                                                  o.get("price", ""))))
                    except (TypeError, ValueError):
                        pass
                if ev.get("isAccessibleForFree") or (prices
                                                     and max(prices) == 0):
                    cost = "Free"
                elif prices:
                    p = min(x for x in prices if x > 0)
                    cost = f"€{p:.2f}".rstrip("0").rstrip(".")
                else:
                    cost = "See link"
                rows.append(event_row(
                    iso=iso, time_str=t or parse_time_range(name),
                    venue=venue, activity=name, cat="Library",
                    ages="Children", status=availability(ev),
                    book="Book online", cost=cost,
                    link=url, area="South Dublin", source="sdcc"))
    return rows

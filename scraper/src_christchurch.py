"""Christ Church Cathedral (christchurchcathedral.ie).

The site runs The Events Calendar, whose REST API is open and clean:
/wp-json/tribe/events/v1/events?categories=<slug>. The calendar is ~2,300
rows of daily worship services — so only the workshop / programmes / visit
categories are queried (family drop-in craft workshops, Heritage Week tours,
bell-ringing experiences). Opening-hours and closure notices live in the
'visit' category too and are dropped by title. 'BOOKED OUT' prefixes on
titles carry the availability signal and become the status.
"""
import html as H
import re

from common import (fetch, event_row, status_from_text, today, HORIZON_DAYS,
                    clean_summary)
import datetime as dt

API = "https://christchurchcathedral.ie/wp-json/tribe/events/v1/events"
CATEGORIES = ["workshop", "programmes", "visit"]

NOT_EVENT_RX = re.compile(
    r"opening hours|closed for|bank holiday|easter monday|summer break",
    re.I)
ADULT_RX = re.compile(r"lecture|friends of|agm|18\+|adults? only|wine", re.I)


def scrape():
    seen = set()
    rows = []
    lo = today().isoformat()
    hi = (today() + dt.timedelta(days=HORIZON_DAYS)).isoformat()
    for cat_slug in CATEGORIES:
        r = fetch(f"{API}?per_page=50&start_date={lo}&end_date={hi}"
                  f"&categories={cat_slug}")
        if not r:
            continue
        try:
            events = r.json().get("events", [])
        except ValueError:
            continue
        for e in events:
            title = re.sub(r"\s+", " ", H.unescape(e.get("title", ""))).strip()
            if not title or NOT_EVENT_RX.search(title):
                continue
            desc = re.sub(r"<[^>]+>", " ", H.unescape(e.get("description",
                                                            "")))
            if ADULT_RX.search(title + " " + desc[:400]):
                continue
            start = e.get("start_date", "")  # 'YYYY-MM-DD HH:MM:SS'
            if len(start) < 16:
                continue
            iso = start[:10]
            if not (lo <= iso <= hi) or (iso, title.lower()) in seen:
                continue
            seen.add((iso, title.lower()))

            status = "Available"
            m = re.match(r"(?:BOOKED OUT|SOLD OUT)\s*[:—-]?\s*(.*)", title,
                         re.I)
            if m:
                status, title = "Fully booked", m.group(1).strip() or title
            else:
                status = status_from_text(desc[:400], "Available")

            t = start[11:16]
            end = e.get("end_date", "")
            if len(end) >= 16 and end[:10] == iso and end[11:16] != t:
                t = f"{t}–{end[11:16]}"

            cost_raw = (e.get("cost") or "").strip()
            if cost_raw.lower() == "free" or \
                    re.search(r"included (in|with) admission|free with|"
                              r"no extra (cost|charge)", desc, re.I):
                cost = "Free" if cost_raw.lower() == "free" \
                    else "With admission"
            elif "€" in cost_raw:
                cost = cost_raw
            else:
                cost = "With admission"

            ages_m = re.search(r"\b(?:aged?|ages)\s*(\d{1,2}\s*(?:\+|and "
                               r"(?:up|over|older)|[-–]\s*\d{1,2}))",
                               desc, re.I)
            ages = re.sub(r"\s*and (?:up|over|older)", "+",
                          ages_m.group(1)).replace(" ", "") if ages_m \
                else "Families"

            dropin = bool(re.search(r"drop.?in|no booking", title + desc,
                                    re.I))
            rows.append(event_row(
                iso=iso, time_str=t, venue="Christ Church Cathedral",
                activity=title,
                cat="Workshop" if cat_slug in ("workshop", "programmes")
                else "Museum",
                ages=ages, status=status,
                book="Drop-in" if dropin else "Book online",
                cost=cost, link=e.get("url") or
                "https://christchurchcathedral.ie/whats-on/",
                area="Dublin City", source="christchurch",
                summary=clean_summary(desc)))
    return rows


if __name__ == "__main__":
    for row in scrape():
        print(row["iso"], row["time"], "|", row["activity"][:55], "|",
              row["status"], row["cost"], row["ages"], row["book"])

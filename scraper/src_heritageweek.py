"""National Heritage Week (heritageweek.ie) — Dublin's four councils + north
Wicklow.

One national listing of ~2,600 events for the nine days of Heritage Week
(15–23 August in 2026). Server-rendered, 12 cards a page, paged at
`/event-listings/pN`; filters are plain GET arrays — `where[0]=dublin-city`,
`eventFeatures[0]=…` — so the crawl is one query per (county, feature) pair.

Two organiser-set feature tags do the first cut:
  * `specifically-an-event-for-children` — taken as-is, always a row;
  * `suitable-for-families` — far looser (144 Dublin events, most of them
    cemetery walks, recitals and archive talks), so it must also carry a kid
    word in an EVENT-FRAMING phrase. "Children under 16 must be accompanied"
    and "Children 4–16: €6" are boilerplate, not a children's event; only
    "children's tour", "for children", "family fun", storytime, treasure hunt
    and friends count.

Dates live in one `<h3>` as `D[, D][ - D] Month, 10am - 12pm`, one line per
run (multi-day events separate the lines with `<br>`), so a single event
becomes one row per date it actually runs. Booking is a "Booking Link" button
on the detail page when it exists; email/phone-only events link the
heritageweek page itself, which carries both.

Out of season the listing returns nothing for these filters and the source
returns [] — build.py then keeps the previous rows, which by then are all in
the past.
"""
import datetime as dt
import re
import html as H

from common import (fetch, event_row, parse_time_range, status_from_text,
                    today, HORIZON_DAYS, MONTHS)

BASE = "https://www.heritageweek.ie/event-listings"

# listing county slug -> dublinkids area label
COUNTIES = {"dublin-city": "Dublin City",
            "dublin-dunlaoghaire-rathdown": "DLR",
            "dublin-fingal": "Fingal",
            "dublin-south": "South Dublin",
            "wicklow": "North Wicklow"}
KIDS_TAG = "specifically-an-event-for-children"
FAMILY_TAG = "suitable-for-families"

# Co. Wicklow reaches Arklow; the site covers the north of it only. Eircode
# routing keys are the reliable cut (A98 Bray/Enniskerry/Glendalough,
# A63 Greystones/Delgany/Kilcoole, A67 Ashford/Wicklow town), with town names
# as the fallback when an organiser leaves the eircode out.
NORTH_WICKLOW_EIR = re.compile(r"\b(A98|A63|A67)\s?[A-Z0-9]{4}\b", re.I)
NORTH_WICKLOW_TOWN = re.compile(
    r"\bbray\b|greystones|delgany|enniskerry|kilmacanogue|kilcoole|"
    r"newtownmountkennedy|glendalough|laragh|roundwood|powerscourt|"
    r"ashford|rathnew|kilpedder|newcastle", re.I)

# Kid words that only count as an event framing — see the module note.
KID_RX = re.compile(
    r"\bkids?\b|children's\b|for children|children are (invited|welcome to)|"
    r"child(ren)?[ -]friendly|famil(y|ies)[ -]friendly|"
    r"famil(y|ies) (fun|day|event|tour|workshop|trail|drop|activit)|"
    r"for (all the |the whole )?famil|all the family|families welcome|"
    r"storytim|story time|teddy|puppet|\blego\b|big dig|treasure hunt|"
    r"safari|face paint|pond dip|mini ?beast|fossil hunt|bouncy|"
    r"\bteens?\b|teenager|aged? \d{1,2}\s*[-–+]|ages? \d{1,2}\b|"
    r"\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:year|yr)s?", re.I)
# hard vetoes — the organiser says the event isn't for children
VETO_RX = re.compile(
    r"not (suitable|recommended) for (young )?child|adults? only|18\+|"
    r"over 18s?\b", re.I)
# adult subject matter / format: enough to reject a merely family-tagged
# event, but never a children-tagged one (Peter and the Wolf is a recital)
ADULT_RX = re.compile(
    r"cemeter|graveyard|\bburial|execution|court-?martial|famine|workhouse|"
    r"genealog|lecture|symposium|\bagm\b|recital|commemorat|"
    r"challenging terrain", re.I)
# an organiser-tagged children's event that is a plain tour/talk/exhibition
# with nothing for children in its text is a mis-tag, not a children's event
PASSIVE_TYPES = {"tour", "talk", "exhibition", "an-opw-site"}
# stripped before the kid test — the standard "bring an adult" / price small
# print mentions children without being for them
BOILERPLATE_RX = re.compile(
    r"children (under \d{1,2}s?\s*)?(must|should|need to) be accompanied|"
    r"accompanied by an adult|children (aged )?\d{1,2}\s*(to|[-–])\s*\d{1,2}"
    r"\s*(years?)?\s*:?\s*€|children (go )?free|under \d{1,2}s? (go )?free",
    re.I)

MON_RX = "|".join(MONTHS)
# '17 August, 10:30am - 12pm' / '15 - 23 August, 10am - 5pm' /
# '1, 8 and 15 August, 2pm - 3pm'
DATE_LINE_RX = re.compile(
    rf"^(?P<days>\d{{1,2}}(?:\s*(?:,|-|–|and)\s*\d{{1,2}})*)\s+"
    rf"(?P<mon>{MON_RX})\b(?P<rest>.*)$", re.I)

# Venues that already reach the site through another source, under that
# source's name — aliased so build.py's (date, venue, title) de-dup can see
# the same event twice. Matched against the whole address block.
VENUE_ALIASES = [
    (re.compile(r"Dead Zoo|Collins Barracks", re.I), "NMI Collins Barracks"),
    (re.compile(r"National Museum.*Kildare|Kildare St", re.I),
     "NMI Archaeology, Kildare St"),
    (re.compile(r"Glendalough", re.I), "Glendalough Visitor Centre"),
]

PARK_RX = re.compile(
    r"\bpark\b|garden|\bwood|forest|beach|nature|trail|walk|bog|river|"
    r"hill\b|mountain|estate|farm|coast", re.I)


def _year_for(mon, day):
    """Heritage Week is an August fixture; a date months past means next year."""
    t = today()
    for year in (t.year, t.year + 1):
        try:
            d = dt.date(year, mon, day)
        except ValueError:
            return None
        if (t - d).days <= 90:
            return d
    return None


def parse_date_line(line):
    """'15 - 23 August, 10am - 5pm' -> (['2026-08-15', …], '10:00–17:00')."""
    m = DATE_LINE_RX.match(line.strip())
    if not m:
        return [], None
    mon = [x.lower() for x in MONTHS].index(m.group("mon").lower()) + 1
    nums = [int(n) for n in re.findall(r"\d{1,2}", m.group("days"))]
    if re.search(r"[-–]", m.group("days")) and len(nums) == 2:
        nums = list(range(nums[0], nums[1] + 1))
    lo, hi = today(), today() + dt.timedelta(days=HORIZON_DAYS)
    dates = []
    for n in nums:
        d = _year_for(mon, n)
        if d and lo <= d <= hi:
            dates.append(d.isoformat())
    return sorted(set(dates)), parse_time_range(m.group("rest"))


def _text(fragment):
    t = re.sub(r"\s+", " ",
               H.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()
    return t.replace("’", "'")   # curly apostrophes break the kid regex


def listing(county, feature):
    """{event id: detail url} for one (county, feature) filter pair."""
    out = {}
    for page in range(1, 40):
        url = BASE if page == 1 else f"{BASE}/p{page}"
        r = fetch(url, params=[("where[0]", county),
                               ("eventFeatures[0]", feature)])
        if not r:
            break
        cards = re.findall(r'<article class="item item-summary.*?</article>',
                           r.text, re.S)
        for c in cards:
            href = re.search(r'href="(https://www\.heritageweek\.ie/'
                             r'event-listings/[^"#]+)"', c)
            eid = re.search(r'data-id="(\d+)"', c)
            if href and eid:
                out[eid.group(1)] = href.group(1)
        total = re.search(r'listings-count">([\d,]+)', r.text)
        total = int(total.group(1).replace(",", "")) if total else 0
        if not cards or page * 12 >= total:
            break
    return out


def parse_detail(html_text):
    d = {}
    m = re.search(r'<h1 class="page-title[^"]*">(.*?)</h1>', html_text, re.S)
    d["title"] = _text(m.group(1)) if m else ""
    m = re.search(r"<h3>((?:[^<]|<br\s*/?>)*\d{1,2}\s+[A-Z][a-z]+"
                  r"(?:[^<]|<br\s*/?>)*)</h3>", html_text)
    d["date_lines"] = [_text(x) for x in
                       re.split(r"<br\s*/?>", m.group(1))] if m else []
    m = re.search(r'<ul class="list-unstyled event-details event-dates[^"]*">'
                  r'(.*?)</ul>', html_text, re.S)
    d["place"] = [_text(x) for x in re.findall(r"<li>(.*?)</li>", m.group(1),
                                               re.S)] if m else []
    m = re.search(r'<div class="content-block text-block">(.*?)</div>',
                  html_text, re.S)
    d["desc"] = _text(m.group(1)) if m else ""
    m = re.search(r'href="([^"]+)"[^>]*>Booking Link<', html_text)
    d["booking"] = m.group(1) if m else ""
    m = re.search(r"<h3>Event Type</h3>(.*?)</ul>", html_text, re.S)
    section = m.group(1) if m else ""
    d["types"] = re.findall(r"eventType\[\]=([a-z0-9-]+)", section)
    d["features"] = re.findall(r"eventFeatures\[\]=([a-z0-9-]+)", section)
    return d


def category(d, venue):
    types = set(d["types"])
    if re.search(r"\blibrar", venue, re.I):
        return "Library"
    if "workshop" in types or re.search(r"workshop|craft|make your own",
                                        d["title"], re.I):
        return "Workshop"
    if types & {"performance-or-reenactment", "festival"}:
        return "Show"
    if PARK_RX.search(f"{venue} {d['title']}") and "exhibition" not in types:
        return "Park"
    return "Museum"


def ages_for(blurb):
    m = re.search(r"(?:ages?d?|suitable for (?:children )?aged?)\s*"
                  r"(\d{1,2}\s*(?:[-–]\s*\d{1,2}|\+))", blurb, re.I)
    if not m:
        m = re.search(r"\((\d{1,2}\s*[-–]\s*\d{1,2})\s*(?:yrs?|years?)", blurb,
                      re.I)
    return m.group(1).replace(" ", "") if m else "Families"


def scrape():
    # one crawl per (county, feature); a kids-tagged event is kept outright,
    # a family-tagged one has to earn it in the kid test below
    urls, kid_tagged = {}, set()
    for county in COUNTIES:
        for feature in (KIDS_TAG, FAMILY_TAG):
            for eid, url in listing(county, feature).items():
                urls[eid] = (url, county)
                if feature == KIDS_TAG:
                    kid_tagged.add(eid)
    rows = []
    for eid, (url, county) in urls.items():
        r = fetch(url)
        if not r:
            continue
        d = parse_detail(r.text)
        if not d["place"] or not d["date_lines"]:
            continue
        blurb = f"{d['title']} {d['desc']}"
        if VETO_RX.search(blurb):
            continue
        if eid in kid_tagged:
            if not KID_RX.search(blurb) and \
                    set(d["types"]) <= PASSIVE_TYPES:
                continue
        else:
            if ADULT_RX.search(blurb) or d["types"] == ["talk"]:
                continue
            if not KID_RX.search(BOILERPLATE_RX.sub(" ", blurb)):
                continue

        where = " ".join(d["place"])
        area = COUNTIES[county]
        if area == "North Wicklow" and not (NORTH_WICKLOW_EIR.search(where)
                                            or NORTH_WICKLOW_TOWN.search(where)):
            continue

        venue = re.sub(r"\s*\(.*?\)\s*$", "", d["place"][0]).strip(" ,.")
        if venue.isupper() and " " in venue:   # organisers shout; cards don't
            venue = venue.title()               # (single words stay: IFI, OPW)
        venue = next((name for rx, name in VENUE_ALIASES if rx.search(where)),
                     venue)
        cost = "Free" if "free" in d["features"] else None
        if not cost:
            eur = re.search(r"€\s?\d+(?:\.\d{2})?", d["desc"])
            cost = eur.group(0).replace(" ", "") if eur else "See link"
        # organiser booking links go stale (ifi.ie/familyfest was a 404 on the
        # first run) — a dead link is worse than the listing page, which
        # carries the same booking route plus phone and email
        if d["booking"] and fetch(d["booking"], tries=1, timeout=15):
            book, link = "Book online", d["booking"]
        elif re.search(r"drop.?in|no booking|booking (is )?not (required|"
                       r"necessary)|just turn up|no need to book", d["desc"],
                       re.I):
            book, link = "Drop-in", url
        else:
            book, link = "Book online", url

        cat = category(d, venue)
        ages = ages_for(blurb)
        status = status_from_text(d["desc"])
        for line in d["date_lines"]:
            dates, time_str = parse_date_line(line)
            for iso in dates:
                rows.append(event_row(
                    iso=iso, time_str=time_str, venue=venue,
                    activity=d["title"], cat=cat, ages=ages, status=status,
                    book=book, cost=cost, link=link, area=area,
                    source="heritageweek"))
    return rows


if __name__ == "__main__":
    for row in scrape():
        print(row["iso"], row["area"][:12].ljust(12), row["venue"][:28].ljust(28),
              "|", row["activity"][:50], "|", row["time"], row["cost"],
              row["ages"], row["cat"])

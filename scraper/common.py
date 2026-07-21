"""Shared helpers: fetching, date handling, schema, recurrence expansion."""
import re
import time
import datetime as dt
from zoneinfo import ZoneInfo

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TZ = ZoneInfo("Europe/Dublin")

# How far ahead recurring rules are expanded.
HORIZON_DAYS = 45


def today():
    return dt.datetime.now(TZ).date()


_session = requests.Session()
_session.headers["User-Agent"] = UA


def fetch(url, *, tries=3, timeout=30, **kw):
    """GET with browser UA and simple retry. Returns Response or None."""
    for i in range(tries):
        try:
            r = _session.get(url, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404, 410):
                return None
        except requests.RequestException:
            pass
        time.sleep(1 + 2 * i)
    return None


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def parse_time_range(text, require_ampm=False):
    """Normalise a time expression to 'HH:MM' or 'HH:MM–HH:MM'. None if absent.

    Handles: '11am', '2.30pm', '10:00 - 14:00', '10.00am - 12.30pm',
    '11:00–13:00', '2pm & 3pm shows'. Bare numbers, phone numbers and
    coordinates never match: minutes need an explicit ':' or '.' separator,
    hours are validated, and require_ampm demands an am/pm marker (useful on
    noisy full-page text).
    """
    t = text.replace("–", "-").replace("—", "-")
    pat = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?|"
                     r"\b(\d{1,2})\s*(am|pm)\b", re.I)
    found = []  # (span, 'HH:MM')
    for m in pat.finditer(t):
        if m.group(1) is not None:
            h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        else:
            h, mi, ap = int(m.group(4)), 0, m.group(5)
        if require_ampm and not ap:
            continue
        if ap and ap.lower().startswith("p") and h < 12:
            h += 12
        if ap and ap.lower().startswith("a") and h == 12:
            h = 0
        if h > 23 or mi > 59:
            continue
        found.append((m.span(), f"{h:02d}:{mi:02d}"))
    if not found:
        return None
    if len(found) == 1:
        return found[0][1]
    (s1, t1), (s2, t2) = found[0], found[1]
    sep = t[s1[1]:s2[0]]
    if len(sep) < 12 and ("-" in sep or re.search(r"\bto\b|\buntil\b", sep,
                                                  re.I)):
        return f"{t1}–{t2}"
    if len(sep) < 12 and ("&" in sep or re.search(r"\band\b", sep, re.I)):
        return f"{t1} & {t2}"
    return t1


AGE_RULES = [
    ("under5", re.compile(r"\b(babies|baby|toddler|under\s*5|0\s*-\s*[2-5]|"
                          r"2\s*-\s*[2-5]|pre-?school|early\s*years)\b", re.I)),
    ("5to8", re.compile(r"\b(5|6|7|8)\s*(-|–|to)\s*(5|6|7|8|9|10|11|12)\b|"
                        r"\bage[sd]?\s*[5-8]\b", re.I)),
    ("9to12", re.compile(r"\b(9|10|11|12)\s*(-|–|to)\s*(10|11|12|13)\b|"
                         r"\b(8|9)\s*(-|–|to)\s*1[0-2]\b", re.I)),
    ("teen", re.compile(r"\b(teen|1[3-7]\s*(-|–|to)\s*1[3-9]|young\s*adult)\b",
                        re.I)),
]


def age_tags(ages_text):
    """Derive ageTags[] from a free-text age description."""
    if not ages_text:
        return ["any"]
    t = ages_text.lower()
    if any(w in t for w in ("all ages", "families", "family", "everyone",
                            "all welcome", "children")):
        tags = ["any"]
    else:
        tags = [tag for tag, rx in AGE_RULES if rx.search(ages_text)]
    return tags or ["any"]


_SUM_BOILERPLATE = re.compile(
    r"cookie|newsletter|mailing list|sign ?up|follow us|share this|"
    r"book (here|now|online|your|a place)|tickets?\b|©|all rights|"
    r"click here|read more|find out more|terms|privacy|please note", re.I)
_SUM_LEADIN = re.compile(
    r"^(location|meeting point|venue|cost|price|times?|dates?|when|where|"
    r"ages?|suitable for|free)\b[^.]*?[:–-]\s*", re.I)


def clean_summary(text, max_len=140):
    """First substantial, non-boilerplate sentence of a description, trimmed
    to one clean line. Returns '' when there's nothing worth showing —
    the UI hides empties, so a weak summary is better dropped than shown."""
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    for _ in range(3):  # peel stacked "Location: … Free, booking required." lead-ins
        stripped = _SUM_LEADIN.sub("", t)
        if stripped == t:
            break
        t = stripped.strip()
    for s in re.split(r"(?<=[.!?])\s+", t):
        s = s.strip()
        if len(s) < 25 or _SUM_BOILERPLATE.search(s):
            continue
        if len(s) > max_len:
            s = s[:max_len].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
        return s
    return ""


def event_row(*, iso, time_str, venue, activity, cat, ages, status, book,
              cost, link, area, source, summary=""):
    d = dt.date.fromisoformat(iso)
    ok = status.lower() not in ("full", "fully booked", "sold out",
                                "waitlisted", "wait list")
    return {
        "date": f"{d.day} {MONTHS[d.month - 1][:3]}",
        "iso": iso,
        "day": WEEKDAYS[d.weekday()][:3],
        "time": time_str or "See link",
        "venue": venue,
        "activity": activity,
        "cat": cat,
        "ages": ages or "All ages",
        "status": status,
        "book": book,
        "cost": cost or "Free",
        "link": link,
        "area": area,
        "summary": (summary or "").strip(),
        "ageTags": age_tags(ages),
        "free": (cost or "Free").strip().lower() == "free",
        "dropin": book == "Drop-in",
        "ok": ok,
        "src": source,
    }


def expand_rule(rule_text, *, start=None, end=None):
    """Expand a recurring-rule phrase into concrete dates within the horizon.

    Understands: 'Every Friday in July', 'Every Tuesday in July and August',
    'Every Monday', 'Tuesdays', 'Every Tuesday and Thursday'. Returns [] if
    no weekday pattern is found.
    """
    t = rule_text
    wds = [i for i, w in enumerate(WEEKDAYS)
           if re.search(rf"\b{w}s?\b", t, re.I)]
    if not wds:
        return []
    months = [i + 1 for i, m in enumerate(MONTHS)
              if re.search(rf"\b{m}\b", t, re.I)]
    t0 = today()
    lo = start or t0
    hi = end or (t0 + dt.timedelta(days=HORIZON_DAYS))
    out = []
    d = lo
    while d <= hi:
        if d >= t0 and d.weekday() in wds and (not months or d.month in months):
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def parse_day_month(text, default_year=None):
    """'22nd Jul' / '3 August 2026' / 'Saturday 25 July' -> iso date or None."""
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+"
                  r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                  r"(?:\s+(\d{4}))?", text, re.I)
    if not m:
        return None
    day = int(m.group(1))
    mon = [x[:3].lower() for x in MONTHS].index(m.group(2)[:3].lower()) + 1
    year = int(m.group(3)) if m.group(3) else (default_year or today().year)
    try:
        d = dt.date(year, mon, day)
    except ValueError:
        return None
    # A date months in the past with no explicit year is probably next year.
    if not m.group(3) and (today() - d).days > 90:
        d = dt.date(year + 1, mon, day)
    return d.isoformat()


STATUS_MARKERS = [
    ("Sold out", re.compile(r"sold\s*out", re.I)),
    ("Fully booked", re.compile(r"fully\s*booked|event\s*full\b", re.I)),
    ("Waitlisted", re.compile(r"wait\s*-?list", re.I)),
    ("Limited", re.compile(r"limited\s+(availability|places|spaces)|"
                           r"last\s+few|almost\s+(full|gone)", re.I)),
]


def status_from_text(text, default="Available"):
    for label, rx in STATUS_MARKERS:
        if rx.search(text):
            return label
    return default

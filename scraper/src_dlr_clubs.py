"""dlr Libraries regular clubs & groups (the prose-schedule pages).

The clubs-and-groups category pages list per-branch clubs with a schedule
written in prose. Many are concrete ('every Tuesday at 3.30pm', 'first
Saturday of the month 11am') — those become dated rows via weekly or
nth-weekday expansion. The rest ('one Saturday a month', 'alternating open
Saturdays', 'fortnightly', 'every other Tuesday') can't be resolved to dates
without inventing them, so they are dropped.

Page structure: each branch is a `.field-group-accordion-wrapper` whose first
div is the branch name and second div the content; clubs within a branch are
separated by <h5> titles (or a short bold paragraph when staff skipped the
heading). Blocks noting a break ('on a break until September', 'will start
from the 3 of September') only produce dates from the stated resume date.
'unless bank holiday weekend' drops dates in a weekend touching an Irish
bank holiday (the computable ones — Easter Monday isn't derived, but every
in-horizon one is a fixed or first/last-Monday rule).
"""
import re
import datetime as dt
from bs4 import BeautifulSoup

from common import (fetch, event_row, parse_time_range, today, HORIZON_DAYS,
                    WEEKDAYS, MONTHS)

BASE = "https://libraries.dlrcoco.ie"
# (path, default ages text, require a kid signal in the block)
PAGES = [
    ("/news-events/clubs-and-groups/junior-book-clubs", "Children", False),
    ("/news-events/clubs-and-groups/lego-builder-clubs", "Children", False),
    ("/news-events/clubs-and-groups/gaming-clubs", "Children", True),
    ("/news-events/clubs-and-groups/board-game-groups", "Children", True),
    ("/using-your-library/children-and-families/parent-and-toddler-groups",
     "0-4", False),
    ("/using-your-library/children-and-families/storytime", "Children",
     False),
]

KID_RX = re.compile(r"junior|child|kids?\b|famil|teen|young|lego|baby|babies|"
                    r"toddler|ages?d?\s*:?\s*\d|\d\s*\+", re.I)

# schedules that name a pattern but not a derivable date ('every second
# Wednesday' with no 'of the month' is fortnightly — nth rules are matched
# BEFORE this so 'every Second Saturday of the month' isn't caught)
VAGUE_RX = re.compile(
    r"one\s+\w+day\s+(?:of|a|per)\s+(?:the\s+)?month|alternat|every\s+other|"
    r"fortnight|generally|open\s+(?:mon|tues|wednes|thurs|fri|satur|sun)|"
    r"every\s+(?:open|second)\s+"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)days?", re.I)

_WD_ABBR = "|".join(w[:3] for w in WEEKDAYS)  # Mon|Tue|...
_ORD = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4, "last": -1}
NTH_RX = re.compile(
    rf"(?:every\s+)?({'|'.join(_ORD)})\s+({_WD_ABBR})\w*\s+of\s+"
    r"(?:the|every)\s+month", re.I)
WEEKLY_RX = re.compile(  # 'every Mon(day)', 'Fridays', 'each Tuesday'
    rf"(?:every|each|gach)\s+(?:{_WD_ABBR})|\b(?:{_WD_ABBR})[a-z]*days\b",
    re.I)
# Irish weekday names (parent-toddler page has 'Gach Déardaoin')
_IRISH = {"luain": "Monday", "máirt": "Tuesday", "céadaoin": "Wednesday",
          "déardaoin": "Thursday", "aoine": "Friday", "sathairn": "Saturday",
          "satharn": "Saturday", "domhnaigh": "Sunday", "domhnach": "Sunday"}
START_RX = re.compile(  # 'from 15th September', 'start from the 3 of September'
    rf"(?:from|starting|starts)\s+(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+"
    rf"(?:of\s+)?({'|'.join(m[:3] for m in MONTHS)})", re.I)
UNTIL_RX = re.compile(
    rf"(?:break\s+)?until\s+({'|'.join(MONTHS)})", re.I)
BOOKLINK_RX = re.compile(r"tickettailor|eventbrite|spydus", re.I)


def _bank_holidays(year):
    """Irish public holidays that fall Mon (plus fixed dates). Easter Monday
    is not derived — no in-horizon rule needs it."""
    def nth_mon(month, n):
        d = dt.date(year, month, 1)
        d += dt.timedelta(days=(0 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    def last_mon(month):
        d = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
        return d - dt.timedelta(days=d.weekday())
    return {dt.date(year, 1, 1), dt.date(year, 3, 17), dt.date(year, 12, 25),
            dt.date(year, 12, 26), nth_mon(2, 1), nth_mon(5, 1),
            nth_mon(6, 1), nth_mon(8, 1), last_mon(10)}


def _weekdays_in(text):
    return [i for i, w in enumerate(WEEKDAYS)
            if re.search(rf"\b{w[:3]}(?:{w[3:].lower()})?s?\b", text, re.I)]


def _horizon():
    t0 = today()
    return t0, t0 + dt.timedelta(days=HORIZON_DAYS)


def _expand_weekly(wds):
    lo, hi = _horizon()
    d, out = lo, []
    while d <= hi:
        if d.weekday() in wds:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def _expand_nth(n, wd):
    lo, hi = _horizon()
    out, d = [], lo.replace(day=1)
    while d <= hi:
        month = [d + dt.timedelta(days=i) for i in range(31)
                 if (d + dt.timedelta(days=i)).month == d.month
                 and (d + dt.timedelta(days=i)).weekday() == wd]
        pick = month[n - 1] if 0 < n <= len(month) else \
            (month[-1] if n == -1 else None)
        if pick and lo <= pick <= hi:
            out.append(pick)
        d = (d + dt.timedelta(days=32)).replace(day=1)
    return out


def _club_time(text, block_fallback=""):
    """parse_time_range plus one fix: '2:30-4pm' style ranges where only the
    end carries pm — an early-morning start to an afternoon end is really
    pm-pm."""
    t = parse_time_range(text) or parse_time_range(block_fallback,
                                                   require_ampm=True)
    m = re.match(r"(\d{2}):(\d{2})–(\d{2}):(\d{2})$", t or "")
    if m and int(m.group(1)) < 8 and int(m.group(3)) >= 12:
        t = f"{int(m.group(1)) + 12}:{m.group(2)}–{m.group(3)}:{m.group(4)}"
    return t


def _schedule(lines, block_text):
    """(dates, time_str) from a club block. Per-line first; if no line
    parses and nothing vague was stated, retry on the whole block (schedules
    sometimes wrap mid-phrase)."""
    def try_text(text):
        for irish, eng in _IRISH.items():
            text = re.sub(irish, eng, text, flags=re.I)
        m = NTH_RX.search(text)
        if m:
            wd = _weekdays_in(m.group(2))
            return _expand_nth(_ORD[m.group(1).lower()], wd[0]) if wd else None
        if VAGUE_RX.search(text):
            return None
        if WEEKLY_RX.search(text):
            wds = _weekdays_in(text)
            return _expand_weekly(wds) if wds else None
        return None

    for line in lines:
        dates = try_text(line)
        if dates is not None:
            return dates, _club_time(line, block_text)
    flat = re.sub(r"[|\s]+", " ", block_text)  # schedules can wrap mid-phrase
    dates = try_text(flat)
    if dates is not None:
        return dates, _club_time(flat)
    return [], None


def _constrain(dates, text):
    """Apply 'from <date>' / 'until <Month>' break notes."""
    start = None
    m = START_RX.search(text)
    if m:
        mon = [x[:3].lower() for x in MONTHS].index(m.group(2)[:3].lower()) + 1
        y = today().year + (1 if mon < today().month - 3 else 0)
        try:
            start = dt.date(y, mon, int(m.group(1)))
        except ValueError:
            start = None
    if start is None:
        m = UNTIL_RX.search(text)
        if m:
            mon = MONTHS.index(m.group(1).capitalize()) + 1
            y = today().year + (1 if mon < today().month - 3 else 0)
            start = dt.date(y, mon, 1)
    if start is None and re.search(r"break for the summer|on a break", text,
                                   re.I):
        return []          # a break with no stated resume date: don't guess
    if start:
        dates = [d for d in dates if d >= start]
    if re.search(r"bank holiday", text, re.I):
        bhs = _bank_holidays(today().year) | _bank_holidays(today().year + 1)
        dates = [d for d in dates
                 if not any(0 <= (b - d).days <= 2 or d == b for b in bhs)]
    return dates


_MONTH_UNIT = r"(?:mths?|months?|mí)"        # 'mí' — the Irish-language groups


def _ages(text, default):
    m = re.search(rf"(\d{{1,2}})\s*{_MONTH_UNIT}\s*[-–]\s*(\d{{1,2}})\s*y",
                  text, re.I)
    if m:                                    # '18 mths-3 yrs'
        return f"{int(m.group(1)) // 12}-{m.group(2)}"
    m = re.search(rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s*{_MONTH_UNIT}", text,
                  re.I)
    if m:                                    # '0-18 months', '0-18 mí'
        return f"{int(m.group(1)) // 12}-{max(1, int(m.group(2)) // 12)}"
    # plain year ranges need an age context or unit — times ('2.30-4.30pm')
    # and phone numbers must never match
    m = re.search(r"(?:ages?d?|suitable for)[^.\d]{0,20}"
                  r"(\d{1,2})\s*[-–]\s*(\d{1,2})", text, re.I) or \
        re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(?:years?|yrs?)\b", text,
                  re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"(?:ages?d?|requirement|for)\s*:?\s*(\d{1,2})\s*\+", text,
                  re.I)
    if m:
        return m.group(1) + "+"
    return default


def _venue(branch):
    b = re.sub(r"\s*Library\s*$", "", branch.strip())
    if b.lower() in ("lexicon", "dlr lexicon"):
        return "dlr LexIcon"
    return b + " Library"


NOTE_RX = re.compile(  # bold paragraphs that are notes, not club titles
    r"book|email|phone|contact|welcome|drop.?in|suitable|free|require|"
    r"meets?|meeting|every|ages?|month|bank holiday|"
    rf"{_WD_ABBR}|\d{{1,2}}[:.]\d{{2}}|please", re.I)


def _split_clubs(content):
    """Split a branch's content div into (title, [text lines]) club blocks.
    A block starts at an <h5>, or at a short link-free all-bold paragraph
    that doesn't read as a booking/schedule note."""
    blocks, cur_title, cur = [], None, []

    def flush():
        if cur_title or cur:
            lines = [ln for el in cur
                     for ln in el.get_text("\n", strip=True).split("\n") if ln]
            blocks.append((cur_title, lines))

    for el in content.find_all(recursive=False):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        is_h5 = el.name == "h5"
        is_bold_title = (el.name == "p" and len(txt) < 60 and not el.find("a")
                         and el.find("strong")
                         and el.find("strong").get_text(" ", strip=True) == txt
                         and not NOTE_RX.search(txt))
        if is_h5 or is_bold_title:
            flush()
            cur_title, cur = txt, []
        else:
            cur.append(el)
    flush()
    return blocks


def parse_page(html, url, default_ages, need_kid):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for wrap in soup.select(".field-group-accordion-wrapper"):
        divs = wrap.find_all("div", recursive=False)
        if len(divs) < 2:
            continue
        branch = divs[0].get_text(" ", strip=True)
        for title, lines in _split_clubs(divs[1]):
            if not lines:
                continue
            block = " | ".join(lines)
            if not title:
                title, block = lines[0], " | ".join(lines[1:]) or lines[0]
                lines = lines[1:]
            title = title.strip(" ,;:")
            if len(title) > 70 or (need_kid
                                   and not KID_RX.search(title + " " + block)):
                continue
            dates, time_str = _schedule(lines, block)
            dates = _constrain(dates, title + " | " + block)
            if not dates:
                continue
            booked = next((a["href"] for el in [wrap]
                           for a in el.find_all("a", href=True)
                           if BOOKLINK_RX.search(a["href"])), None)
            if booked:
                book, link, status = "Book online", booked, "Available"
            elif re.search(r"no booking|drop.?in", block, re.I):
                book, link, status = "Drop-in", url, "No booking needed"
            else:
                book, link, status = "Contact branch", url, "Available"
            if re.search(r"currently full|waiting list", block, re.I):
                status = "Waitlisted"
            ages = _ages(block, default_ages)
            for d in dates:
                if d < today():
                    continue
                rows.append(event_row(
                    iso=d.isoformat(), time_str=time_str, venue=_venue(branch),
                    activity=title, cat="Library", ages=ages, status=status,
                    book=book, cost="Free", link=link, area="DLR",
                    source="dlrclubs"))
    return rows


def scrape():
    rows, seen = [], set()
    for path, default_ages, need_kid in PAGES:
        url = BASE + path
        r = fetch(url)
        if not r:
            continue
        for row in parse_page(r.text, url, default_ages, need_kid):
            key = (row["iso"], row["venue"], row["activity"].lower())
            if key not in seen:       # D&D is listed on two category pages
                seen.add(key)
                rows.append(row)
    return rows

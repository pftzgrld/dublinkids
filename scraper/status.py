"""Booking-status polling for events whose source isn't rescraped each run
(the manual seed venues). Scraped sources read status at scrape time.

Generic pages: GET + text markers. Eventbrite: JSON-LD offers. Cloudflare/JS
holdouts (Ticket Tailor, FareHarbor, Hugh Lane) need a headless browser —
used when Playwright is installed (the CI runner), skipped locally.
"""
import re

from common import fetch, status_from_text

HEADLESS_RX = re.compile(r"tickettailor\.com|fareharbor\.com|hughlane\.ie",
                         re.I)
_pw_browser = None


def _headless_text(url):
    global _pw_browser
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        if _pw_browser is None:
            _pw = sync_playwright().start()
            _pw_browser = _pw.chromium.launch()
        page = _pw_browser.new_page()
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        text = page.inner_text("body")
        page.close()
        return text
    except Exception:
        return None


def poll(rows):
    """Update `status`/`ok` in place for bookable rows. Returns (#polled,
    #changed). Unreachable sources keep their previous status."""
    cache = {}
    polled = changed = 0
    for row in rows:
        if row.get("dropin") or not row.get("link", "").startswith("http"):
            continue
        url = row["link"]
        if url not in cache:
            if HEADLESS_RX.search(url):
                text = _headless_text(url)
            else:
                r = fetch(url)
                text = r.text if r else None
            cache[url] = text
        text = cache[url]
        if text is None:
            continue
        polled += 1
        # Eventbrite JSON-LD is the cleanest signal when present
        if "eventbrite" in url and "SoldOut" in text:
            new = "Sold out"
        else:
            new = status_from_text(text, default="Available")
        if new != row["status"]:
            row["status"] = new
            row["ok"] = new.lower() not in ("full", "fully booked",
                                            "sold out", "waitlisted")
            changed += 1
    return polled, changed

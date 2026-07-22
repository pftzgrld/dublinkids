"""One-off discovery sweep: find buried kid/family content across the
council and museum sites via their sitemaps.

Blind-crawling is noisy; every host here publishes /sitemap.xml (Drupal
paginates it, WordPress uses sitemap_index.xml — both handled). We enumerate
every URL, keep the ones whose path matches kid-relevant keywords, and write
a candidate list grouped by host to DISCOVERY.md for hand review. Good
candidates get promoted to real sources; this script is not part of build.py.

Run: python3 scraper/discover.py
"""
import re
import sys
import datetime as dt
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).parent))
from common import fetch, today  # noqa: E402

HOSTS = [
    "https://www.dlrcoco.ie",          # main council — gallery learning etc.
    "https://libraries.dlrcoco.ie",
    "https://www.dublincity.ie",
    "https://www.fingal.ie",
    "https://www.sdcc.ie",
    "https://www.wicklow.ie",
    "https://www.museum.ie",
    "https://imma.ie",
    "https://ark.ie",
    "https://hughlane.ie",
    "https://www.nationalgallery.ie",
]

KID_RX = re.compile(
    r"child|kids?\b|famil|junior|teen|toddler|baby|babies|storytime|"
    r"story-time|lego|camps?\b|youth|young-people|school-holiday|"
    r"learning-programme|exhibition-learning|gallery-learning|"
    r"education-programme|creative-kids|early-years|parent-and-toddler|"
    r"summer-stars|half-term|midterm|mid-term", re.I)
# obvious non-event noise even when a keyword hits
NOISE_RX = re.compile(
    r"/news/|/minutes|/agenda|/consultation|/policy|/policies|/planning-|"
    r"childcare-committee|child-?protection|safeguard|/jobs?/|/careers|"
    r"/press-|family-hub|family-resource|families-first|"
    r"/ga/|/gle/", re.I)  # Irish-language mirrors duplicate the English pages

XMLNS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _parse_sitemap(xml_bytes, depth=0):
    """Yield (loc, lastmod) from a sitemap; recurse into sitemap indexes.
    Takes raw bytes — sdcc.ie serves a UTF-8 BOM that requests' charset
    guess turns into garbage if decoded to text first."""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return
    tag = root.tag.replace(XMLNS, "")
    if tag == "sitemapindex" and depth < 2:
        for sm in root.iter(f"{XMLNS}sitemap"):
            loc = sm.findtext(f"{XMLNS}loc", "").strip()
            r = loc and fetch(loc)
            if r:
                yield from _parse_sitemap(r.content, depth + 1)
    else:
        for u in root.iter(f"{XMLNS}url"):
            loc = u.findtext(f"{XMLNS}loc", "").strip()
            if loc:
                yield loc, (u.findtext(f"{XMLNS}lastmod") or "").strip()[:10]


def host_urls(base):
    """All (url, lastmod) a host's sitemap exposes. Drupal paginates
    /sitemap.xml with ?page=N and links the pages as a sitemapindex, so the
    index recursion covers it; WordPress needs the _index fallback."""
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        r = fetch(base + path)
        if r and (b"<urlset" in r.content[:2000]
                  or b"<sitemapindex" in r.content[:2000]):
            return list(_parse_sitemap(r.content))
    return []


def main():
    out = [f"# Discovery sweep — {today().isoformat()}",
           "",
           "Sitemap-enumerated pages matching kid/family keywords that the",
           "scrapers don't already cover. Hand-review: promote real venue",
           "calendars to sources, ignore the rest. Regenerate with",
           "`python3 scraper/discover.py`.", ""]
    known = re.compile(  # already-covered surfaces: don't re-list event pages
        r"/events?[/-]|/event-calendar|/whats-on|/events$|eventbrite", re.I)
    for base in HOSTS:
        urls = host_urls(base)
        hits = [(u, lm) for u, lm in urls
                if KID_RX.search(u) and not NOISE_RX.search(u)
                and not known.search(u)]
        hits.sort(key=lambda x: x[1], reverse=True)   # freshest first
        print(f"{base}: {len(urls)} urls, {len(hits)} candidates",
              file=sys.stderr)
        out.append(f"## {base} — {len(hits)} candidates "
                   f"(of {len(urls)} sitemap urls)")
        if not urls:
            out.append("- *no XML sitemap exposed — use the site's own "
                       "search or a `site:` web search instead*")
        out.extend(f"- {u}" + (f"  ({lm})" if lm else "")
                   for u, lm in hits)
        out.append("")
    dest = Path(__file__).resolve().parent.parent / "DISCOVERY.md"
    dest.write_text("\n".join(out) + "\n")
    print(f"-> {dest}", file=sys.stderr)


if __name__ == "__main__":
    main()

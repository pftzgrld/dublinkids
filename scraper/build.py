"""Build data/events.json from all sources.

Per-source failure guard: if a source errors or returns nothing while the
previous dataset had rows from it, the previous rows are kept — a broken
parser never empties the site. Venues without a scraper yet live in
data/manual-events.json and get their booking status re-polled each run.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import src_dcc, src_dlr, src_nmi, src_sdcc  # noqa: E402
import status  # noqa: E402
from common import today  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "events.json"
MANUAL = ROOT / "data" / "manual-events.json"
SEASON_START = "2026-06-01"

SOURCES = {"dcc": src_dcc, "dlr": src_dlr, "nmi": src_nmi, "sdcc": src_sdcc}


def main():
    previous = json.loads(DATA.read_text()) if DATA.exists() else []
    prev_by_src = {}
    for r in previous:
        prev_by_src.setdefault(r.get("src", "manual"), []).append(r)

    rows = []
    for name, mod in SOURCES.items():
        try:
            got = mod.scrape()
        except Exception as e:  # a broken parser must not empty the site
            print(f"[{name}] FAILED: {e!r}", file=sys.stderr)
            got = []
        if got:
            print(f"[{name}] {len(got)} events")
            rows.extend(got)
        elif prev_by_src.get(name):
            print(f"[{name}] returned 0 — keeping "
                  f"{len(prev_by_src[name])} previous rows", file=sys.stderr)
            rows.extend(prev_by_src[name])
        else:
            print(f"[{name}] 0 events")

    manual = json.loads(MANUAL.read_text()) if MANUAL.exists() else []
    for r in manual:
        r["src"] = "manual"
    future_manual = [r for r in manual if r["iso"] >= today().isoformat()]
    polled, changed = status.poll(future_manual)
    print(f"[manual] {len(manual)} events; status polled {polled} links, "
          f"{changed} changed")
    rows.extend(manual)

    # de-dup (a venue can surface via two sources) and drop pre-season rows
    seen, out = set(), []
    for r in rows:
        if r["iso"] < SEASON_START:
            continue
        key = (r["iso"], r["venue"].lower().strip(),
               r["activity"].lower().strip()[:60])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    out.sort(key=lambda r: (r["iso"], r["time"]))

    DATA.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    upcoming = sum(1 for r in out if r["iso"] >= today().isoformat())
    print(f"TOTAL {len(out)} events ({upcoming} upcoming) -> {DATA}")


if __name__ == "__main__":
    main()

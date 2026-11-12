"""Cheapest one-way economy cash fare (USD, 1 adult) from Google Flights, per route and date.

Opens a visible Chrome via Playwright (free, no login). Google Flights did not block this on Oct 4, 2026.
Run:  .tmp/venv/bin/python tools/cash_fare_scan.py --routes BKK-NRT,SGN-HND --dates 2026-12-09,2026-12-30
Output: .tmp/cash_fares.json + printed rows.
Lesson: PNH-NRT returned "$73" for every date (a page-reading error), so fares under $150 are flagged.
Lesson (Oct 7, 2026): Google read "KOS" as Kos, Greece ($743, 3 stops). Small or ambiguous airports: pass city
names instead (--routes "Sihanoukville-Siem Reap"), then check each "ORIGIN–DEST" code on the result page.
Results for a city can include other airports (Sihanoukville also returned KTI, Phnom Penh's Techo airport).
--rows: also list every flight on the page (times, airline, duration, ORIGIN–DEST, stops, price), to see which
days a route runs and at what times. Verify: "Siem Reap-Sihanoukville" 2026-11-28 listed Cambodia Airways
11:20 AM SAI–KOS Nonstop $124 on Oct 7, 2026. Short regional hops are often under $150, so "suspect" is only
a hint there; check the rows.
"""
import argparse, json, os, re, time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, ".tmp", "browser-profile-gf")


def flight_rows(text):
    """Each result card has an ORIGIN–DEST line; times/airline/duration sit just above it, stops and price below."""
    L = [x.strip() for x in text.split("\n")]
    rows = []
    for i, x in enumerate(L):
        if re.fullmatch(r"[A-Z]{3}–[A-Z]{3}", x) and i >= 5:
            stops = L[i + 1] if i + 1 < len(L) else ""
            via = L[i + 2] if stops != "Nonstop" and stops.endswith(("stop", "stops")) and i + 2 < len(L) else ""
            price = next((y for y in L[i + 1:i + 8] if y.startswith("$") or y == "Price unavailable"), "")
            rows.append({"departs": L[i - 5], "arrives": L[i - 3], "airline": L[i - 2], "duration": L[i - 1],
                         "airports": x, "stops": stops, "via": via, "price": price})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", default="BKK-NRT,CNX-NRT,DAD-NRT,SGN-NRT,TPE-NRT,PNH-NRT,SGN-HND,BKK-LAX")
    ap.add_argument("--dates", default="2026-12-02,2026-12-09,2026-12-16,2026-12-30")
    ap.add_argument("--rows", action="store_true", help="also list every flight shown on the page")
    a = ap.parse_args()
    out = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False,
                                                   viewport={"width": 1300, "height": 1000})
        pg = ctx.new_page()
        for route in a.routes.split(","):
            o, d = route.split("-")
            for day in a.dates.split(","):
                u = (f"https://www.google.com/travel/flights?q=Flights%20to%20{quote(d)}%20from%20{quote(o)}"
                     f"%20on%20{day}%20oneway&curr=USD&hl=en")
                row = {"route": route, "date": day, "usd": None}
                try:
                    pg.goto(u, timeout=60000)
                    t = ""
                    for _ in range(20):
                        time.sleep(1.5)
                        t = pg.inner_text("body")
                        if "Loading results" not in t and re.search(r"from \$[\d,]+", t):
                            break
                    m = re.search(r"Cheapest\s*\n?\s*from \$([\d,]+)", t) or re.search(r"from \$([\d,]+)", t)
                    if m:
                        row["usd"] = int(m.group(1).replace(",", ""))
                        row["suspect"] = row["usd"] < 150
                    if a.rows:
                        row["flights"] = flight_rows(t)
                except Exception as e:
                    row["err"] = str(e)[:60]
                out.append(row)
                print({k: v for k, v in row.items() if k != "flights"}, flush=True)
                for f in row.get("flights", []):
                    print("   ", " | ".join(f.values()), flush=True)
                time.sleep(2)
        ctx.close()
    json.dump(out, open(os.path.join(ROOT, ".tmp", "cash_fares.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

"""Scan AwardTool (awardtool.com) for live economy award prices, one-way, 1 adult.

Opens a visible Chrome via Playwright (free). Logged out, AwardTool shows real-time
United + Aeroplan prices for a 2-day window per search; signing in once (free, email code)
in the window this opens unlocks all programs, and the session persists in the profile dir.

Setup (once):  python3 -m venv .tmp/venv && .tmp/venv/bin/pip install playwright
Run:
  .tmp/venv/bin/python tools/award_scan.py --from BKK,SGN,TPE --to NRT --dates 2026-12-09,2026-12-30
  .tmp/venv/bin/python tools/award_scan.py --login        # open AwardTool so you can sign in once
Output: .tmp/award_scan.json (all rows) + a printed table of the cheapest Chase/Capital One-usable
award per origin/window/program, with cents-per-point if --cash is given (JSON {"BKK|2026-12-09": 541}).

Lessons (Oct 4, 2026):
- united.com award search returns 403 and aircanada.com returns Akamai "Access Denied" to this
  browser; Seats.aero and AwardFares hit Cloudflare blocks. Do not try to evade; AwardTool works.
- Never read innerText of every element: hangs the page. XPath to "Live seat map", walk up.
- A killed run leaves Chrome holding the profile lock: kill it before relaunching.
- AwardTool shows Delta/American/Alaska too. Neither card transfers there; they are dropped.
- These are AwardTool's numbers. Confirm a winner on the airline's own page before any transfer.
"""
import argparse, datetime as dt, json, os, re, sys, time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, ".tmp", "browser-profile")
OUT = os.path.join(ROOT, ".tmp", "award_scan.json")
CARD_BANKS = ("Chase Ultimate Rewards", "Capital One Miles Rewards")
BANK_WORDS = ("Chase", "Capital One", "Bilt", "American Exp", "Citi")

JS = """(o)=>{const out=[];const seen=new Set();
const xs=document.evaluate("//*[normalize-space(text())='Live seat map']",document,null,XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);
for(let j=0;j<xs.snapshotLength;j++){let n=xs.snapshotItem(j);
 for(let i=0;i<14&&n;i++){n=n.parentElement;const t=n?n.textContent:'';if(t.includes('Seats Left')&&t.includes(o))break}
 if(!n)continue;const t=n.innerText;if(seen.has(t))continue;seen.add(t);
 out.push({t,alts:[...n.querySelectorAll('img')].map(i=>i.alt)});}
return out;}"""


def url(o, d, ts):
    return ("https://www.awardtool.com/flight?flightWay=oneway&pax=1&children=0&cabins=Economy"
            f"&range=true&rangeV2=false&from={o}&to={d}&programs=&targetId="
            f"&oneWayRangeStartDate={ts}&oneWayRangeEndDate={ts + 86400}")


def miles(s):
    try:
        return float(s.replace("K", "").replace(",", "").strip()) * 1000
    except ValueError:
        return None  # logged-out pages mask some prices as "IIII K"


def scan(origins, dest, dates):
    rows = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False,
                                                   viewport={"width": 1400, "height": 1100})
        pg = ctx.new_page()
        pg.set_default_timeout(30000)
        for o in origins:
            for d in dates:
                ts = int(dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
                try:
                    pg.goto(url(o, dest, ts), timeout=60000)
                    last = -1
                    for i in range(25):  # wait until the result list stops growing
                        time.sleep(3)
                        n = len(pg.inner_text("body"))
                        if n == last and i > 5:
                            break
                        last = n
                    for _ in range(6):
                        pg.mouse.wheel(0, 3000)
                        time.sleep(0.7)
                    cards = pg.evaluate(JS, o)
                except Exception as e:
                    print(o, d, "ERR", str(e)[:80], flush=True)
                    continue
                for c in cards:
                    L = [x.strip() for x in c["t"].splitlines() if x.strip()]
                    if "Live seat map" not in L:
                        continue
                    k = L.index("Live seat map")
                    eco = L[k + 1:k + 4]
                    if len(eco) < 3 or "Seats" not in eco[0] or miles(eco[1]) is None:
                        continue
                    progs = [a.replace(" logo", "") for a in c["alts"]
                             if a.endswith(" logo") and not any(b in a for b in BANK_WORDS)]
                    banks = [a.replace(" logo", "") for a in c["alts"] if any(b in a for b in BANK_WORDS)]
                    rows.append({"from": o, "to": dest, "window": d, "program": progs[0] if progs else "?",
                                 "usable": any(b in banks for b in CARD_BANKS), "miles": miles(eco[1]),
                                 "tax": float(re.sub(r"[^\d.]", "", eco[2]) or 0),
                                 "depart": " ".join(L[0:2]), "duration": L[2] if len(L) > 2 else "",
                                 "banks": sorted(set(banks))})
                print(o, d, len(cards), "cards", flush=True)
                json.dump(rows, open(OUT, "w"), indent=1)
        ctx.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="origins", default="BKK,CNX,DAD,SGN,TPE,PNH")
    ap.add_argument("--to", default="NRT")
    ap.add_argument("--dates", default="2026-12-02,2026-12-09,2026-12-16,2026-12-30")
    ap.add_argument("--cash", help='JSON {"BKK|2026-12-09": 541} for cents-per-point')
    ap.add_argument("--login", action="store_true", help="open AwardTool for a one-time sign-in")
    a = ap.parse_args()
    os.makedirs(PROFILE, exist_ok=True)
    if a.login:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False)
            ctx.new_page().goto("https://www.awardtool.com/")
            input("Sign in in the Chrome window, then press Enter here... ")
            ctx.close()
        return
    rows = scan(a.origins.split(","), a.to, a.dates.split(","))
    cash = json.loads(a.cash) if a.cash else {}
    best = {}
    for r in rows:
        if not r["usable"]:
            continue
        key = (r["from"], r["window"], r["program"])
        if key not in best or r["miles"] < best[key]["miles"]:
            best[key] = r
    for key in sorted(best):
        r = best[key]
        c = cash.get(f"{r['from']}|{r['window']}")
        cpp = f"{(c - r['tax']) / r['miles'] * 100:.2f}c" if c else "-"
        print(f"{r['from']}->{r['to']} {r['window']} {r['program']:<28} {r['miles']:>9,.0f} + ${r['tax']:<7.2f}"
              f" {r['depart']:<18} {r['duration']:<28} {cpp}")


if __name__ == "__main__":
    sys.exit(main())

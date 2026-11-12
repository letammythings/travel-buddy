"""Find places on Google Maps and pull what matters for remote work: hours, drive time, WiFi talk, links (free: local Chrome, no key).

Run:  .tmp/venv/bin/python -I tools/maps_places.py --near "Independence Monument Phnom Penh" --max 12 \
          "coworking space Phnom Penh" "co-working Phnom Penh" > .tmp/places.json
--type  keep only places whose Maps card matches this regex (e.g. "cowork|co-work|office"); stops bars/laundries.
--near  where we stay (a Maps search or "lat,lng"); results are centered there and get drive minutes from it.
--max   how many places to open (after de-duplicating all queries), nearest first.
--km    skip places farther than this straight line from --near (default 6; ~15 min by car in a city).
Prints JSON, one item per place: name, rating, reviews, category, status (e.g. "Permanently closed"), address,
phone, website, maps_url, hours {Monday: "8 AM–10 PM", ...}, late (review lines about 24/7 or late access), weekday_close (earliest Mon–Fri closing, "24h" if
open 24 hours), drive_min (driving now, from --near), km (straight line), wifi (review lines/tags about WiFi).
Quirks: logged out, a Maps search lists only ~8 places ("limited view"), so pass 2–3 query wordings. Drive minutes
are Google's estimate for right now, so they change with traffic. Maps hours are often staff hours: members may
get 24/7 access (check "late" and the website). Verified Oct 28, 2026: Phnom Penh coworking near the city center
found 58 places within 6 km; Mekong Office Space 4.8 (50), closes 17:00, 10 min drive, review says "24/7 access".
"""
import argparse, json, math, re, sys, time
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("queries", nargs="+")
ap.add_argument("--near")
ap.add_argument("--max", type=int, default=12)
ap.add_argument("--type", help='keep only places whose Maps card matches this regex, e.g. "cowork|co-work|office"')
ap.add_argument("--km", type=float, default=6, help="skip places farther than this straight line from --near")
a = ap.parse_args()
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WIFI = re.compile(r"wi-?fi|internet|mbps|\bmạng\b|connection", re.I)
LATE = re.compile(r"24/7|24 ?h|24 hours|all night|late at night|open late|midnight", re.I)

def coords(url):
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url) or re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    return (float(m.group(1)), float(m.group(2))) if m else None

def km(p, q):
    r = math.radians; dlat, dlng = r(q[0] - p[0]), r(q[1] - p[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(r(p[0])) * math.cos(r(q[0])) * math.sin(dlng / 2) ** 2
    return round(12742 * math.asin(math.sqrt(h)), 1)

def close_min(h):  # "8 AM–10:30 PM" -> 1350; past-midnight closes count as > 1440
    if re.search(r"24 hours", h, re.I): return 9999
    t = re.findall(r"(\d{1,2})(?::(\d\d))?\s*([AP]M)", h)
    if not t: return None
    def m(x): return (int(x[0]) % 12 + (12 if x[2] == "PM" else 0)) * 60 + int(x[1] or 0)
    o, c = m(t[0]), m(t[-1])
    return c + 1440 if c <= o else c

def hhmm(v): return "24h" if v == 9999 else f"{v // 60 % 24}:{v % 60:02d}" + (" (after midnight)" if v > 1440 else "")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(".tmp/browser-profile-gf", channel="chrome", headless=False, viewport={"width": 1300, "height": 1000})
    pg = ctx.new_page()
    def open_maps(q):
        pg.goto("https://www.google.com/maps/search/" + q.replace(" ", "+") + "?hl=en", timeout=60000); time.sleep(5)
    home = None
    if a.near:
        home = tuple(map(float, a.near.split(","))) if re.fullmatch(r"\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+\s*", a.near) else None
        if not home:
            open_maps(a.near)
            if pg.locator('[role="feed"]').count():
                pg.locator('[role="feed"] a[href*="/maps/place/"]').first.click(); time.sleep(5)
            home = coords(pg.url)
        print(f"near: {a.near} -> {home}", file=sys.stderr)
    links = {}
    for q in a.queries:
        url = "https://www.google.com/maps/search/" + q.replace(" ", "+") + (f"/@{home[0]},{home[1]},14z" if home else "") + "?hl=en"
        pg.goto(url, timeout=60000); time.sleep(5)
        feed = pg.locator('[role="feed"]')
        for _ in range(6):
            if feed.count(): feed.first.evaluate("e => e.scrollBy(0, 4000)"); time.sleep(1.5)
        for el in pg.locator('[role="feed"] a[href*="/maps/place/"]').all():
            try: card = el.locator("xpath=..").inner_text(timeout=1000)  # name, rating, category, address
            except Exception: card = ""
            if not a.type or re.search(a.type, card, re.I):
                links.setdefault(el.get_attribute("href"), el.get_attribute("aria-label"))
        print(f"query '{q}': {len(links)} places so far", file=sys.stderr)
    if home:  # nearest first; place links carry their own coordinates
        dist = {h: km(home, coords(h)) if coords(h) else 99 for h in links}
        links = {h: links[h] for h in sorted(links, key=dist.get) if dist[h] <= a.km}
        print(f"{len(links)} places within {a.km} km", file=sys.stderr)
    seen = set()  # the same place can come back under two links
    links = {h: l for h, l in links.items() if not (l in seen or seen.add(l))}
    out = []
    for href, label in list(links.items())[:a.max]:
        d = {"name": label, "maps_url": href.split("?")[0]}
        try:
            pg.goto(href, timeout=60000); time.sleep(4)
            main = pg.locator('[role="main"]').last
            try: main.locator('[aria-label*="hours" i]').first.click(timeout=3000, force=True); time.sleep(1.5)
            except Exception: pass
            lines = [l.strip() for l in main.inner_text(timeout=8000).split("\n") if l.strip()]
            for i, l in enumerate(lines):
                if re.fullmatch(r"\d\.\d", l) and i + 1 < len(lines) and re.fullmatch(r"\([\d,]+\)", lines[i + 1]):
                    d["rating"], d["reviews"] = float(l), int(re.sub(r"\D", "", lines[i + 1]))
                    d["category"] = re.sub(r"[·\s]*[\ue000-\uf8ff].*$", "", lines[i + 2]).strip(" ·") if i + 2 < len(lines) else None; break
            d["status"] = next((l for l in lines if re.search(r"(Permanently|Temporarily) closed", l)), "")
            for k, sel in [("address", '[data-item-id="address"]'), ("phone", '[data-item-id^="phone:tel:"]')]:
                el = main.locator(sel)
                d[k] = re.sub(r"^\w+:\s*", "", el.first.get_attribute("aria-label") or "") if el.count() else None
            el = main.locator('a[data-item-id="authority"]')
            d["website"] = el.first.get_attribute("href") if el.count() else None
            hours = {}
            for i, l in enumerate(lines[:-1]):
                if l in DAYS and l not in hours: hours[l] = lines[i + 1]
            d["hours"] = hours
            wk = [close_min(hours[x]) for x in DAYS[:5] if x in hours]
            wk = [v for v in wk if v is not None] if wk else []
            d["weekday_close"] = hhmm(min(wk)) if wk else ("24h" if any("24 hours" in l for l in lines) else None)
            here = coords(pg.url)
            if home and here:
                d["km"] = km(home, here)
            try:
                pg.get_by_role("tab", name=re.compile("Reviews", re.I)).first.click(timeout=5000); time.sleep(3)
                for b in pg.get_by_role("radio").all():  # topic chips; one about WiFi loads matching reviews
                    if WIFI.search(b.inner_text(timeout=500) or ""):
                        b.click(force=True, timeout=2000); time.sleep(3); break
                for _ in range(4): pg.mouse.move(400, 600); pg.mouse.wheel(0, 3000); time.sleep(1)
                rev = pg.locator('[role="main"]').last.inner_text(timeout=8000).split("\n")
                d["wifi"] = list(dict.fromkeys(r.strip()[:220] for r in rev if WIFI.search(r)))[:6]
                d["late"] = list(dict.fromkeys(r.strip()[:220] for r in rev if LATE.search(r)))[:4]
            except Exception: d["wifi"], d["late"] = [], []
            if home and here:
                pg.goto(f"https://www.google.com/maps/dir/?api=1&origin={home[0]},{home[1]}&destination={here[0]},{here[1]}&travelmode=driving&hl=en", timeout=60000); time.sleep(5)
                m = re.search(r"(?:(\d+)\s*hr\s*)?(\d+)\s*min", pg.locator('[role="main"]').last.inner_text(timeout=8000))
                d["drive_min"] = int(m.group(1) or 0) * 60 + int(m.group(2)) if m else None
        except Exception as e:
            d["error"] = f"{type(e).__name__}: {e}"[:200]
        out.append(d)
        print(f"  {d.get('name')}: close {d.get('weekday_close')}, drive {d.get('drive_min')} min", file=sys.stderr)
    ctx.close()
print(json.dumps(out, ensure_ascii=False, indent=1))

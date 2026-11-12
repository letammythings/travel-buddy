"""FazWaz rental cards (Chiang Mai condos) via local Chrome. Free (Playwright, .tmp/venv). FazWaz blocks WebFetch (403).
Run:  .tmp/venv/bin/python tools/fazwaz_scan.py OUT.json suthep chang-phueak
Each card: {url, text, area}; text includes "Min. Rental Duration", "Available:", SqM, floor, features.
Prices show in VND when browsing from Vietnam (?currency=THB is ignored); convert at the XE THB/VND rate.
Known issue (Oct 23, 2026): page 1 gives 30 cards, later pages only 5-6 with the one-card-per-listing check,
so some listings are missed. Fix before trusting the count (e.g. wait longer / pick the card element by class).
"""
import sys, time, json, re
from playwright.sync_api import sync_playwright
JS = """() => { const out=[]; const seen=new Set();
 for (const a of document.querySelectorAll("a[href*='/property-rent/']")) {
   const h=a.href.split('?')[0]; if (seen.has(h)) continue;
   const cnt=x=>((x&&x.innerText)||'').split('Min. Rental Duration').length-1;
   let e=a; for (let i=0;i<14 && e && cnt(e)==0;i++) e=e.parentElement;
   if (!e || cnt(e)!=1) continue; seen.add(h); out.push({url:h, text:e.innerText}); }
 return out; }"""
areas = sys.argv[2:]; res = []
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(".tmp/browser-profile-gf", channel="chrome", headless=False, viewport={"width":1300,"height":1000})
    pg = ctx.new_page()
    for area in areas:
        for n in range(1, 20):
            u = f"https://www.fazwaz.com/condo-for-rent/thailand/chiang-mai/mueang-chiang-mai/{area}?currency=THB&page={n}"
            try:
                pg.goto(u, timeout=60000); time.sleep(4)
                for _ in range(3): pg.mouse.wheel(0, 4000); time.sleep(0.8)
                cards = pg.evaluate(JS)
            except Exception as e:
                print("ERR", u, e); cards = []
            print(area, n, len(cards), flush=True)
            if not cards: break
            for c in cards: c["area"] = area; res.append(c)
    ctx.close()
json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)

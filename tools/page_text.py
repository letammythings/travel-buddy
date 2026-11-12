"""Print the visible text of a web page that blocks WebFetch (HTTP 403/429), using local Chrome.

Free: same local Chrome + Playwright setup as tools/listing_text.py (no Firecrawl credits, no login).
Run:  .tmp/venv/bin/python -I tools/page_text.py URL [--wait 8] [--scrolls 6] > OUT.txt
Then grep OUT.txt. Verified Oct 15, 2026 on https://www.ihg.com/bangkok-thailand/pool-hotels
(ihg.com returns 403 to WebFetch; this printed "17 hotels in Bangkok" + names and addresses).
Quirks: wait for "domcontentloaded", not full load (ihg.com never finished loading and hung 2+ min).
"View more" style buttons on ihg.com time out when clicked; read other ihg.com city pages
(luxury-hotels, pool-hotels, pet-friendly-hotels) instead to fill gaps.
"""
import argparse
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("--wait", type=int, default=8, help="seconds to wait after load")
ap.add_argument("--scrolls", type=int, default=6)
a = ap.parse_args()

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=False)
    pg = b.new_page()
    pg.goto(a.url, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(a.wait * 1000)
    for _ in range(a.scrolls):
        pg.mouse.wheel(0, 3000)
        pg.wait_for_timeout(1000)
    print(pg.inner_text("body"))
    b.close()

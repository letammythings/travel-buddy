"""Google Maps place details + visible reviews, saved as text (free: local Chrome via Playwright, no API key, no login).

Run:  .tmp/venv/bin/python tools/maps_reviews.py OUT_DIR "Raffles Hotel Le Royal Phnom Penh" "Central Market Phnom Penh" ...
Each query opens the first Maps result and saves OUT_DIR/<query>.txt (rating, review count, address, phone, review
topic tags with counts, and the reviews Google shows). Then grep the files for words like pressure/clean/rush.
Lesson (Oct 15, 2026): logged out, Google shows a "limited view": rating, count, tags and only ~3 reviews per place;
sorting by Newest fails. To list places first, open https://www.google.com/maps/search/<query> and read the
[role="feed"] panel. Lesson (Oct 15): clicking the topic chips (noise, construction…) with force=True
(an overlay blocks normal clicks) loads ~10 reviews instead of 3. Verify: "Lomchang Spa Phnom Penh St 566" gave 4.8 (1,145) on Oct 15, 2026.
Oct 28: the overview now expands the weekly hours (click on [aria-label*="hours"]), so all 7 days land in the file
(verified on 5 HCMC coworking spaces).
"""
import sys, time, re, os
from playwright.sync_api import sync_playwright
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(".tmp/browser-profile-gf", channel="chrome", headless=False, viewport={"width":1300,"height":1000})
    pg = ctx.new_page()
    for q in sys.argv[2:]:
        txt = ""
        try:
            pg.goto("https://www.google.com/maps/search/" + q.replace(" ", "+") + "?hl=en", timeout=60000)
            time.sleep(5)
            if pg.locator('[role="feed"]').count():
                pg.locator('[role="feed"] a[href*="/maps/place/"]').first.click(); time.sleep(5)
            main = pg.locator('[role="main"]').last
            try:  # expand the weekly opening-hours table so all 7 days land in the overview text
                main.locator('[aria-label*="hours" i]').first.click(timeout=3000, force=True); time.sleep(1.5)
            except Exception: pass
            txt += "=== OVERVIEW ===\n" + main.inner_text(timeout=8000) + "\n"
            try:
                pg.get_by_role("tab", name=re.compile("Reviews", re.I)).first.click(timeout=5000); time.sleep(3)
                try:
                    pg.get_by_role("button", name=re.compile("^Sort", re.I)).first.click(timeout=3000); time.sleep(1)
                    pg.get_by_role("menuitemradio", name=re.compile("Newest", re.I)).first.click(timeout=3000); time.sleep(3)
                except Exception as e: txt += f"[sort failed {type(e).__name__}]\n"
                for _ in range(12):
                    pg.mouse.move(400, 600); pg.mouse.wheel(0, 4000); time.sleep(1.2)
                for b in pg.get_by_role("button", name=re.compile("^(More|See more)$")).all()[:60]:
                    try: b.click(timeout=500)
                    except Exception: pass
                txt += "=== REVIEWS ===\n" + pg.locator('[role="main"]').last.inner_text(timeout=8000)
            except Exception as e:
                txt += f"[no reviews tab: {type(e).__name__}]"
        except Exception as e:
            txt += f"[failed: {type(e).__name__} {e}]"
        fn = re.sub(r"\W+", "_", q)[:60] + ".txt"
        open(os.path.join(out, fn), "w").write(txt)
        print("saved", fn, len(txt))
    ctx.close()

"""Read listing cards (title, rating, total price, link) from Airbnb and Booking.com search pages.

Free: opens a visible Chrome via Playwright on this computer (no Firecrawl credits, no login).
Needs .tmp/venv with playwright (see tools/cash_fare_scan.py docstring for setup).
Run:  .tmp/venv/bin/python tools/stay_price_scan.py searches.json .tmp/stays.json
searches.json: [{"label": "PP 28 nights", "url": "<Airbnb or Booking.com search URL>"}, ...]
  Airbnb URLs: build with tools/airbnb_search_url.py (add --currency USD). Booking.com:
  https://www.booking.com/searchresults.html?ss=<place>&checkin=YYYY-MM-DD&checkout=YYYY-MM-DD&group_adults=2&no_rooms=1&selected_currency=USD
Output: per search, a list of cards {title, kind, rating, price_usd, price_text, url}. Prices are the page's
total for the stay incl. fees (Airbnb says "Prices include all fees"; Booking shows taxes separately on some cards).
Airbnb shows ~18-24 cards per search; split the map box for more.
Verified: Oct 8, 2026, Phnom Penh Nov 6-Dec 4 search read "$732 monthly, originally $812" cards.
"""
import json, re, sys, time
from playwright.sync_api import sync_playwright

PROFILE = ".tmp/browser-profile-gf"
MONEY = re.compile(r"\$\s?([\d,]+)")


def airbnb(pg):
    out = []
    for c in pg.query_selector_all('[data-testid="card-container"]'):
        t = c.inner_text()
        lines = [x.strip() for x in t.split("\n") if x.strip() and x.strip() not in (",", "·")]
        a = c.query_selector("a[href*='/rooms/']")
        url = a.get_attribute("href").split("?")[0] if a else ""
        if url.startswith("/"):
            url = "https://www.airbnb.com" + url
        kind = next((x for x in lines if " in " in x and len(x) < 60), "")
        rating = next((x for x in lines if re.fullmatch(r"\d\.\d+ \(\d+\)", x)), "New" if "New" in lines else "")
        title_el = c.query_selector('[data-testid="listing-card-name"]')
        title = title_el.inner_text().strip() if title_el else ""
        ptxt = next((x for x in lines if re.search(r"\$[\d,]+ (monthly|total|for \d+ nights)", x)), "")
        if not ptxt:  # price split over two lines: "$732" then "monthly"/"total"
            for i, x in enumerate(lines[:-1]):
                if MONEY.fullmatch(x) and lines[i + 1] in ("monthly", "total"):
                    ptxt = x + " " + lines[i + 1]
        m = MONEY.search(ptxt)
        out.append({"title": title, "kind": kind, "rating": rating,
                    "price_usd": int(m.group(1).replace(",", "")) if m else None, "price_text": ptxt, "url": url})
    return out


def booking(pg):
    out = []
    for c in pg.query_selector_all('[data-testid="property-card"]'):
        def txt(sel):
            e = c.query_selector(sel)
            return e.inner_text().strip().replace("\n", " ") if e else ""
        ptxt = txt('[data-testid="price-and-discounted-price"]')
        nums = [int(x.replace(",", "")) for x in MONEY.findall(ptxt)]
        a = c.query_selector('a[data-testid="title-link"]')
        out.append({"title": txt('[data-testid="title"]'), "kind": txt('[data-testid="recommended-units"]')[:80],
                    "rating": txt('[data-testid="review-score"]')[:40],
                    "price_usd": nums[-1] if nums else None,  # last number = current price after any discount
                    "price_text": ptxt + " " + txt('[data-testid="taxes-and-charges"]'),
                    "url": (a.get_attribute("href") or "").split("?")[0] if a else ""})
    return out


def main(spec, outp):
    res = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False,
                                                   viewport={"width": 1300, "height": 1000})
        pg = ctx.new_page()
        for s in json.load(open(spec)):
            for attempt in (1, 2):  # Airbnb sometimes hangs on load; retry once, then skip
                try:
                    pg.goto(s["url"], timeout=60000)
                    break
                except Exception as e:
                    print(f'{s["label"]}: load failed (attempt {attempt}): {type(e).__name__}')
            else:
                res.append({"label": s["label"], "url": s["url"], "cards": [], "error": "load timeout"})
                continue
            time.sleep(8)
            for _ in range(3):  # scroll so lazy cards load
                pg.mouse.wheel(0, 4000)
                time.sleep(1.5)
            cards = airbnb(pg) if "airbnb." in s["url"] else booking(pg)
            res.append({"label": s["label"], "url": s["url"], "cards": cards})
            priced = sorted(c["price_usd"] for c in cards if c["price_usd"])
            print(f'{s["label"]}: {len(cards)} cards, {len(priced)} priced'
                  + (f', ${priced[0]}-${priced[-1]}, median ${priced[len(priced)//2]}' if priced else ""))
        ctx.close()
    json.dump(res, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

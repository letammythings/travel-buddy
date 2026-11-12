"""Save the full text of Airbnb / Booking.com listing pages (description + all amenities + visible reviews).

Free: same local Chrome + Playwright setup as tools/stay_price_scan.py (no Firecrawl credits, no login).
Run:  .tmp/venv/bin/python tools/listing_text.py urls.txt OUT_DIR [--checkin 2026-11-06 --checkout 2026-12-04]
urls.txt: one listing URL per line. Output: OUT_DIR/<id>.txt per listing, for grepping size, desk, WiFi, kitchen.
Airbnb hides the description and amenities behind "Show more" / "Show all N amenities" dialogs; this opens both.
"""
import argparse, os, re, time
from playwright.sync_api import sync_playwright

PROFILE = ".tmp/browser-profile-gf"


def dialog_text(pg, button_re):
    try:
        b = pg.get_by_role("button", name=re.compile(button_re, re.I)).first
        b.click(timeout=4000)
        time.sleep(2)
        t = pg.locator('[role="dialog"]').last.inner_text(timeout=4000)
        pg.keyboard.press("Escape")
        time.sleep(1)
        return t
    except Exception as e:
        return f"[no dialog for {button_re}: {type(e).__name__}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls"); ap.add_argument("out")
    ap.add_argument("--checkin"); ap.add_argument("--checkout")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    urls = [u.strip() for u in open(a.urls) if u.strip()]
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False,
                                                   viewport={"width": 1300, "height": 1000})
        pg = ctx.new_page()
        for u in urls:
            lid = re.sub(r"\W+", "_", u.rstrip("/").split("/")[-1].replace(".html", ""))
            q = ""
            if a.checkin:
                q = (f"?check_in={a.checkin}&check_out={a.checkout}&adults=2&currency=USD" if "airbnb." in u else
                     f"?checkin={a.checkin}&checkout={a.checkout}&group_adults=2&no_rooms=1&selected_currency=USD")
            try:
                pg.goto(u + q, timeout=60000)
                time.sleep(7)
                for _ in range(4):
                    pg.mouse.wheel(0, 2500); time.sleep(1)
                parts = [pg.inner_text("body")]
                if "airbnb." in u:
                    parts.append("=== DESCRIPTION ===\n" + dialog_text(pg, r"^Show more$"))
                    parts.append("=== AMENITIES ===\n" + dialog_text(pg, r"Show all \d+ amenities"))
                open(os.path.join(a.out, lid + ".txt"), "w").write(u + "\n\n" + "\n\n".join(parts))
                print("ok", lid)
            except Exception as e:
                print("FAIL", u, type(e).__name__)
        ctx.close()


if __name__ == "__main__":
    main()

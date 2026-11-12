"""Fetch one freely licensed photo per item from Wikimedia Commons, for itinerary pages.

Free, no API key. Needs Pillow (the system python3 has it; .tmp/venv does not).

Spec file (JSON): {"key": "Wikipedia article title" | "search:<Commons query>" | "file:<Commons file name>"}
    {"angkor_wat": "Angkor Wat", "phare": "file:Phare Circus, Siem Reap, Cambodia - 49633492161.jpg",
     "riverside": "search:Sisowath Quay Phnom Penh"}

Usage:
    python3 tools/commons_photos.py spec.json OUT_DIR
Writes OUT_DIR/<key>.jpg (max 640 px, ~20-100 KB each), OUT_DIR/credits.json (artist, license,
Commons page per key) and OUT_DIR/_sheet<N>.jpg contact sheets (8 labeled photos each).

ALWAYS open every _sheet image and check each photo shows the real place or activity before
publishing. A Wikipedia lead image can be off-topic (on 2026-10-07 "Silk Island" came back as
thread spools and "Phare circus" as a bar). If no real photo exists, use none, not a stand-in.

Verify: the script prints "<key> OK <file> | <license> | <artist>" per item and skips keys
already in credits.json, so a rerun after an HTTP 429 picks up where it stopped.
Commons rate-limits (429) after ~10 fast requests; the script waits 3 s per item and backs off.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "TravelBuddyResearch/1.0 (personal trip planning)"}  # never put the user's email here
COMMONS = "https://commons.wikimedia.org/w/api.php?"


def get(url, raw=False):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(10 * (i + 1))
    raise RuntimeError("still rate-limited (429)")


def resolve(ref):
    """Return a Commons file name for a spec value, or None."""
    if ref.startswith("file:"):
        return ref[5:]
    if ref.startswith("search:"):
        q = {"action": "query", "list": "search", "srsearch": ref[7:] + " filetype:bitmap",
             "srnamespace": 6, "srlimit": 1, "format": "json"}
        hits = get(COMMONS + urllib.parse.urlencode(q))["query"]["search"]
        return hits[0]["title"].split(":", 1)[1] if hits else None
    q = {"action": "query", "titles": ref, "prop": "pageimages", "piprop": "name",
         "format": "json", "redirects": 1}
    pages = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q))["query"]["pages"]
    return next(iter(pages.values())).get("pageimage")


def clean_artist(a):
    a = re.sub(r"<[^>]+>", "", html.unescape(a))
    a = re.sub(r"\S+@\S+|\[at\]|\(at\)", "", a)
    return re.sub(r"\s+", " ", a).strip(" ,;")[:60] or "unknown"


def main(spec_path, out):
    from PIL import Image, ImageDraw

    os.makedirs(out, exist_ok=True)
    spec = json.load(open(spec_path))
    cred_path = os.path.join(out, "credits.json")
    credits = json.load(open(cred_path)) if os.path.exists(cred_path) else {}
    for key, ref in spec.items():
        if key in credits:
            continue
        try:
            fname = resolve(ref)
            if not fname:
                print(key, "NO IMAGE")
                continue
            q = {"action": "query", "titles": "File:" + fname, "prop": "imageinfo",
                 "iiprop": "url|extmetadata", "iiurlwidth": 720, "format": "json"}
            pg = next(iter(get(COMMONS + urllib.parse.urlencode(q))["query"]["pages"].values()))
            if "imageinfo" not in pg:
                print(key, "NOT ON COMMONS (likely non-free)", fname)
                continue
            ii = pg["imageinfo"][0]
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "?")
            path = os.path.join(out, key + ".jpg")
            open(path, "wb").write(get(ii["thumburl"], raw=True))
            im = Image.open(path).convert("RGB")
            im.thumbnail((640, 640))
            im.save(path, quality=68)
            credits[key] = {"a": clean_artist(md.get("Artist", {}).get("value", "")), "l": lic,
                            "u": ii["descriptionurl"], "file": fname}
            json.dump(credits, open(cred_path, "w"), indent=1, ensure_ascii=False)
            print(key, "OK", fname, "|", lic, "|", credits[key]["a"])
        except Exception as e:  # keep going; rerun picks up the rest
            print(key, "ERR", e)
        time.sleep(3)

    keys = [k for k in spec if k in credits]
    W, H = 420, 315
    for n in range(0, len(keys), 8):
        sheet = Image.new("RGB", (W * 4, (H + 30) * 2), "white")
        d = ImageDraw.Draw(sheet)
        for i, k in enumerate(keys[n:n + 8]):
            im = Image.open(os.path.join(out, k + ".jpg")).convert("RGB")
            im.thumbnail((W, H))
            x, y = (i % 4) * W, (i // 4) * (H + 30)
            sheet.paste(im, (x, y + 30))
            d.text((x + 6, y + 8), k, fill="black")
        sheet.save(os.path.join(out, f"_sheet{n // 8}.jpg"), quality=80)
    print(f"{len(keys)}/{len(spec)} photos. Now open every _sheet*.jpg and check each one.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

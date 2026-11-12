"""Kumuang Properties (Chiang Mai agent) rental search + listing details. Free: plain HTTP, standard library only.

Search mode: every card of a filtered rent search -> JSON {id: {id,title,rent,size,ready,nums,tags}}
  python3 tools/kumuang_scan.py search OUT.json --min-price 12000 --max-price 23600 [--pool] [--bedrooms 2] [--pages 10]
Detail mode: main text of each listing (related listings cut off) -> OUT_DIR/<id>.main
  python3 tools/kumuang_scan.py detail OUT_DIR <id>,<id>,<id>
Search filters that work (tested Oct 23, 2026): min_price, max_price, community_pool=1, bedroom_amount=N, min_area=N.
property_size_min returned 0 results; don't use it. Card "พร้อมเช่า DD/MM/YYYY" = date the unit became free (day first).
Card rent is usually the 1-year rate; the 3-month rate (if allowed) is only in the detail text ("สัญญา 3-6 เดือน").
Verify: search with --pool and prices 12000-23600 returned 203 cards on Oct 23, 2026.
"""
import argparse, html, json, os, re, time, urllib.request

BASE = "https://kumuangproperties.com"


def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    try:
        return urllib.request.urlopen(r, timeout=60).read().decode()
    except Exception:  # Oct 29, 2026: one IncompleteRead mid-run killed a 19-page detail fetch; retry once
        time.sleep(3)
        return urllib.request.urlopen(r, timeout=60).read().decode()


def cards(h):
    out = []
    pat = r'<a class="no-underline" href="https://kumuangproperties.com/(\d+)/condo">(.*?)(?=<a class="no-underline" href="https://kumuangproperties.com/\d+/condo">|$)'
    for m in re.finditer(pat, h, re.S):
        t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '|', m.group(2)[:3000]))
        parts = [p.strip() for p in t.split('|') if p.strip() and p.strip() != '&nbsp;']
        g = lambda p: (re.search(p, t) or [None, None])[1]
        out.append(dict(id=m.group(1), title=parts[0] if parts else '', rent=g(r'เช่า ([\d,]+)฿'),
                        size=g(r'พื้นที่ใช้สอย ([\d.]+) ตร'), ready=g(r'พร้อมเช่า ([\d/]+)'),
                        nums=[p for p in parts if p.isdigit()][:2]))
    return out


def search(a):
    q = f"{BASE}/search?type=condo&status=rent&min_price={a.min_price}&max_price={a.max_price}"
    if a.pool: q += "&community_pool=1"
    if a.bedrooms: q += f"&bedroom_amount={a.bedrooms}"
    if a.min_area: q += f"&min_area={a.min_area}"
    res = {}
    for p in range(1, a.pages + 1):
        cs = cards(get(q + f"&page={p}"))
        if not cs: break
        for c in cs: res.setdefault(c["id"], c)
        time.sleep(1)
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(len(res), "listings ->", a.out)


def detail(a):
    os.makedirs(a.out, exist_ok=True)
    for i in a.ids.split(','):
        h = re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', '', get(f"{BASE}/{i}/condo"))
        lines = [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', h)).split('\n') if l.strip()]
        s = next((k for k, l in enumerate(lines) if '(ID:' in l), 0)
        e = next((k for k, l in enumerate(lines) if k > s and ('สนใจนัดชม' in l or 'Kumuang Properties Co' in l
                  or 'อสังหาริมทรัพย์ที่เกี่ยวข้อง' in l or 'ส่งข้อความถึงผู้ขาย' in l)), len(lines))
        open(f"{a.out}/{i}.main", "w").write('\n'.join(lines[s:e]))
        time.sleep(1)
    print("saved", a.ids, "->", a.out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="mode", required=True)
    s = sp.add_parser("search"); s.add_argument("out"); s.add_argument("--min-price", type=int, default=0)
    s.add_argument("--max-price", type=int, default=30000); s.add_argument("--pool", action="store_true")
    s.add_argument("--bedrooms", type=int); s.add_argument("--min-area", type=int); s.add_argument("--pages", type=int, default=10)
    d = sp.add_parser("detail"); d.add_argument("out"); d.add_argument("ids")
    a = ap.parse_args(); search(a) if a.mode == "search" else detail(a)

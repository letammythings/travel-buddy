"""Quick gate pass over saved listing pages (output of tools/listing_text.py). Free, no network.

Run:  python3 tools/listing_gate.py CARDS.json PAGES_DIR
CARDS.json: {listing_id: card} from tools/stay_price_scan.py output (id = last URL segment, non-word chars -> "_").
Prints one line per page: price, rating, m2 found, Mbps found, bedrooms, Airbnb Cleanliness score,
count of dirt/bug/smell review hits, and flags (table, stove, wash, hotw, ac, gym, unavail).
"unavail" = "Those dates are not available" or "Unavailable: Washer/Hot water/Kitchen": read why before rejecting.
Example line: m2=[92] mbps=[80, 200] clean=4.8 dirty=0.
"""
import re, glob, json, sys
cards = json.load(open(sys.argv[1]))
for f in sorted(glob.glob(sys.argv[2] + '/*.txt')):
    t = open(f).read(); lid = f.split('/')[-1][:-4]
    c = cards.get(lid, {})
    f_ = lambda p: bool(re.search(p, t, re.I))
    sizes = sorted({int(m.group(1)) for m in re.finditer(r'(\d{2,3})\s?(?:sqm|sq\.? ?m\b|m²|m2\b|square met)', t, re.I)})
    mbps = sorted({int(m.group(1)) for m in re.finditer(r'(\d{1,4})\s?mbps', t, re.I)})
    bed = re.search(r'(\d) bedrooms?', t)
    clean = re.search(r'Cleanliness\s*\n?\s*(\d\.\d)', t)
    dirty = [m.group(0) for m in re.finditer(r'.{0,60}\b(dirty|mou?ld|smell|stain|cockroach|roach|bugs?|ants|dusty|not clean|unclean)\b.{0,40}', t, re.I)]
    flags = dict(table=f_(r'dedicated workspace|\bdesk\b|work ?space|working table|dining table'),
                 stove=f_(r'\bstove\b|cooktop|stovetop|induction|\bhob\b|gas burner'),
                 wash=f_(r'\bwasher\b|washing machine'), hotw=f_(r'hot water|water heater'),
                 ac=f_(r'air condition|\bA/C\b'), gym=f_(r'\bgym\b|fitness'),
                 unavail=f_(r'those dates are not available|We have no availability|Unavailable: (Washer|Hot water|Kitchen)'))
    print(f"{lid[:22]:22} ${c.get('price_usd')} {str(c.get('rating',''))[:24]:>24} | m2={sizes[:4]} mbps={mbps[:5]} "
          f"bed={bed.group(1) if bed else '?'} clean={clean.group(1) if clean else '-'} dirty={len(dirty)} | "
          + " ".join(k for k, v in flags.items() if v) + f" | {c.get('title','')[:40]}")

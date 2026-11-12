#!/usr/bin/env python3
"""Build Airbnb search URLs with dates + a map box + filters.

Free and deterministic: makes no network calls, just prints URLs to scrape.

Examples:
  # One search, Nimman box, Nov 6 -> Dec 6, price cap 22k THB
  python3 tools/airbnb_search_url.py --checkin 2026-11-06 --checkout 2026-12-06 \
      --box nimman --price-max 22000

  # Split a large box into a 2x2 grid (Airbnb only shows ~18 cards per search,
  # and ignores items_offset when scraped, so smaller boxes = more listings seen)
  python3 tools/airbnb_search_url.py --checkin 2026-11-06 --checkout 2026-12-06 \
      --box cm15mi --split 2 --price-max 22000

  # Seasonal check: one month-long window per month for 8 months
  python3 tools/airbnb_search_url.py --checkin 2026-11-06 --box nimman --months 8
"""
import argparse
import calendar
import sys
from datetime import date
from urllib.parse import urlencode

# Named map boxes: (sw_lat, sw_lng, ne_lat, ne_lng)
BOXES = {
    # Nimman + Santitham + Chang Phueak (example anchor area)
    "nimman": (18.7885, 98.9580, 18.8165, 98.9880),
    # ~5 km ring around central Chiang Mai
    "cm-inner": (18.745, 98.935, 18.835, 99.035),
    # ~15 miles around central Chiang Mai
    "cm15mi": (18.571, 98.755, 19.005, 99.215),
}


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def build_url(checkin, checkout, box, adults, min_bedrooms, price_max, currency, place):
    sw_lat, sw_lng, ne_lat, ne_lng = box
    params = [
        ("checkin", checkin.isoformat()),
        ("checkout", checkout.isoformat()),
        ("adults", adults),
        ("room_types[]", "Entire home/apt"),
        ("min_bedrooms", min_bedrooms),
        ("currency", currency),
        ("search_by_map", "true"),
        ("ne_lat", ne_lat), ("ne_lng", ne_lng),
        ("sw_lat", sw_lat), ("sw_lng", sw_lng),
    ]
    if price_max:
        params += [("price_filter_input_type", 2), ("price_max", price_max)]
    return f"https://www.airbnb.com/s/{place}/homes?" + urlencode(params)


def split_box(box, n):
    sw_lat, sw_lng, ne_lat, ne_lng = box
    dlat = (ne_lat - sw_lat) / n
    dlng = (ne_lng - sw_lng) / n
    for i in range(n):
        for j in range(n):
            yield (round(sw_lat + i * dlat, 4), round(sw_lng + j * dlng, 4),
                   round(sw_lat + (i + 1) * dlat, 4), round(sw_lng + (j + 1) * dlng, 4))


def parse_box(value):
    if value in BOXES:
        return BOXES[value]
    parts = [float(x) for x in value.split(",")]
    if len(parts) != 4:
        sys.exit("--box must be a name (%s) or 'sw_lat,sw_lng,ne_lat,ne_lng'" % ", ".join(BOXES))
    return tuple(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--checkin", required=True, type=date.fromisoformat)
    p.add_argument("--checkout", type=date.fromisoformat, help="default: one month after check-in")
    p.add_argument("--box", default="nimman", help="named box or 'sw_lat,sw_lng,ne_lat,ne_lng'")
    p.add_argument("--split", type=int, default=1, help="split box into NxN smaller boxes")
    p.add_argument("--months", type=int, default=0, help="seasonal mode: N consecutive month-long windows")
    p.add_argument("--adults", type=int, default=2)
    p.add_argument("--min-bedrooms", type=int, default=1)
    p.add_argument("--price-max", type=int, default=0, help="monthly cap in --currency (0 = none)")
    p.add_argument("--currency", default="THB")
    p.add_argument("--place", default="Chiang-Mai--Thailand", help="Airbnb place slug in the URL path")
    a = p.parse_args()

    box = parse_box(a.box)
    if a.months:
        windows = [(add_months(a.checkin, i), add_months(a.checkin, i + 1)) for i in range(a.months)]
    else:
        checkout = a.checkout or add_months(a.checkin, 1)
        if checkout <= a.checkin:
            sys.exit("checkout must be after checkin")
        windows = [(a.checkin, checkout)]

    for ci, co in windows:
        for sub in (split_box(box, a.split) if a.split > 1 else [box]):
            print(f"{ci} -> {co}  box={sub}")
            print(build_url(ci, co, sub, a.adults, a.min_bedrooms, a.price_max, a.currency, a.place))


if __name__ == "__main__":
    main()

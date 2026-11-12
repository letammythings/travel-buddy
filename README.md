# Travel Buddy

Research tools for planning long stays abroad as a remote worker: finding a monthly apartment,
checking a place's reviews and hours, comparing flight prices, and turning a plan into a
spreadsheet you can share.

I built these with Claude while planning moves across Southeast Asia. Every tool is free to run:
no paid APIs, no keys. The ones that read websites drive a normal Chrome window on your own
computer with Playwright.

## The tools

**Finding a place to live**

| Tool | What it does |
|---|---|
| `airbnb_search_url.py` | Builds Airbnb search links with dates, a map area and a price cap. Can split an area into a grid, because Airbnb only shows about 18 listings per search. |
| `stay_price_scan.py` | Reads the listing cards (title, rating, total price, link) from Airbnb and Booking.com searches. |
| `listing_text.py` | Saves the full text of each listing: description, every amenity, and the visible reviews. |
| `listing_gate.py` | Quick pass over the saved listings: size in m², WiFi speed, cleanliness score, review words like "dirty" or "bugs", and flags for desk, stove, washer, gym. |
| `kumuang_scan.py`, `fazwaz_scan.py` | Search two Chiang Mai rental sites for longer leases. |

**Checking places**

| Tool | What it does |
|---|---|
| `maps_places.py` | Finds places on Google Maps near where you stay (coworking, gyms…) and returns hours, drive time, rating, and review lines about WiFi and late access. |
| `maps_reviews.py` | Saves a place's rating, address, review topics and reviews to text. |
| `page_text.py` | Prints the text of pages that block simple downloads. |

**Flights**

| Tool | What it does |
|---|---|
| `cash_fare_scan.py` | Cheapest cash fare per route and date from Google Flights. Flags fares that look like page-reading errors. |
| `award_scan.py` | Points prices from AwardTool, with cents-per-point when you give the cash fare. |

**Sharing the plan**

| Tool | What it does |
|---|---|
| `make_trip_sheet.py` | Turns a trip plan (JSON) into a formatted spreadsheet: itinerary with price totals and a Booked? dropdown, plus a checklist tab. |
| `make_compare_sheet.py` | Turns options (JSON) into a side-by-side comparison spreadsheet. |
| `commons_photos.py` | Fetches one freely licensed photo per place from Wikimedia Commons, with credits. |

Each file's top comment explains how to run it, what good output looks like, and what went
wrong when it was tested.

## Setup

```bash
git clone https://github.com/letammythings/travel-buddy.git
cd travel-buddy
python3 -m venv .tmp/venv
.tmp/venv/bin/pip install -r requirements.txt
```

The browser tools use your installed Google Chrome.

## Try it

```bash
.tmp/venv/bin/python tools/make_trip_sheet.py examples/trip_sheet.json trip.xlsx
.tmp/venv/bin/python tools/make_compare_sheet.py examples/compare_sheet.json compare.xlsx
python3 tools/airbnb_search_url.py --checkin 2026-12-08 --checkout 2027-01-08 --box nimman --price-max 22000
```

The example files are made up, to show the format.

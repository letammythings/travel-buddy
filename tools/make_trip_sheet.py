"""Build a formatted trip-plan spreadsheet (.xlsx) from a JSON spec, ready to upload to Google Drive.

Free, no network. Needs openpyxl in .tmp/venv:  .tmp/venv/bin/pip install openpyxl
Run:  .tmp/venv/bin/python tools/make_trip_sheet.py examples/trip_sheet.json .tmp/trip.xlsx
      add --b64 to also write .tmp/trip.xlsx.b64 (the text to pass to Drive create_file as base64Content)
Output: an "Itinerary" tab (rows colored by section, travel days bold, Booked? dropdown, price x travelers
formulas, a "Known so far" total) and a "Checklist" tab (grouped items, Done? dropdown).
Spec format: see examples/trip_sheet.json. Row keys: date, sleep, plan, how, leaves, arrives,
price (number or null), per ("person" | "car" | "stay" | ""), booked ("Yes" | "No" | "Not needed"),
notes, section (a key in "sections"; "travel" makes the row bold), source (optional cell note on the price).
Verified: Oct 7, 2026, Cambodia sheet (13 KB) uploaded and converted with formulas, colors and dropdowns intact.
"""
import argparse, base64, json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule

F = "Arial"
HEAD = "2F4F6F"
thin = Side(style="thin", color="D0D0D0")
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)


def font(**k):
    return Font(name=F, **k)


def fill(c):
    return PatternFill("solid", fgColor=c)


def header(ws, row, names):
    for i, h in enumerate(names, 1):
        c = ws.cell(row, i, h)
        c.font = font(bold=True, color="FFFFFF")
        c.fill = fill(HEAD)
        c.alignment = Alignment(vertical="center", wrap_text=True)
        c.border = BOX


def yes_rules(ws, rng, options):
    dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(rng)
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"Yes"'], fill=fill("B7E1CD"),
                                                  font=Font(name=F, bold=True, color="0B6E3B")))
    if "Not needed" in options:
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"No"'],
                                                      font=Font(name=F, color="B00020")))


def itinerary(wb, s):
    ws = wb.active
    ws.title = "Itinerary"
    secs = s["sections"]
    ws["A1"] = s["title"]; ws["A1"].font = font(bold=True, size=16)
    ws["A2"] = s.get("subtitle", ""); ws["A2"].font = font(italic=True, color="666666")
    ws["A3"] = "Travelers"; ws["A3"].font = font(bold=True)
    ws["B3"] = s.get("travelers", 2); ws["B3"].font = font(bold=True, color="0000FF"); ws["B3"].fill = fill("FFF2CC")
    ws["C3"] = "Blue on yellow = a number you can change."; ws["C3"].font = font(italic=True, color="666666")
    H = 5
    header(ws, H, ["Date", "Where we sleep", "Plan", "Getting there", "Leaves", "Arrives", "Price ($)",
                   "Price is per", "Total for us ($)", "Booked?", "Notes"])
    r = first = H + 1
    for row in s["rows"]:
        sec = row.get("section", "travel")
        bold = sec == "travel"
        vals = [row.get("date"), row.get("sleep"), row.get("plan"), row.get("how", ""), row.get("leaves", ""),
                row.get("arrives", ""), row.get("price"), row.get("per", ""), None, row.get("booked", "No"),
                row.get("notes", "")]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v)
            c.font = font(bold=bold and i in (1, 3, 4))
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BOX
            c.fill = fill(secs[sec]["color"])
        ws.cell(r, 7).number_format = "$#,##0"
        ws.cell(r, 7).font = font(color="0000FF")
        ws.cell(r, 9).value = f'=IF(G{r}="","",IF(H{r}="person",G{r}*$B$3,G{r}))'
        ws.cell(r, 9).number_format = "$#,##0"
        if row.get("source"):
            ws.cell(r, 7).comment = Comment(row["source"], "Claude")
        r += 1
    last = r - 1
    ws.cell(r, 8, "Known so far").font = font(bold=True)
    ws.cell(r, 9, f"=SUM(I{first}:I{last})").font = font(bold=True)
    ws.cell(r, 9).number_format = "$#,##0"
    ws.cell(r, 11, s.get("total_note", "")).font = font(italic=True, color="666666")
    yes_rules(ws, f"J{first}:J{last}", ["Yes", "No", "Not needed"])
    for col, w in zip("ABCDEFGHIJK", [20, 22, 44, 20, 16, 20, 10, 11, 14, 11, 52]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = f"A{H + 1}"
    lg = r + 2
    ws.cell(lg, 1, "Colors").font = font(bold=True)
    for j, (k, v) in enumerate(secs.items()):
        c = ws.cell(lg + 1 + j, 1, v["label"])
        c.fill = fill(v["color"]); c.font = font(bold=(k == "travel")); c.border = BOX


def checklist(wb, s):
    cs = wb.create_sheet("Checklist")
    cs["A1"] = s.get("checklist_title", "Before and during the trip"); cs["A1"].font = font(bold=True, size=16)
    header(cs, 3, ["Item", "When", "Done?", "Notes"])
    rr = 4
    for group in s["checklist"]:
        c = cs.cell(rr, 1, group["group"]); c.font = font(bold=True, size=12)
        for i in range(1, 5):
            cs.cell(rr, i).fill = fill("E8EEF4")
        rr += 1
        for it in group["items"]:
            for i, v in enumerate([it["item"], it.get("when", ""), it.get("done", "No"), it.get("notes", "")], 1):
                c = cs.cell(rr, i, v)
                c.font = font(); c.alignment = Alignment(vertical="top", wrap_text=True); c.border = BOX
            rr += 1
    yes_rules(cs, f"C4:C{rr - 1}", ["Yes", "No"])
    for col, w in zip("ABCD", [44, 24, 10, 60]):
        cs.column_dimensions[col].width = w
    cs.freeze_panes = "A4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--b64", action="store_true")
    a = ap.parse_args()
    s = json.load(open(a.spec))
    wb = Workbook()
    itinerary(wb, s)
    if s.get("checklist"):
        checklist(wb, s)
    wb.save(a.out)
    print(f"saved {a.out}")
    if a.b64:
        b = base64.b64encode(open(a.out, "rb").read()).decode()
        open(a.out + ".b64", "w").write(b)
        print(f"base64: {a.out}.b64 ({len(b)} chars)")


if __name__ == "__main__":
    main()

"""Build a side-by-side comparison spreadsheet (.xlsx) from a JSON spec: one tab per table, ready for Google Drive.

Free, no network. Needs openpyxl in .tmp/venv:  .tmp/venv/bin/pip install openpyxl
Run:  .tmp/venv/bin/python tools/make_compare_sheet.py examples/compare_sheet.json .tmp/compare.xlsx --b64
Spec: {"title", "subtitle", "tabs": [{"name", "intro" (optional), "columns": [[header, width], ...],
       "money": [column indexes shown as $], "group": column index whose value colors the row (optional),
       "colors": {value: "RRGGBB"}, "rows": [[cell, ...], ...]}]}
Use null for an unknown price (shown blank, never guessed). Keep text plain: no emoji.
Verified: Oct 8, 2026, Cambodia transport comparison.
"""
import argparse, base64, json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

F = "Arial"
thin = Side(style="thin", color="D0D0D0")
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)


def build(spec, out):
    wb = Workbook()
    wb.remove(wb.active)
    for tab in spec["tabs"]:
        ws = wb.create_sheet(tab["name"][:31])
        ws.cell(1, 1, spec["title"] + ": " + tab["name"]).font = Font(name=F, size=14, bold=True)
        ws.cell(2, 1, tab.get("intro") or spec.get("subtitle", "")).font = Font(name=F, italic=True, color="555555")
        r0 = 4
        for i, (name, width) in enumerate(tab["columns"], 1):
            c = ws.cell(r0, i, name)
            c.font = Font(name=F, bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2F4F6F")
            c.alignment = Alignment(vertical="center", wrap_text=True)
            c.border = BOX
            ws.column_dimensions[c.column_letter].width = width
        money = set(tab.get("money", []))
        g, colors = tab.get("group"), tab.get("colors", {})
        for r, row in enumerate(tab["rows"], r0 + 1):
            color = colors.get(row[g]) if g is not None else None
            for i, v in enumerate(row):
                c = ws.cell(r, i + 1, v)
                c.font = Font(name=F, bold=(i == 0))
                c.alignment = Alignment(vertical="top", wrap_text=True)
                c.border = BOX
                if i in money and isinstance(v, (int, float)):
                    c.number_format = '"$"#,##0'
                if color:
                    c.fill = PatternFill("solid", fgColor=color)
        ws.freeze_panes = ws.cell(r0 + 1, 2)
    wb.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--b64", action="store_true", help="also write OUT.b64 for Drive create_file base64Content")
    a = ap.parse_args()
    build(json.load(open(a.spec)), a.out)
    if a.b64:
        open(a.out + ".b64", "w").write(base64.b64encode(open(a.out, "rb").read()).decode())
    print("wrote", a.out)

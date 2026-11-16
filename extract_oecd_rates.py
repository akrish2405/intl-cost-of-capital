"""Measure OECD Figure 2.1 bar lengths (vector paths) -> statutory CIT rate, %."""
import sys, json, pdfplumber
pg = pdfplumber.open(sys.argv[1]).pages[23]
# Axis tick marks (0% and 40%) found from vertical tick lines
AX = {"L": (143.62, 297.55), "R": (315.53, 461.57)}
words = pg.extract_words()
codes = [w for w in words if len(w["text"]) == 3 and w["text"].isupper() and w["top"] < pg.height * 0.75]
bars = [r for r in pg.curves if r.get("fill") and (r["bottom"] - r["top"]) < 8 and r["top"] < pg.height * 0.75]
out = {}
for c in codes:
    side = "R" if c["x0"] > 299 else "L"
    x0, x40 = AX[side]
    cy = (c["top"] + c["bottom"]) / 2
    rs = [r for r in bars if abs((r["top"] + r["bottom"]) / 2 - cy) < 2.5 and abs(r["x0"] - x0) < 1.5]
    out[c["text"]] = round((max(r["x1"] for r in rs) - x0) / (x40 - x0) * 40, 2) if rs else 0.0
print(json.dumps(out))

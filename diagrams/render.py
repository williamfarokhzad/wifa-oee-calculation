"""Rebuild SVG and WebP. Requires Inkscape CLI and Pillow; the OEE lab does not."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from oee import percent, read_shifts, summarize

WIDTH, HEIGHT = 1000, 560
INK = "#123048"
MUTED = "#38536a"
GREEN = "#087f71"
ORANGE = "#d68128"
RED = "#b54a58"
BLUE = "#406c9b"


def label(x, y, content, size=30, color=INK, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(content)}</text>')


def box(x, y, w, h, color, radius=0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{color}"/>'


def render(name, title, subtitle, markup):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
           f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="DejaVu Sans,sans-serif" role="img">'
           f'<title>{escape(title)}</title>{box(0, 0, WIDTH, HEIGHT, "#f1f6fb", 26)}'
           f'{label(56, 74, title, 40, weight=700)}{label(56, 121, subtitle, 25, MUTED)}'
           + "".join(markup) + "</svg>\n")
    src = HERE / (name + ".svg")
    src.write_text(svg, encoding="utf-8")
    with TemporaryDirectory() as tmp:
        png = Path(tmp) / "diagram.png"
        subprocess.run(["inkscape", str(src), f"--export-filename={png}"],
                       check=True, capture_output=True)
        with Image.open(png) as image:
            image.save(HERE / (name + ".webp"), format="WEBP", lossless=True, method=6)


def ledger():
    r = summarize(read_shifts(ROOT / "examples/single-shift.csv"))
    bars = [("Stops", r.stop_ms, BLUE), ("Speed loss", r.speed_loss_ms, ORANGE),
            ("Rejects", r.reject_loss_ms, RED), ("Productive", r.good_ms, GREEN)]
    out = [label(56, 187, "Planned production: 3,600 s", 31, weight=700)]
    left = 56
    for i, (name, value, color) in enumerate(bars):
        w = 888 * value / r.planned_ms
        out.append(box(left, 212, w, 75, color))
        left += w
        x, y = (56 if i % 2 == 0 else 516), 347 + 69 * (i // 2)
        out += [box(x, y - 24, 30, 30, color, 4), label(x + 45, y, f"{name}: {value//1000:,} s", 29)]
    out.append(label(56, 501, f"Productive ÷ planned = {percent(r.oee)} OEE", 31, GREEN, 700))
    render("oee-shift-loss-ledger", "Where 3,600 seconds go",
           "One machine, one part, one synthetic shift", out)


def weighting():
    shifts = read_shifts(ROOT / "examples/unequal-shifts.csv")
    results = [summarize([s]) for s in shifts]
    combined = summarize(shifts)
    average = sum(r.oee for r in results) / len(results)
    out = []
    for i, r in enumerate(results):
        y = 181 + i * 103
        scale = 520 / max(item.planned_ms for item in results)
        out += [label(56, y, f"{shifts[i].name}: {r.planned_ms//1000:,} s planned", 29, weight=700),
                box(56, y + 16, scale * r.planned_ms, 33, "#c5d3df"),
                box(56, y + 16, scale * r.good_ms, 33, GREEN),
                label(923, y + 46, percent(r.oee), 33, GREEN, 700, "end")]
    out += [box(56, 370, 22, 22, GREEN, 3), label(88, 390, "Productive seconds", 24, MUTED),
            box(455, 370, 22, 22, "#c5d3df", 3), label(488, 390, "Lost seconds", 24, MUTED),
            label(56, 464, f"Simple average: {percent(average)}", 32, MUTED),
            label(56, 516, f"Combined by time: {percent(combined.oee)}", 34, GREEN, 700)]
    render("oee-unequal-shift-weighting", "Two shifts, different lengths",
           "The longer shift accounts for four times as much planned time", out)


if __name__ == "__main__":
    ledger()
    weighting()

"""Generate SYNTHETIC demo photos of a 9-in-1 drinking-water test strip next to its colour chart.

These are drawn with Pillow - they are NOT photos of real water. Each PNG carries a tEXt chunk
`jalparakh_demo=<scenario>` so the app (a) marks tests made with them as demo data, excluded from the
public impact counters, and (b) the offline mock reader knows which readings to return.

    python scripts/make_demo_strips.py   ->  demo_assets/demo_safe.png, demo_high_fluoride.png,
                                             demo_high_nitrate_iron.png, demo_blurry.png
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from PIL.PngImagePlugin import PngInfo

OUT = Path(__file__).resolve().parent.parent / "demo_assets"

# (label, unit, [(value, rgb), ...]) - colour ramps loosely modelled on common retail strips
CHART = [
    ("pH", "", [(6.0, (236, 160, 60)), (6.5, (230, 186, 70)), (7.0, (200, 190, 80)), (7.5, (150, 170, 90)),
                (8.0, (100, 150, 110)), (8.5, (70, 120, 130))]),
    ("Hardness", "ppm", [(0, (60, 90, 170)), (50, (90, 90, 170)), (120, (130, 90, 160)), (250, (170, 80, 140)),
                         (425, (200, 70, 120)), (1000, (210, 60, 100))]),
    ("Alkalinity", "ppm", [(0, (225, 200, 90)), (40, (190, 190, 100)), (120, (130, 170, 120)),
                           (180, (90, 150, 140)), (240, (60, 120, 140)), (360, (40, 100, 130))]),
    ("Nitrate", "ppm", [(0, (250, 245, 235)), (10, (245, 215, 225)), (25, (235, 180, 205)), (50, (220, 140, 180)),
                        (100, (200, 100, 160)), (250, (170, 60, 130))]),
    ("Nitrite", "ppm", [(0, (250, 245, 235)), (0.5, (245, 225, 230)), (1, (240, 200, 215)), (3, (225, 160, 195)),
                        (5, (205, 120, 175)), (10, (180, 80, 150))]),
    ("Free Cl", "ppm", [(0, (250, 248, 240)), (0.5, (225, 230, 240)), (1, (195, 210, 235)), (3, (150, 180, 225)),
                        (5, (110, 150, 210)), (10, (70, 110, 190))]),
    ("Iron", "ppm", [(0, (250, 245, 230)), (0.3, (245, 230, 200)), (1, (235, 205, 160)), (3, (215, 170, 120)),
                     (5, (195, 140, 90)), (10, (170, 110, 70))]),
    ("Fluoride", "ppm", [(0, (240, 120, 150)), (0.5, (235, 140, 165)), (1, (230, 165, 180)), (1.5, (225, 190, 195)),
                         (2, (220, 210, 210)), (4, (215, 225, 225))]),
    ("Lead", "ppm", [(0, (250, 250, 245)), (0.01, (240, 235, 240)), (0.05, (225, 210, 230)), (0.1, (205, 180, 215)),
                     (0.5, (180, 150, 200)), (1, (150, 120, 185))]),
]

SCENARIOS = {
    "safe": {"pH": 7.0, "Hardness": 120, "Alkalinity": 120, "Nitrate": 10, "Nitrite": 0, "Free Cl": 0.5,
             "Iron": 0, "Fluoride": 0.5, "Lead": 0},
    "fluoride": {"pH": 8.0, "Hardness": 250, "Alkalinity": 240, "Nitrate": 10, "Nitrite": 0, "Free Cl": 0,
                 "Iron": 0, "Fluoride": 2, "Lead": 0},
    "nitrate": {"pH": 7.0, "Hardness": 120, "Alkalinity": 120, "Nitrate": 100, "Nitrite": 1, "Free Cl": 0,
                "Iron": 3, "Fluoride": 0.5, "Lead": 0},
}
FILES = {"safe": "demo_safe.png", "fluoride": "demo_high_fluoride.png", "nitrate": "demo_high_nitrate_iron.png"}


def font(size: int, bold: bool = False):
    for name in (["DejaVuSans-Bold.ttf"] if bold else []) + ["DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def jitter(rgb, rnd, amt=8):
    return tuple(max(0, min(255, c + rnd.randint(-amt, amt))) for c in rgb)


def draw(scenario: str, seed: int) -> Image.Image:
    rnd = random.Random(seed)
    W, H = 1100, 780
    img = Image.new("RGB", (W, H), (205, 178, 140))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 6):  # wood-ish table
        shade = 190 + int(15 * ((y // 6) % 5) / 5) + rnd.randint(-4, 4)
        d.line([(0, y), (W, y)], fill=(shade, int(shade * 0.86), int(shade * 0.68)), width=6)
    # chart card (the bottle label)
    cx0, cy0, cx1, cy1 = 60, 50, 760, 730
    d.rounded_rectangle([cx0 + 8, cy0 + 10, cx1 + 8, cy1 + 10], 22, fill=(120, 100, 80))
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 22, fill=(252, 252, 248), outline=(200, 200, 200), width=2)
    d.text((cx0 + 24, cy0 + 16), "9-in-1 Drinking Water Test Strips", fill=(20, 60, 110), font=font(26, True))
    d.text((cx0 + 24, cy0 + 50), "Dip 1 s - wait 30 s - compare (ppm = mg/L)", fill=(90, 90, 90), font=font(17))
    sw, gap, rowh, top = 78, 8, 64, cy0 + 86
    for i, (label, unit, ramp) in enumerate(CHART):
        y = top + i * rowh
        d.text((cx0 + 22, y + 18), label, fill=(30, 30, 30), font=font(18, True))
        for j, (val, rgb) in enumerate(ramp):
            x = cx0 + 160 + j * (sw + gap)
            d.rounded_rectangle([x, y + 4, x + sw, y + 40], 6, fill=rgb, outline=(210, 210, 210))
            d.text((x + 6, y + 44), f"{val:g}", fill=(60, 60, 60), font=font(14))
    # the strip
    sx0, sy0, sx1 = 840, 40, 900
    d.rectangle([sx0 + 5, sy0 + 6, sx1 + 5, H - 30], fill=(130, 110, 90))
    d.rectangle([sx0, sy0, sx1, H - 36], fill=(248, 248, 246), outline=(215, 215, 215))
    values = SCENARIOS[scenario]
    for i, (label, _unit, ramp) in enumerate(CHART):
        y = top + i * rowh
        target = values[label]
        rgb = min(ramp, key=lambda vr: abs(vr[0] - target))[1]
        d.rectangle([sx0 + 8, y + 2, sx1 - 8, y + 44], fill=jitter(rgb, rnd), outline=(200, 200, 200))
    d.text((sx1 + 18, 60), "dipped\nstrip", fill=(60, 45, 30), font=font(18))
    # label so nobody mistakes it for a real photo
    d.rounded_rectangle([W - 320, H - 58, W - 14, H - 16], 10, fill=(180, 20, 40))
    d.text((W - 304, H - 50), "SYNTHETIC DEMO IMAGE", fill=(255, 255, 255), font=font(19, True))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def save(img: Image.Image, path: Path, scenario: str) -> None:
    meta = PngInfo()
    meta.add_text("jalparakh_demo", scenario)
    meta.add_text("Description", "Synthetic demo image generated by Jal Parakh (not a real water test)")
    img.save(path, "PNG", pnginfo=meta, optimize=True)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for i, (sc, fname) in enumerate(FILES.items()):
        save(draw(sc, 7 + i), OUT / fname, sc)
    save(draw("safe", 99).filter(ImageFilter.GaussianBlur(9)), OUT / "demo_blurry.png", "blurry")
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("demo_*.png"))))


if __name__ == "__main__":
    main()

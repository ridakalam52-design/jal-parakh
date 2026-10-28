"""Draw docs/banner.png (README banner) with Pillow. Needs Noto Sans + Noto Sans Devanagari and libraqm."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2  # draw at 2x, then downsample for smooth edges
W, H = 1280 * S, 400 * S
FONTS = Path("/usr/share/fonts/truetype/noto")
OUT = Path(__file__).resolve().parent.parent / "docs" / "banner.png"


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size * S, layout_engine=ImageFont.Layout.RAQM)


def main():
    img = Image.new("RGB", (W, H))
    px = img.load()
    top, bot = (8, 74, 104), (4, 28, 48)
    for y in range(H):
        t = y / (H - 1)
        for x in range(W):
            s = min(1, t + 0.15 * x / W)
            px[x, y] = tuple(round(top[i] + (bot[i] - top[i]) * s) for i in range(3))

    # soft light glow behind the drop
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((60 * S, 40 * S, 400 * S, 380 * S), fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(70 * S))
    img = Image.composite(Image.new("RGB", (W, H), (40, 190, 220)), img, glow)

    # waves along the bottom
    waves = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(waves)
    for i, (base, amp, alpha, col) in enumerate([(336, 12, 70, (64, 200, 230)), (352, 10, 110, (30, 160, 200)),
                                                 (370, 9, 200, (6, 60, 90))]):
        pts = [(x, S * (base + amp * math.sin(x / S / (95 + 25 * i) + i * 1.7))) for x in range(0, W + 8, 8)]
        wd.polygon(pts + [(W, H), (0, H)], fill=col + (alpha,))
    img = Image.alpha_composite(img.convert("RGBA"), waves)

    d = ImageDraw.Draw(img)
    # water drop with a check mark
    cx, cy, r = 205 * S, 200 * S, 92 * S
    drop = [(cx + r * math.cos(a), cy + 30 + r * math.sin(a)) for a in [math.radians(t) for t in range(-30, 211, 4)]]
    drop = [(cx, cy - 135 * S)] + drop
    d.polygon(drop, fill=(120, 225, 245))
    d.ellipse((cx - 50 * S, cy - 10 * S, cx - 18 * S, cy + 40 * S), fill=(200, 245, 252))
    d.line([(cx - 40 * S, cy + 40 * S), (cx - 8 * S, cy + 72 * S), (cx + 48 * S, cy + 8 * S)], fill=(6, 50, 75), width=16 * S, joint="curve")

    white, aqua, soft = (255, 255, 255), (120, 225, 245), (200, 232, 240)
    x0 = 360 * S
    base = 150 * S
    title_en = font("NotoSans-Bold.ttf", 76)
    title_hi = font("NotoSansDevanagari-Bold.ttf", 76)
    d.text((x0, base), "Jal Parakh", font=title_en, fill=white, anchor="ls")
    w_en = d.textlength("Jal Parakh", font=title_en)
    d.text((x0 + w_en + 22 * S, base), "—", font=title_en, fill=aqua, anchor="ls")
    w_dash = d.textlength("—", font=title_en)
    d.text((x0 + w_en + w_dash + 44 * S, base), "जल परख", font=title_hi, fill=aqua, anchor="ls")

    tag = font("NotoSans-Regular.ttf", 34)
    d.text((x0, 180 * S), "Snap a ₹100 water-test strip.", font=tag, fill=white)
    d.text((x0, 226 * S), "Know if your water is safe.", font=tag, fill=white)
    small = font("NotoSans-Regular.ttf", 21)
    d.text((x0, 288 * S), "AI strip reader · BIS IS 10500 rules · CGWB district data · Hindi + English",
           font=small, fill=soft)

    img.convert("RGB").resize((W // S, H // S), Image.LANCZOS).save(OUT, optimize=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()

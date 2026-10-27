#!/usr/bin/env python3
"""Draws the program's icon (icon.png and icon.ico): a "W" and an "O" (Warframe Overlay) where the O is a sniper-scope
reticle. An original design, drawn here with Pillow so it can be regenerated: python build_icon.py"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024                      # drawing size (then shrunk: smooth edges)
BG1, BG2 = (8, 26, 22), (16, 54, 44)            # deep green
CYAN, GOLD, WHITE = (190, 240, 60), (215, 235, 110), (236, 250, 215)   # lime accents


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # rounded square with a vertical gradient
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        k = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * k) for i in range(3)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([14, 14, S - 15, S - 15], radius=int(S * 0.21), outline=CYAN + (150,), width=10)

    def thick(points, width, color):
        d.line(points, fill=color, width=width, joint="curve")
        for x, y in (points[0], points[-1]):
            d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=color)

    # W (left): four strokes, sharp like a blade
    w_pts = [(90, 340), (190, 700), (290, 480), (390, 700), (490, 340)]
    thick(w_pts, 66, WHITE)
    # O (right) = scope: ring, crosshair, centre dot
    cx, cy, r = 765, 520, 170
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GOLD, width=54)
    for a in (0, 90, 180, 270):
        dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line([(cx + dx * (r + 55), cy + dy * (r + 55)), (cx + dx * (r - 95), cy + dy * (r - 95))],
               fill=CYAN, width=24)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=CYAN)
    # small accent under the letters
    d.rectangle([110, 800, 914, 816], fill=CYAN + (170,))
    return img


def main():
    here = Path(__file__).parent
    big = draw()
    big.resize((512, 512), Image.LANCZOS).save(here / "icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.resize((256, 256), Image.LANCZOS).save(here / "icon.ico", sizes=[(s, s) for s in sizes])
    print("icon.png, icon.ico written")


if __name__ == "__main__":
    main()

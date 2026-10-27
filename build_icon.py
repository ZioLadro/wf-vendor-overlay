#!/usr/bin/env python3
"""Draws the program's icon (icon.png and icon.ico): the silhouette of a man in his thirties with dreadlocks, half
cybernetic, holding a sniper rifle, over a green glow, with a small W and O (Warframe Overlay) at the bottom.
An original design drawn with Pillow so it can be regenerated: python build_icon.py"""
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024
BG1, BG2 = (6, 20, 17), (14, 46, 38)
LIME, PALE, SIL = (190, 240, 60), (236, 250, 215), (5, 10, 9)


def background() -> Image.Image:
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        k = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * k) for i in range(3)) + (255,))
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([200, 140, 840, 780], fill=LIME + (120,))
    grad.alpha_composite(glow.filter(ImageFilter.GaussianBlur(110)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle([14, 14, S - 15, S - 15], radius=int(S * 0.21), outline=LIME + (150,), width=10)
    return out


def figure() -> Image.Image:
    """The silhouette (dark) with a lime rim light, and the cybernetic half drawn in lime lines. Man facing right, holding
    a sniper rifle across his body, dreadlocks falling behind his head."""
    sil = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(sil)

    def poly(pts):
        d.polygon(pts, fill=SIL)

    def stroke(pts, w):
        d.line(pts, fill=SIL, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=SIL)

    # legs, boots
    poly([(470, 600), (555, 600), (575, 770), (560, 900), (490, 900), (495, 770)])
    poly([(545, 600), (625, 600), (665, 770), (680, 900), (610, 905), (590, 775)])
    poly([(478, 890), (566, 890), (590, 930), (462, 930)])
    poly([(600, 892), (690, 892), (712, 932), (590, 932)])
    # torso: broad shoulders, narrow waist, open coat tails
    poly([(430, 345), (625, 345), (665, 415), (630, 610), (470, 610), (415, 430)])
    poly([(465, 580), (630, 580), (690, 760), (430, 760), (445, 650)])
    # neck, head in profile, jaw and nose
    poly([(520, 285), (585, 285), (590, 350), (515, 350)])
    d.ellipse([485, 160, 610, 300], fill=SIL)
    poly([(588, 222), (628, 250), (594, 266), (592, 296), (560, 298)])
    # dreadlocks: separate ropes falling behind the head over the shoulder
    ropes = [(500, 170, 400, 350, 22), (492, 185, 380, 400, 22), (490, 205, 372, 455, 20), (505, 165, 430, 360, 20),
             (515, 160, 455, 330, 18), (487, 225, 392, 500, 18), (528, 158, 470, 300, 16)]
    for sx, sy, ex, ey, w in ropes:
        stroke([(sx, sy), ((sx + ex) / 2 - 30, (sy + ey) / 2 - 10), (ex, ey)], w)
    d.pieslice([480, 148, 622, 280], 170, 350, fill=SIL)
    # sniper rifle across the body: stock at the shoulder, long barrel up to the right, scope, bipod
    stroke([(335, 650), (470, 575)], 40)                                          # stock
    d.line([(450, 575), (930, 360)], fill=SIL, width=30)                          # receiver + long barrel
    d.line([(520, 548), (720, 466)], fill=SIL, width=52)                          # scope tube
    d.ellipse([498, 520, 556, 578], fill=SIL)
    d.ellipse([694, 438, 750, 494], fill=SIL)
    d.line([(820, 425), (790, 520)], fill=SIL, width=14)                          # bipod
    d.line([(850, 412), (878, 508)], fill=SIL, width=14)
    # arms: rear hand at the grip, front arm reaching to the fore-end
    stroke([(440, 395), (410, 505), (500, 590)], 54)
    stroke([(620, 395), (690, 480), (760, 455)], 50)

    # rim light: the silhouette's outline in lime, so the rifle and arms separate from the body
    alpha = sil.getchannel("A")
    ring = ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(9)), alpha)
    rim = Image.new("RGBA", (S, S), LIME + (0,))
    rim.putalpha(ring.point(lambda v: int(v * 0.45)))
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.alpha_composite(rim)
    img.alpha_composite(sil)
    d2 = ImageDraw.Draw(img)

    # cybernetic half (lime): metal face side, glowing eye, seams; front arm segments, joints; chest line
    ln = lambda pts, w=8: d2.line(pts, fill=LIME, width=w, joint="curve")
    d2.pieslice([485, 160, 610, 300], 300, 95, fill=(30, 56, 46, 255))
    ln([(550, 168), (556, 240), (592, 268)])
    ln([(525, 262), (590, 290)], 6)
    d2.ellipse([566, 212, 584, 230], fill=LIME)
    d2.ellipse([560, 206, 590, 236], outline=LIME + (140,), width=3)
    for pts in ([(655, 410), (668, 452)], [(678, 440), (694, 478)], [(710, 462), (748, 472)]):
        ln(pts, 9)
    d2.ellipse([684, 466, 706, 488], fill=LIME)
    d2.ellipse([608, 380, 630, 402], fill=LIME)
    ln([(545, 400), (545, 560)], 6)
    ln([(525, 470), (565, 470)], 6)
    ln([(440, 520), (470, 560)], 7)                                               # grip hand: cyber knuckles
    return img


def letters(img):
    """A small W and O (Warframe Overlay) under the figure."""
    d = ImageDraw.Draw(img)
    w = [(385, 870), (420, 960), (452, 900), (484, 960), (519, 870)]
    d.line(w, fill=PALE, width=20, joint="curve")
    for x, y in (w[0], w[-1]):
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=PALE)
    cx, cy, r = 610, 915, 46
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=LIME, width=18)
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=LIME)


def draw() -> Image.Image:
    img = background()
    img.alpha_composite(figure())
    letters(img)
    return img


def main():
    here = Path(__file__).parent
    big = draw()
    big.resize((512, 512), Image.LANCZOS).save(here / "icon.png")
    big.resize((256, 256), Image.LANCZOS).save(here / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("icon.png, icon.ico written")


if __name__ == "__main__":
    main()

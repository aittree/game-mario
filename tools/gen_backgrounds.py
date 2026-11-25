"""生成 4 套主题的远景/近景背景与关卡缩略图无关的装饰层。

输出（1400×720）：
- bg_grass_far.png / bg_grass_near.png
- bg_cave_far.png / bg_cave_near.png
- bg_sky_far.png / bg_sky_near.png
- bg_castle_far.png / bg_castle_near.png

远景不透明，近景 RGBA 透明，绘制时水平重复 3 次保证 1400px 平铺无缝。
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1400, 720
OUT = Path(__file__).resolve().parents[1] / "assets" / "images"


def gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    assert px is not None
    for y in range(H):
        t = y / (H - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = color
    return img


def composite(base: Image.Image, draw_fn: Callable[[ImageDraw.ImageDraw], None]) -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(overlay, "RGBA"))
    return Image.alpha_composite(base.convert("RGBA"), overlay)


def cloud(d: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float,
          color: tuple[int, int, int, int]) -> None:
    for dx in (-W, 0, W):
        cx = x + dx
        d.ellipse([cx, y, cx + w, y + h], fill=color)
        d.ellipse([cx + w * 0.22, y - h * 0.45, cx + w * 0.72, y + h * 0.6], fill=color)
        d.ellipse([cx + w * 0.48, y - h * 0.2, cx + w, y + h * 0.8], fill=color)


def periodic_range(d: ImageDraw.ImageDraw, base_y: float, height: float, color: tuple[int, int, int, int],
                   freq: float, phase: float, step: int = 14) -> None:
    """周期函数保证 x=0 与 x=W 高度一致，平铺无接缝。"""
    for dx in (-W, 0, W):
        points: list[tuple[float, float]] = []
        for x in range(0, W + step, step):
            wave = 0.5 + 0.5 * math.sin(2 * math.pi * freq * x / W + phase)
            yy = base_y - height * (0.35 + 0.65 * wave)
            points.append((x + dx, yy))
        points += [(W + dx, H), (dx, H)]
        d.polygon(points, fill=color)


def hills(d: ImageDraw.ImageDraw, base_y: float, height: float, color: tuple[int, int, int, int],
          freq: float, phase: float) -> None:
    periodic_range(d, base_y, height, color, freq, phase, step=10)


def trees(d: ImageDraw.ImageDraw, ground_y: int, color: tuple[int, int, int, int],
          count: int, seed: int, scale: float = 1.0) -> None:
    rng = random.Random(seed)
    for i in range(count):
        x = i * (W / count) + rng.randrange(-18, 18)
        h = int(rng.randrange(90, 170) * scale)
        w = int(h * 0.62)
        for dx in (-W, 0, W):
            cx = x + dx
            d.rectangle([cx - 4, ground_y - h * 0.45, cx + 4, ground_y], fill=color)
            d.polygon([(cx, ground_y - h), (cx - w / 2, ground_y - h * 0.28),
                       (cx + w / 2, ground_y - h * 0.28)], fill=color)
            d.polygon([(cx, ground_y - h * 0.78), (cx - w * 0.44, ground_y - h * 0.16),
                       (cx + w * 0.44, ground_y - h * 0.16)], fill=color)


def grass_far() -> Image.Image:
    base = gradient((64, 122, 200), (205, 237, 255))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.ellipse([980, 70, 1160, 250], fill=(255, 246, 210, 70))
        d.ellipse([1010, 100, 1130, 220], fill=(255, 246, 200, 150))
        for x, y, w, h in ((120, 160, 260, 90), (620, 110, 320, 100), (1120, 210, 240, 80),
                           (300, 280, 220, 70)):
            cloud(d, x, y, w, h, (255, 255, 255, 130))
        periodic_range(d, 570, 240, (104, 146, 168, 170), 2.6, 0.8)
        periodic_range(d, 620, 170, (74, 112, 120, 210), 3.4, 2.1)
        hills(d, 650, 110, (70, 116, 92, 230), 4.2, 1.3)
    return composite(base, draw).convert("RGB")


def grass_near() -> Image.Image:
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        hills(d, 660, 150, (47, 107, 62, 255), 3.1, 0.4)
        trees(d, 690, (30, 78, 48, 255), 18, 11, 1.0)
        for i in range(22):
            x = i * 66 + (i % 3) * 8
            d.ellipse([x, 656, x + 90, 706], fill=(38, 92, 55, 255))
        d.rectangle([0, 700, W, H], fill=(24, 66, 40, 255))
    return composite(base, draw)


def cave_far() -> Image.Image:
    base = gradient((16, 12, 30), (54, 38, 72))

    def draw(d: ImageDraw.ImageDraw) -> None:
        for x, y, s in ((180, 380, 46), (520, 300, 64), (900, 410, 40), (1180, 320, 52)):
            d.polygon([(x, y + s), (x + s * 0.5, y), (x + s, y + s * 0.7),
                       (x + s * 0.7, y + s * 1.8), (x + s * 0.2, y + s * 1.6)],
                      fill=(116, 86, 170, 120))
        periodic_range(d, 560, 210, (42, 32, 58, 230), 2.2, 0.6)
        periodic_range(d, 650, 140, (28, 22, 42, 255), 3.5, 1.7)
        d.rectangle([0, 690, W, H], fill=(18, 14, 28, 255))
    return composite(base, draw).convert("RGB")


def cave_near() -> Image.Image:
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        rng = random.Random(5)
        for i in range(16):
            x = i * (W / 16) + rng.randrange(-20, 20)
            w = rng.randrange(40, 90)
            h = rng.randrange(90, 220)
            for dx in (-W, 0, W):
                d.polygon([(x + dx, 0), (x + w + dx, 0), (x + w / 2 + dx, h)],
                          fill=(20, 16, 32, 245))
        for i in range(20):
            x = i * (W / 20) + rng.randrange(-14, 14)
            w = rng.randrange(30, 70)
            h = rng.randrange(50, 140)
            for dx in (-W, 0, W):
                d.polygon([(x + dx, H), (x + w + dx, H), (x + w / 2 + dx, H - h)],
                          fill=(24, 18, 38, 245))
        d.rectangle([0, 700, W, H], fill=(18, 14, 28, 255))
    return composite(base, draw)


def sky_far() -> Image.Image:
    base = gradient((72, 140, 214), (226, 246, 255))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.ellipse([1040, 80, 1200, 240], fill=(255, 250, 220, 80))
        d.ellipse([1068, 108, 1172, 212], fill=(255, 250, 220, 180))
        for x, y, w, h in ((80, 180, 300, 100), (500, 130, 260, 90), (900, 230, 340, 110),
                           (220, 330, 220, 70)):
            cloud(d, x, y, w, h, (255, 255, 255, 150))
        for x, y, w, h in ((180, 470, 360, 120), (760, 430, 300, 100), (1180, 500, 260, 90)):
            cloud(d, x, y, w, h, (255, 255, 255, 120))
        periodic_range(d, 600, 150, (140, 180, 214, 120), 2.4, 1.1)
    return composite(base, draw).convert("RGB")


def sky_near() -> Image.Image:
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        for x, y, w, h in ((-100, 560, 420, 140), (420, 610, 360, 120), (900, 570, 480, 150)):
            cloud(d, x, y, w, h, (255, 255, 255, 215))
        rng = random.Random(9)
        for i in range(6):
            x = i * 240 + rng.randrange(-40, 40)
            y = rng.randrange(360, 520)
            w = rng.randrange(90, 150)
            for dx in (-W, 0, W):
                cx = x + dx
                # 浮岛底部岩体
                d.polygon([(cx, y + 18), (cx + w, y + 18),
                           (cx + w * 0.78, y + 52), (cx + w * 0.24, y + 52)],
                          fill=(118, 150, 180, 175))
                # 草皮顶
                d.ellipse([cx, y, cx + w, y + 28], fill=(112, 176, 116, 205))
                d.ellipse([cx + 6, y + 4, cx + w - 6, y + 20], fill=(146, 204, 142, 215))
                # 岛上小树
                tx, ty = cx + w * 0.5, y + 6
                d.rectangle([tx - 2, ty - 10, tx + 2, ty + 2], fill=(72, 58, 40, 205))
                d.polygon([(tx, ty - 28), (tx - 14, ty - 2), (tx + 14, ty - 2)],
                          fill=(58, 112, 72, 215))
        for _ in range(14):
            bx, by = rng.randrange(W), rng.randrange(140, 320)
            d.line([bx, by, bx + 10, by - 6], fill=(80, 100, 130, 150), width=2)
            d.line([bx + 10, by - 6, bx + 20, by], fill=(80, 100, 130, 150), width=2)
        d.rectangle([0, 705, W, H], fill=(250, 253, 255, 240))
    return composite(base, draw)


def castle_far() -> Image.Image:
    base = gradient((18, 8, 16), (74, 26, 36))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.ellipse([1020, 90, 1180, 250], fill=(170, 60, 50, 60))
        d.ellipse([1050, 120, 1150, 220], fill=(210, 92, 70, 160))
        for x, y, w in ((120, 220, 320), (650, 170, 300), (1090, 280, 260)):
            for dx in (-W, 0, W):
                d.ellipse([x + dx, y, x + w + dx, y + 60], fill=(38, 14, 22, 180))
        for x, y, w, h in ((100, 470, 140, 200), (360, 430, 170, 240), (760, 480, 150, 190),
                           (1120, 440, 180, 230)):
            for dx in (-W, 0, W):
                cx = x + dx
                # 塔身
                d.rectangle([cx, y, cx + w, y + h], fill=(42, 16, 24, 230))
                # 城垛
                for i in range(5):
                    bx = cx + i * w / 5
                    d.rectangle([bx, y - 26, bx + w * 0.12, y], fill=(42, 16, 24, 230))
                # 尖顶
                d.polygon([(cx + w * 0.22, y - 26), (cx + w * 0.5, y - 120),
                           (cx + w * 0.78, y - 26)], fill=(42, 16, 24, 230))
                # 窗
                for wy in range(int(y) + 40, int(y + h) - 20, 60):
                    d.rectangle([cx + w / 2 - 8, wy, cx + w / 2 + 8, wy + 20],
                                fill=(160, 70, 40, 150))
        d.rectangle([0, 690, W, H], fill=(96, 28, 20, 255))
        d.rectangle([0, 700, W, H], fill=(160, 54, 24, 255))
    return composite(base, draw).convert("RGB")


def castle_near() -> Image.Image:
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.rectangle([0, 660, W, H], fill=(16, 8, 14, 255))
        for i in range(18):
            x = i * 80
            d.rectangle([x, 620, x + 50, 665], fill=(16, 8, 14, 255))
        for x in (180, 520, 900, 1240):
            for dx in (-W, 0, W):
                d.rectangle([x + dx, 0, x + 8 + dx, 260], fill=(24, 12, 20, 230))
                d.ellipse([x - 16 + dx, 250, x + 24 + dx, 290], fill=(24, 12, 20, 230))
        for x in (340, 700, 1080):
            for dx in (-W, 0, W):
                d.rectangle([x + dx, 560, x + 18 + dx, 660], fill=(30, 14, 20, 245))
                d.polygon([(x - 10 + dx, 560), (x + 9 + dx, 520), (x + 28 + dx, 560)],
                          fill=(30, 14, 20, 245))
    return composite(base, draw)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = {
        "grass": (grass_far(), grass_near()),
        "cave": (cave_far(), cave_near()),
        "sky": (sky_far(), sky_near()),
        "castle": (castle_far(), castle_near()),
    }
    for theme, (far, near) in pairs.items():
        far.save(OUT / f"bg_{theme}_far.png")
        near.save(OUT / f"bg_{theme}_near.png")
        print(f"wrote bg_{theme}_far.png / bg_{theme}_near.png")


if __name__ == "__main__":
    main()

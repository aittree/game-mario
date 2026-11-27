"""生成 4 套主题的远景/近景背景，像素风。

先在 350×180 逻辑像素画布上以实色块绘制，再用最近邻放大 4 倍到 1400×720，
像素块统一为 4×4。输出：
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

W, H = 1400, 720          # 输出尺寸
BW, BH = W // 4, H // 4   # 逻辑像素画布 350×180
OUT = Path(__file__).resolve().parents[1] / "assets" / "images"


def bands(top: tuple[int, int, int], bottom: tuple[int, int, int], n: int = 7) -> Image.Image:
    """天空用有限色带代替逐像素渐变，保留硬边台阶感。"""
    img = Image.new("RGB", (BW, BH))
    d = ImageDraw.Draw(img)
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        color = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
        y0 = i * BH // n
        y1 = (i + 1) * BH // n - 1
        d.rectangle([0, y0, BW - 1, y1], fill=color)
    return img


def layer(base: Image.Image, draw_fn: Callable[[ImageDraw.ImageDraw], None]) -> Image.Image:
    overlay = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(overlay, "RGBA"))
    return Image.alpha_composite(base.convert("RGBA"), overlay)


def cloud(d: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float,
          color: tuple[int, int, int, int]) -> None:
    """块状云：三个矩形叠出轮廓，不做柔边。"""
    for dx in (-BW, 0, BW):
        cx, yy, ww, hh = int(x + dx), int(y), int(w), int(h)
        d.rectangle([cx, yy + hh // 3, cx + ww, yy + hh], fill=color)
        d.rectangle([cx + ww // 5, yy, cx + ww * 3 // 5, yy + hh // 2], fill=color)
        d.rectangle([cx + ww // 2, yy + hh // 5, cx + ww, yy + hh * 2 // 3], fill=color)


def periodic_range(d: ImageDraw.ImageDraw, base_y: float, height: float,
                   color: tuple[int, int, int, int], freq: float, phase: float,
                   step: int = 1) -> None:
    """周期正弦山丘；逐逻辑像素取点，放大后自然形成 4px 台阶。"""
    for dx in (-BW, 0, BW):
        points: list[tuple[int, int]] = []
        for x in range(0, BW + step, step):
            wave = 0.5 + 0.5 * math.sin(2 * math.pi * freq * x / BW + phase)
            yy = base_y - height * (0.35 + 0.65 * wave)
            points.append((x + dx, int(yy)))
        points += [(BW + dx, BH), (dx, BH)]
        d.polygon(points, fill=color)


def hills(d: ImageDraw.ImageDraw, base_y: float, height: float,
          color: tuple[int, int, int, int], freq: float, phase: float) -> None:
    periodic_range(d, base_y, height, color, freq, phase, step=1)


def trees(d: ImageDraw.ImageDraw, ground_y: int, color: tuple[int, int, int, int],
          count: int, seed: int, scale: float = 1.0) -> None:
    rng = random.Random(seed)
    for i in range(count):
        x = int(i * (BW / count) + rng.randrange(-5, 5))
        h = int(rng.randrange(22, 42) * scale)
        w = int(h * 0.62)
        for dx in (-BW, 0, BW):
            cx = x + dx
            d.rectangle([cx - 1, int(ground_y - h * 0.45), cx + 1, int(ground_y)], fill=color)
            d.polygon([(cx, int(ground_y - h)),
                       (cx - w // 2, int(ground_y - h * 0.28)),
                       (cx + w // 2, int(ground_y - h * 0.28))], fill=color)
            d.polygon([(cx, int(ground_y - h * 0.78)),
                       (cx - int(w * 0.44), int(ground_y - h * 0.16)),
                       (cx + int(w * 0.44), int(ground_y - h * 0.16))], fill=color)


def grass_far() -> Image.Image:
    base = bands((64, 122, 200), (205, 237, 255))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.ellipse([248, 20, 292, 64], fill=(255, 246, 210, 255))
        d.ellipse([256, 28, 284, 56], fill=(255, 252, 232, 255))
        for x, y, w, h in ((30, 40, 65, 22), (155, 28, 80, 25), (280, 52, 60, 20),
                           (75, 70, 55, 17)):
            cloud(d, x, y, w, h, (255, 255, 255, 255))
        periodic_range(d, 142, 60, (104, 146, 168, 255), 2.6, 0.8)
        periodic_range(d, 155, 42, (74, 112, 120, 255), 3.4, 2.1)
        hills(d, 162, 27, (70, 116, 92, 255), 4.2, 1.3)
    return layer(base, draw).convert("RGB")


def grass_near() -> Image.Image:
    base = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        hills(d, 165, 37, (47, 107, 62, 255), 3.1, 0.4)
        trees(d, 172, (30, 78, 48, 255), 18, 11, 1.0)
        for i in range(22):
            x = i * 16 + (i % 3) * 2
            d.ellipse([x, 164, x + 22, 176], fill=(38, 92, 55, 255))
        d.rectangle([0, 175, BW - 1, BH - 1], fill=(24, 66, 40, 255))
    return layer(base, draw)


def cave_far() -> Image.Image:
    base = bands((16, 12, 30), (54, 38, 72))

    def draw(d: ImageDraw.ImageDraw) -> None:
        for x, y, s in ((45, 95, 11), (130, 75, 16), (225, 102, 10), (295, 80, 13)):
            d.polygon([(x, y + s), (x + s // 2, y), (x + s, y + int(s * 0.7)),
                       (x + int(s * 0.7), y + int(s * 1.8)),
                       (x + int(s * 0.2), y + int(s * 1.6))],
                      fill=(116, 86, 170, 255))
        periodic_range(d, 140, 52, (42, 32, 58, 255), 2.2, 0.6)
        periodic_range(d, 162, 35, (28, 22, 42, 255), 3.5, 1.7)
        d.rectangle([0, 172, BW - 1, BH - 1], fill=(18, 14, 28, 255))
    return layer(base, draw).convert("RGB")


def cave_near() -> Image.Image:
    base = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        rng = random.Random(5)
        for i in range(16):
            x = int(i * (BW / 16) + rng.randrange(-5, 5))
            w = rng.randrange(10, 22)
            h = rng.randrange(22, 55)
            for dx in (-BW, 0, BW):
                d.polygon([(x + dx, 0), (x + w + dx, 0), (x + w // 2 + dx, h)],
                          fill=(20, 16, 32, 255))
        for i in range(20):
            x = int(i * (BW / 20) + rng.randrange(-4, 4))
            w = rng.randrange(7, 17)
            h = rng.randrange(12, 35)
            for dx in (-BW, 0, BW):
                d.polygon([(x + dx, BH), (x + w + dx, BH), (x + w // 2 + dx, BH - h)],
                          fill=(24, 18, 38, 255))
        d.rectangle([0, 175, BW - 1, BH - 1], fill=(18, 14, 28, 255))
    return layer(base, draw)


def sky_far() -> Image.Image:
    base = bands((72, 140, 214), (226, 246, 255))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.ellipse([260, 20, 300, 60], fill=(255, 250, 220, 255))
        d.ellipse([267, 27, 293, 53], fill=(255, 253, 236, 255))
        for x, y, w, h in ((20, 45, 75, 25), (125, 32, 65, 22), (225, 57, 85, 27),
                           (55, 82, 55, 17)):
            cloud(d, x, y, w, h, (255, 255, 255, 255))
        for x, y, w, h in ((45, 117, 90, 30), (190, 107, 75, 25), (295, 125, 65, 22)):
            cloud(d, x, y, w, h, (255, 255, 255, 255))
        periodic_range(d, 150, 37, (140, 180, 214, 255), 2.4, 1.1)
    return layer(base, draw).convert("RGB")


def sky_near() -> Image.Image:
    base = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        for x, y, w, h in ((-25, 140, 105, 35), (105, 152, 90, 30), (225, 142, 120, 37)):
            cloud(d, x, y, w, h, (255, 255, 255, 255))
        rng = random.Random(9)
        for i in range(6):
            x = i * 60 + rng.randrange(-10, 10)
            y = rng.randrange(90, 130)
            w = rng.randrange(22, 37)
            for dx in (-BW, 0, BW):
                cx = x + dx
                d.polygon([(cx, y + 5), (cx + w, y + 5),
                           (cx + int(w * 0.78), y + 13), (cx + int(w * 0.24), y + 13)],
                          fill=(118, 150, 180, 255))
                d.ellipse([cx, y, cx + w, y + 7], fill=(112, 176, 116, 255))
                d.ellipse([cx + 2, y + 1, cx + w - 2, y + 5], fill=(146, 204, 142, 255))
                tx, ty = cx + w // 2, y + 2
                d.rectangle([tx - 1, ty - 3, tx + 1, ty], fill=(72, 58, 40, 255))
                d.polygon([(tx, ty - 7), (tx - 4, ty - 1), (tx + 4, ty - 1)],
                          fill=(58, 112, 72, 255))
        for _ in range(14):
            bx, by = rng.randrange(BW), rng.randrange(35, 80)
            d.line([bx, by, bx + 3, by - 2], fill=(80, 100, 130, 255))
            d.line([bx + 3, by - 2, bx + 6, by], fill=(80, 100, 130, 255))
        d.rectangle([0, 176, BW - 1, BH - 1], fill=(250, 253, 255, 255))
    return layer(base, draw)


def castle_far() -> Image.Image:
    base = bands((18, 8, 16), (74, 26, 36))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.ellipse([255, 22, 295, 62], fill=(170, 60, 50, 255))
        d.ellipse([262, 29, 288, 55], fill=(210, 92, 70, 255))
        for x, y, w in ((30, 55, 80), (162, 42, 75), (272, 70, 65)):
            for dx in (-BW, 0, BW):
                d.ellipse([x + dx, y, x + w + dx, y + 15], fill=(38, 14, 22, 255))
        for x, y, w, h in ((25, 117, 35, 50), (90, 107, 42, 60), (190, 120, 37, 47),
                           (280, 110, 45, 57)):
            for dx in (-BW, 0, BW):
                cx = int(x + dx)
                d.rectangle([cx, y, cx + w, y + h], fill=(42, 16, 24, 255))
                for i in range(5):
                    bx = cx + i * w // 5
                    d.rectangle([bx, y - 6, bx + max(1, w // 12), y], fill=(42, 16, 24, 255))
                d.polygon([(cx + w // 5, y - 6), (cx + w // 2, y - 30),
                           (cx + w * 4 // 5, y - 6)], fill=(42, 16, 24, 255))
                for wy in range(y + 10, y + h - 5, 15):
                    d.rectangle([cx + w // 2 - 2, wy, cx + w // 2 + 2, wy + 5],
                                fill=(160, 70, 40, 255))
        d.rectangle([0, 172, BW - 1, BH - 1], fill=(96, 28, 20, 255))
        d.rectangle([0, 175, BW - 1, BH - 1], fill=(160, 54, 24, 255))
    return layer(base, draw).convert("RGB")


def castle_near() -> Image.Image:
    base = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))

    def draw(d: ImageDraw.ImageDraw) -> None:
        d.rectangle([0, 165, BW - 1, BH - 1], fill=(16, 8, 14, 255))
        for i in range(18):
            x = i * 20
            d.rectangle([x, 155, x + 12, 166], fill=(16, 8, 14, 255))
        for x in (45, 130, 225, 310):
            for dx in (-BW, 0, BW):
                d.rectangle([x + dx, 0, x + 3 + dx, 65], fill=(24, 12, 20, 255))
                d.ellipse([x - 4 + dx, 62, x + 7 + dx, 73], fill=(24, 12, 20, 255))
        for x in (85, 175, 270):
            for dx in (-BW, 0, BW):
                d.rectangle([x + dx, 140, x + 5 + dx, 165], fill=(30, 14, 20, 255))
                d.polygon([(x - 2 + dx, 140), (x + 2 + dx, 130), (x + 7 + dx, 140)],
                          fill=(30, 14, 20, 255))
    return layer(base, draw)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = {
        "grass": (grass_far(), grass_near()),
        "cave": (cave_far(), cave_near()),
        "sky": (sky_far(), sky_near()),
        "castle": (castle_far(), castle_near()),
    }
    for theme, (far, near) in pairs.items():
        far.resize((W, H), Image.Resampling.NEAREST).convert("RGB").save(OUT / f"bg_{theme}_far.png")
        near.resize((W, H), Image.Resampling.NEAREST).save(OUT / f"bg_{theme}_near.png")
        print(f"wrote bg_{theme}_far.png / bg_{theme}_near.png")


if __name__ == "__main__":
    main()

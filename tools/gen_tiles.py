"""生成 4 套 16 帧地形瓦片集（320×80）。

索引顺序见 docs/08 §2.2，四套主题只换配色与材质，形状与索引完全一致。
"""

from __future__ import annotations

import random
from pathlib import Path
from zlib import crc32

from PIL import Image, ImageDraw

CELL = 40
COLS, ROWS = 8, 2
OUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "images"

# 与 docs/08 §2.6 的主题主色保持一致
TILE_COLORS = {
    "grass": {
        "dirt": "#9A5B34", "dirt_dark": "#6E3A1E", "dirt_light": "#B87A4A",
        "top": "#5DBB46", "top_dark": "#3E8A30", "top_light": "#86E06A",
        "brick": "#C86B3C", "brick_dark": "#8C3F20", "mortar": "#F0D2A8",
        "metal": "#7C8DA6", "metal_dark": "#4F5E74", "metal_light": "#B9C7DA",
        "gold": "#F2C230", "gold_dark": "#A77A10", "gold_light": "#FFE27A",
        "used": "#9A7424", "used_dark": "#6A4D12",
        "pipe": "#3FA34D", "pipe_dark": "#1F6B31", "pipe_light": "#7BDC78",
        "wood": "#B07A3A", "wood_dark": "#6E461E", "wood_light": "#D9A45A",
        "spike": "#DCE6F2", "spike_dark": "#8494AA",
        "coin": "#FFD54A", "coin_dark": "#B8860B", "coin_light": "#FFF3B0",
    },
    "cave": {
        "dirt": "#3B3550", "dirt_dark": "#241F36", "dirt_light": "#5A5172",
        "top": "#6B5A8A", "top_dark": "#43375C", "top_light": "#907EB4",
        "brick": "#7A4E6B", "brick_dark": "#4A2A40", "mortar": "#B98FA5",
        "metal": "#6A7288", "metal_dark": "#3C4254", "metal_light": "#A2AAC0",
        "gold": "#C9A227", "gold_dark": "#7E6210", "gold_light": "#E8C860",
        "used": "#6E5A24", "used_dark": "#463712",
        "pipe": "#2E7D5B", "pipe_dark": "#164A34", "pipe_light": "#5DB88A",
        "wood": "#6B4A5A", "wood_dark": "#3E2836", "wood_light": "#9A7488",
        "spike": "#C8D2E4", "spike_dark": "#6E7890",
        "coin": "#FFCC33", "coin_dark": "#A87800", "coin_light": "#FFE89A",
    },
    "sky": {
        "dirt": "#C9DDF2", "dirt_dark": "#94B4D6", "dirt_light": "#EAF5FF",
        "top": "#FFFFFF", "top_dark": "#C7E2FA", "top_light": "#FFFFFF",
        "brick": "#D8B48A", "brick_dark": "#A47A50", "mortar": "#FFF1DA",
        "metal": "#9FB3C8", "metal_dark": "#667E96", "metal_light": "#D8E8F6",
        "gold": "#F2C230", "gold_dark": "#A77A10", "gold_light": "#FFE27A",
        "used": "#9A7424", "used_dark": "#6A4D12",
        "pipe": "#4FB3D9", "pipe_dark": "#26779A", "pipe_light": "#9BE4F6",
        "wood": "#E8D7B0", "wood_dark": "#A98A5A", "wood_light": "#FFF4D8",
        "spike": "#F2F8FF", "spike_dark": "#9CB6D2",
        "coin": "#FFD54A", "coin_dark": "#B8860B", "coin_light": "#FFF3B0",
    },
    "castle": {
        "dirt": "#4A2230", "dirt_dark": "#2A101A", "dirt_light": "#6E3446",
        "top": "#8B3A48", "top_dark": "#5A202C", "top_light": "#B45A64",
        "brick": "#6B2A38", "brick_dark": "#3E1620", "mortar": "#B07A82",
        "metal": "#5C5A66", "metal_dark": "#35323C", "metal_light": "#8E8A98",
        "gold": "#E0A526", "gold_dark": "#8E650C", "gold_light": "#FFD46A",
        "used": "#7A5A1A", "used_dark": "#4E3810",
        "pipe": "#556B2F", "pipe_dark": "#30401A", "pipe_light": "#8BA25A",
        "wood": "#7A4A2A", "wood_dark": "#462614", "wood_light": "#A97448",
        "spike": "#E8E8F0", "spike_dark": "#8A8A9A",
        "coin": "#FFC83D", "coin_dark": "#A87800", "coin_light": "#FFE89A",
    },
}

QUESTION_BITS = (
    (0, 1, 1, 1, 0),
    (1, 0, 0, 0, 1),
    (0, 0, 0, 0, 1),
    (0, 0, 1, 1, 0),
    (0, 0, 1, 0, 0),
    (0, 0, 0, 0, 0),
    (0, 0, 1, 0, 0),
)


def _cell() -> Image.Image:
    return Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))


def _dirt(d: ImageDraw.ImageDraw, p: dict[str, str], seed: int) -> None:
    d.rectangle([0, 0, 39, 39], fill=p["dirt"])
    d.rectangle([0, 0, 39, 5], fill=p["top"])
    d.rectangle([0, 6, 39, 6], fill=p["top_dark"])
    d.line([0, 0, 0, 39], fill=p["dirt_light"])
    d.line([39, 0, 39, 39], fill=p["dirt_dark"])
    rng = random.Random(seed)
    for _ in range(18):
        x, y = rng.randrange(2, 38), rng.randrange(9, 38)
        d.point((x, y), fill=p["dirt_dark"] if rng.random() < 0.6 else p["dirt_light"])
    for x in range(1, 40, 5):
        d.line([x, 0, x + 1, 3], fill=p["top_light"])


def _brick(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    d.rectangle([0, 0, 39, 39], fill=p["mortar"])
    for row, y in enumerate((2, 21)):
        offset = 0 if row == 0 else 10
        for x in range(-20 + offset, 40, 20):
            d.rectangle([x + 1, y, x + 18, y + 16], fill=p["brick"])
            d.line([x + 1, y, x + 18, y], fill=p["brick_dark"])
            d.line([x + 1, y + 16, x + 18, y + 16], fill=p["brick_dark"])
    d.rectangle([0, 0, 39, 39], outline=p["brick_dark"])


def _hard(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    d.rectangle([0, 0, 39, 39], fill=p["metal"])
    d.rectangle([0, 0, 39, 39], outline=p["metal_dark"], width=2)
    d.line([2, 2, 37, 2], fill=p["metal_light"], width=2)
    d.line([2, 2, 2, 37], fill=p["metal_light"], width=2)
    d.line([2, 37, 37, 37], fill=p["metal_dark"], width=2)
    d.line([37, 2, 37, 37], fill=p["metal_dark"], width=2)
    for cx, cy in ((7, 7), (32, 7), (7, 32), (32, 32)):
        d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=p["metal_light"], outline=p["metal_dark"])


def _question(d: ImageDraw.ImageDraw, p: dict[str, str], frame: int) -> None:
    d.rectangle([1, 1, 38, 38], fill=p["gold"], outline=p["gold_dark"], width=2)
    d.rectangle([4, 4, 35, 35], outline=p["gold_light"], width=1)
    if frame == 1:
        d.line([5, 5, 20, 5], fill=p["gold_light"], width=2)
    scale = 4
    w = len(QUESTION_BITS[0]) * scale
    h = len(QUESTION_BITS) * scale
    ox, oy = (CELL - w) // 2, (CELL - h) // 2 + 1
    for gy, row in enumerate(QUESTION_BITS):
        for gx, bit in enumerate(row):
            if bit:
                d.rectangle([ox + gx * scale, oy + gy * scale,
                             ox + gx * scale + scale - 1, oy + gy * scale + scale - 1],
                            fill="#FFFFFF")
    for cx, cy in ((5, 5), (34, 5), (5, 34), (34, 34)):
        d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1], fill=p["gold_dark"])


def _used(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    d.rectangle([1, 1, 38, 38], fill=p["used"], outline=p["used_dark"], width=2)
    d.rectangle([4, 4, 35, 35], outline=p["used_dark"], width=1)
    for cx, cy in ((5, 5), (34, 5), (5, 34), (34, 34)):
        d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1], fill=p["used_dark"])


def _pipe_body(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    d.rectangle([0, 0, 39, 39], fill=p["pipe"])
    for x in (5, 15, 25, 35):
        d.line([x, 0, x, 39], fill=p["pipe_light"])
    d.line([0, 0, 0, 39], fill=p["pipe_dark"], width=2)
    d.line([39, 0, 39, 39], fill=p["pipe_dark"], width=2)


def _pipe_lip(d: ImageDraw.ImageDraw, p: dict[str, str], side: str) -> None:
    if side == "left":
        d.rectangle([1, 0, 39, 13], fill=p["pipe_light"], outline=p["pipe_dark"], width=2)
        d.rectangle([1, 14, 39, 39], fill=p["pipe"])
        d.line([5, 16, 5, 39], fill=p["pipe_light"])
        d.line([15, 16, 15, 39], fill=p["pipe_light"])
        d.line([1, 14, 39, 14], fill=p["pipe_dark"], width=2)
    elif side == "right":
        d.rectangle([1, 0, 39, 13], fill=p["pipe_light"], outline=p["pipe_dark"], width=2)
        d.rectangle([0, 14, 38, 39], fill=p["pipe"])
        d.line([24, 16, 24, 39], fill=p["pipe_light"])
        d.line([34, 16, 34, 39], fill=p["pipe_light"])
        d.line([0, 14, 38, 14], fill=p["pipe_dark"], width=2)
    else:
        d.rectangle([1, 0, 38, 13], fill=p["pipe_light"], outline=p["pipe_dark"], width=2)
        d.rectangle([4, 14, 35, 39], fill=p["pipe"])
        d.line([9, 16, 9, 39], fill=p["pipe_light"])
        d.line([30, 16, 30, 39], fill=p["pipe_light"])


def _semisolid(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    d.rectangle([0, 0, 39, 8], fill=p["wood"], outline=p["wood_dark"])
    d.line([1, 1, 38, 1], fill=p["wood_light"], width=2)
    for x in range(3, 40, 8):
        d.line([x, 9, x, 18], fill=p["wood_dark"])


def _spike(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    for base in (0, 14, 28):
        pts = [(base, 39), (base + 6, 10), (base + 12, 39)]
        d.polygon(pts, fill=p["spike"], outline=p["spike_dark"])
        d.line([base + 6, 12, base + 6, 36], fill=p["spike_dark"])


def _coin(d: ImageDraw.ImageDraw, p: dict[str, str], frame: int) -> None:
    widths = (26, 18, 6, 18)
    w = widths[frame]
    x0 = (CELL - w) // 2
    d.ellipse([x0, 5, x0 + w - 1, 35], fill=p["coin"], outline=p["coin_dark"], width=2)
    if w >= 18:
        d.ellipse([x0 + 3, 9, x0 + w - 4, 31], outline=p["coin_light"], width=2)


def draw_frame(index: int, p: dict[str, str], seed: int) -> Image.Image:
    img = _cell()
    d = ImageDraw.Draw(img)
    if index == 0:
        _dirt(d, p, seed)
    elif index == 1:
        _brick(d, p)
    elif index == 2:
        _hard(d, p)
    elif index in (3, 4):
        _question(d, p, index - 3)
    elif index == 5:
        _used(d, p)
    elif index == 6:
        _pipe_body(d, p)
    elif index == 7:
        _pipe_lip(d, p, "left")
    elif index == 8:
        _pipe_lip(d, p, "right")
    elif index == 9:
        _pipe_lip(d, p, "single")
    elif index == 10:
        _semisolid(d, p)
    elif index == 11:
        _spike(d, p)
    elif index >= 12:
        _coin(d, p, index - 12)
    return img


def build_sheet(theme: str, palette: dict[str, str]) -> Image.Image:
    sheet = Image.new("RGBA", (CELL * COLS, CELL * ROWS), (0, 0, 0, 0))
    for i in range(COLS * ROWS):
        # 用 crc32 而非内置 hash()：后者受 PYTHONHASHSEED 影响，跨进程不可复现。
        sheet.paste(draw_frame(i, palette, seed=crc32(theme.encode()) + i), ((i % COLS) * CELL, (i // COLS) * CELL))
    return sheet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme, palette in TILE_COLORS.items():
        path = OUT_DIR / f"tiles_{theme}.png"
        build_sheet(theme, palette).save(path)
        print(f"wrote {path.relative_to(OUT_DIR.parents[1])}")


if __name__ == "__main__":
    main()

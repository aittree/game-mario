"""生成 4 套 16 帧地形瓦片集（320×80），像素风。

每帧先在 10×10 逻辑像素画布上绘制，再用最近邻放大 4 倍到 40×40，
像素块统一为 4×4。索引顺序见 docs/08 §2.2，四套主题只换配色与材质。
"""

from __future__ import annotations

import random
from pathlib import Path
from zlib import crc32

from PIL import Image, ImageDraw

CELL = 40
BASE = 10                     # 逻辑像素边长
S = CELL // BASE              # 最近邻放大倍数 = 4
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
    return Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))


def _dirt(d: ImageDraw.ImageDraw, p: dict[str, str], seed: int) -> None:
    """地面：顶部两条草边 + 下部泥土与颗粒点缀。"""
    d.rectangle([0, 0, BASE - 1, BASE - 1], fill=p["dirt"])
    d.rectangle([0, 0, BASE - 1, 1], fill=p["top"])
    d.rectangle([0, 2, BASE - 1, 2], fill=p["top_dark"])
    d.line([0, 0, 0, BASE - 1], fill=p["dirt_light"])
    d.line([BASE - 1, 0, BASE - 1, BASE - 1], fill=p["dirt_dark"])
    rng = random.Random(seed)
    for _ in range(6):
        x, y = rng.randrange(1, BASE - 1), rng.randrange(4, BASE - 1)
        d.point((x, y), fill=p["dirt_dark"] if rng.random() < 0.6 else p["dirt_light"])
    for x in (1, 4, 7):
        d.point((x, 0), fill=p["top_light"])


def _brick(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    """砖块：灰缝打底 + 两行错缝砖，砖宽 4 逻辑像素。"""
    d.rectangle([0, 0, BASE - 1, BASE - 1], fill=p["mortar"])
    for y0, y1, start in ((0, 3, 0), (5, 8, -2)):
        x = start
        while x < BASE:
            x0, x1 = max(0, x), min(BASE - 1, x + 3)
            if x1 >= x0:
                d.rectangle([x0, y0, x1, y1], fill=p["brick"])
                d.line([x0, y0, x1, y0], fill=p["brick_dark"])
                d.line([x0, y1, x1, y1], fill=p["brick_dark"])
            x += 5


def _hard(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    """硬块：实心金属 + 1 像素内斜面 + 四角铆钉。"""
    d.rectangle([0, 0, BASE - 1, BASE - 1], fill=p["metal"])
    d.rectangle([0, 0, BASE - 1, BASE - 1], outline=p["metal_dark"])
    d.line([1, 1, BASE - 2, 1], fill=p["metal_light"])
    d.line([1, 1, 1, BASE - 2], fill=p["metal_light"])
    d.line([1, BASE - 2, BASE - 2, BASE - 2], fill=p["metal_dark"])
    d.line([BASE - 2, 1, BASE - 2, BASE - 2], fill=p["metal_dark"])
    for cx, cy in ((2, 2), (7, 2), (2, 7), (7, 7)):
        d.point((cx, cy), fill=p["metal_light"])


def _question(d: ImageDraw.ImageDraw, p: dict[str, str], frame: int) -> None:
    """问号块：金底 + 内高光 + 1 像素问号点阵。"""
    d.rectangle([0, 0, BASE - 1, BASE - 1], fill=p["gold"])
    d.rectangle([0, 0, BASE - 1, BASE - 1], outline=p["gold_dark"])
    d.rectangle([1, 1, BASE - 2, BASE - 2], outline=p["gold_light"])
    if frame == 1:
        d.line([2, 2, BASE - 3, 2], fill=p["gold_light"])
    w, h = len(QUESTION_BITS[0]), len(QUESTION_BITS)
    ox, oy = (BASE - w) // 2, (BASE - h) // 2 + 1
    for gy, row in enumerate(QUESTION_BITS):
        for gx, bit in enumerate(row):
            if bit:
                d.point((ox + gx, oy + gy), fill="#FFFFFF")


def _used(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    """已用块：暗金双层边框 + 四角铆点。"""
    d.rectangle([0, 0, BASE - 1, BASE - 1], fill=p["used"])
    d.rectangle([0, 0, BASE - 1, BASE - 1], outline=p["used_dark"])
    d.rectangle([1, 1, BASE - 2, BASE - 2], outline=p["used_dark"])
    for cx, cy in ((1, 1), (BASE - 2, 1), (1, BASE - 2), (BASE - 2, BASE - 2)):
        d.point((cx, cy), fill=p["used_dark"])


def _pipe_body(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    """管身：竖纹 + 两侧暗边。"""
    d.rectangle([0, 0, BASE - 1, BASE - 1], fill=p["pipe"])
    for x in (1, 3, 6, 8):
        d.line([x, 0, x, BASE - 1], fill=p["pipe_light"])
    d.line([0, 0, 0, BASE - 1], fill=p["pipe_dark"])
    d.line([BASE - 1, 0, BASE - 1, BASE - 1], fill=p["pipe_dark"])


def _pipe_lip(d: ImageDraw.ImageDraw, p: dict[str, str], side: str) -> None:
    """管口：顶部宽唇 + 下方管身；左/右半靠条纹位置区分。"""
    if side == "single":
        d.rectangle([1, 0, BASE - 2, 3], fill=p["pipe_light"], outline=p["pipe_dark"])
        d.rectangle([1, 4, BASE - 2, BASE - 1], fill=p["pipe"])
        for x in (3, 6):
            d.line([x, 4, x, BASE - 1], fill=p["pipe_light"])
        d.line([1, 4, BASE - 2, 4], fill=p["pipe_dark"])
        return
    d.rectangle([0, 0, BASE - 1, 3], fill=p["pipe_light"], outline=p["pipe_dark"])
    d.rectangle([0, 4, BASE - 1, BASE - 1], fill=p["pipe"])
    stripes = (1, 3) if side == "left" else (6, 8)
    for x in stripes:
        d.line([x, 4, x, BASE - 1], fill=p["pipe_light"])
    d.line([0, 4, BASE - 1, 4], fill=p["pipe_dark"])


def _semisolid(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    """单向平台：顶部实木板 + 下方短木钉，其余透明。"""
    d.rectangle([0, 0, BASE - 1, 3], fill=p["wood"], outline=p["wood_dark"])
    d.line([1, 0, BASE - 2, 0], fill=p["wood_light"])
    for x in (2, 5, 8):
        d.line([x, 4, x, 5], fill=p["wood_dark"])


def _spike(d: ImageDraw.ImageDraw, p: dict[str, str]) -> None:
    """尖刺：3 个三角，底边贴格底，高 7 逻辑像素（28 px）。"""
    for base in (0, 3, 6):
        d.polygon([(base, BASE - 1), (base + 1, 2), (base + 2, BASE - 1)],
                  fill=p["spike"], outline=p["spike_dark"])


def _coin(d: ImageDraw.ImageDraw, p: dict[str, str], frame: int) -> None:
    """金币：4 帧旋转，宽度 6/4/2/4 逻辑像素。"""
    widths = (6, 4, 2, 4)
    w = widths[frame]
    x0 = (BASE - w) // 2
    d.ellipse([x0, 1, x0 + w - 1, BASE - 2], fill=p["coin"], outline=p["coin_dark"])
    if w >= 4:
        d.ellipse([x0 + 1, 2, x0 + w - 2, BASE - 3], outline=p["coin_light"])


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
    return img.resize((CELL, CELL), Image.Resampling.NEAREST)


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

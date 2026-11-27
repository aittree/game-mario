"""生成玩家/敌人/道具精灵表、标题 Logo 与图标。

布局见 docs/08 §2.3～§2.5、§2.7：
- player_small.png  288×192，6×4 格，48×48
- player_big.png    288×288，6×4 格，48×72
- enemies.png       192×240，4×5 格，48×48
- items.png         192×144，4×3 格，48×48
- logo.png          512×512 透明底
- icon.png          256×256
- icon.ico          16/24/32/48/64/128/256
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "assets" / "images"

RED = "#E63B2E"
RED_D = "#A6241C"
RED_L = "#FF6A58"
BLUE = "#2E5BFF"
BLUE_D = "#1B3BB8"
BLUE_L = "#6E8CFF"
SKIN = "#F6C89A"
SKIN_D = "#C98A5A"
SKIN_L = "#FFE3C4"
HAIR = "#5A3A22"
DARK = "#2A1A18"
WHITE = "#FFF7E8"
YELLOW = "#FFD54A"
GREEN = "#3FA34D"
GREEN_D = "#1F6B31"
GREEN_L = "#7BDC78"
ORANGE = "#F08A24"
PINK = "#E85D8A"
TEAL = "#2E9E9E"
PURPLE = "#6B3FA0"
BROWN = "#8B5A2B"
BROWN_D = "#5A3A1A"
SILVER = "#DCE6F2"


class Grid:
    """以逻辑像素格绘制，自动放大为精灵帧。"""

    def __init__(self, gw: int, gh: int, scale: int = 3):
        self.s = scale
        self.img = Image.new("RGBA", (gw * scale, gh * scale), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        if w <= 0 or h <= 0:
            return
        self.d.rectangle([x * self.s, y * self.s, (x + w) * self.s - 1, (y + h) * self.s - 1], fill=color)

    def ellipse(self, x: int, y: int, w: int, h: int, color: str) -> None:
        self.d.ellipse([x * self.s, y * self.s, (x + w) * self.s - 1, (y + h) * self.s - 1], fill=color)

    def poly(self, points: list[tuple[int, int]], color: str) -> None:
        self.d.polygon([(px * self.s, py * self.s) for px, py in points], fill=color)


def _small_legs(g: Grid, poses: dict) -> None:
    for x, y, w, h in poses["legs"]:
        g.rect(x, y, w, h, BLUE)
        g.rect(x, y + h - 1, w, 1, BLUE_D)
    for x, y, w in poses["shoes"]:
        g.rect(x, y, w, 2, DARK)
        g.rect(x + 1, y, w - 2, 1, "#4A3230")


def draw_small_frame(name: str) -> Image.Image:
    g = Grid(16, 16)
    lean = -1 if name == "skid" else 0
    flash = SKIN_L if name == "hurt2" else SKIN
    cap = RED_L if name == "hurt2" else RED
    legs = [(4, 12, 3, 3), (9, 12, 3, 3)]
    shoes = [(3, 14, 4), (9, 14, 4)]
    arms = [(2, 8, 2, 3), (12, 8, 2, 3)]
    dy = 0

    if name in ("run1", "run3"):
        legs = [(3, 12, 3, 3), (10, 12, 3, 3)] if name == "run1" else [(3, 12, 3, 3), (10, 12, 3, 3)]
        shoes = [(2, 14, 4), (10, 14, 4)]
        arms = [(2, 9, 2, 3), (12, 9, 2, 3)] if name == "run1" else [(2, 7, 2, 3), (12, 7, 2, 3)]
    elif name in ("run2", "run4"):
        legs = [(5, 12, 3, 3), (8, 12, 3, 3)]
        shoes = [(4, 14, 4), (8, 14, 4)]
        arms = [(2, 8, 2, 2), (12, 8, 2, 2)]
    elif name == "jump":
        dy = -1
        legs = [(4, 11, 3, 3), (9, 11, 3, 3)]
        shoes = [(3, 13, 4), (9, 13, 4)]
        arms = [(1, 6, 2, 3), (13, 6, 2, 3)]
    elif name == "fall":
        legs = [(3, 12, 3, 3), (10, 12, 3, 3)]
        shoes = [(2, 14, 4), (10, 14, 4)]
        arms = [(0, 8, 2, 2), (14, 8, 2, 2)]
    elif name == "skid":
        arms = [(1, 7, 2, 3), (13, 9, 2, 2)]
    elif name in ("hurt1", "hurt2"):
        dy = -1 if name == "hurt1" else 0
        arms = [(1, 6, 2, 3), (13, 6, 2, 3)]
        legs = [(3, 12, 3, 3), (10, 12, 3, 3)]
        shoes = [(2, 14, 4), (10, 14, 4)]
    elif name in ("grow1", "grow2"):
        dy = 1 if name == "grow1" else 0

    if name.startswith("dead"):
        return _small_dead(name)

    # 帽子
    g.rect(3 + lean, 1 + dy, 10, 3, cap)
    g.rect(8 + lean, 4 + dy, 7, 1, RED_D)
    g.rect(4 + lean, 2 + dy, 3, 1, RED_L)
    # 头与脸
    g.rect(4 + lean, 4 + dy, 8, 4, flash)
    g.rect(3 + lean, 5 + dy, 1, 3, HAIR)
    g.rect(11 + lean, 5 + dy, 1, 1, DARK)
    g.rect(8 + lean, 7 + dy, 4, 1, DARK)
    # 身体
    g.rect(4 + lean, 8 + dy, 8, 3, cap)
    g.rect(5 + lean, 10 + dy, 6, 3, BLUE)
    g.rect(6 + lean, 10 + dy, 1, 1, YELLOW)
    g.rect(9 + lean, 10 + dy, 1, 1, YELLOW)
    # 手臂
    for ax, ay, aw, ah in arms:
        g.rect(ax, ay + dy, aw, ah, cap)
        g.rect(ax, ay + ah - 1 + dy, aw, 1, flash)
    # 腿脚
    _small_legs(g, {"legs": [(x, y + dy, w, h) for x, y, w, h in legs],
                    "shoes": [(x, y + dy, w) for x, y, w in shoes]})
    if name in ("grow1", "grow2"):
        for sx, sy in ((1, 2), (14, 5), (2, 12), (13, 1)):
            g.rect(sx, sy, 1, 1, WHITE)
    return g.img


def _small_dead(name: str) -> Image.Image:
    g = Grid(16, 16)
    oy = 1 if name == "dead2" else 0
    g.rect(4, 2 + oy, 8, 3, RED)
    g.rect(8, 5 + oy, 7, 1, RED_D)
    g.rect(4, 5 + oy, 8, 4, SKIN)
    for ex in (6, 10):
        g.rect(ex, 6 + oy, 2, 1, DARK)
        g.rect(ex, 7 + oy, 1, 1, DARK)
    g.rect(7, 8 + oy, 2, 1, DARK)
    g.rect(3, 3 + oy, 2, 3, SKIN)
    g.rect(11, 3 + oy, 2, 3, SKIN)
    g.rect(5, 9 + oy, 6, 2, RED)
    return g.img


def draw_big_frame(name: str) -> Image.Image:
    g = Grid(16, 24)
    flash = SKIN_L if name == "hurt2" else SKIN
    cap = RED_L if name == "hurt2" else RED

    if name == "crouch":
        g.rect(3, 8, 10, 3, cap)
        g.rect(8, 11, 7, 1, RED_D)
        g.rect(4, 11, 8, 5, flash)
        g.rect(11, 12, 1, 1, DARK)
        g.rect(8, 15, 4, 1, DARK)
        g.rect(3, 16, 10, 3, cap)
        g.rect(4, 18, 8, 3, BLUE)
        g.rect(3, 21, 4, 2, BLUE)
        g.rect(9, 21, 4, 2, BLUE)
        g.rect(2, 22, 5, 2, DARK)
        g.rect(9, 22, 5, 2, DARK)
        return g.img

    if name.startswith("dead"):
        oy = 1 if name == "dead2" else 0
        g.rect(3, 2 + oy, 10, 4, RED)
        g.rect(8, 6 + oy, 8, 1, RED_D)
        g.rect(4, 6 + oy, 8, 5, SKIN)
        for ex in (6, 10):
            g.rect(ex, 8 + oy, 2, 1, DARK)
            g.rect(ex, 9 + oy, 1, 1, DARK)
        g.rect(7, 10 + oy, 2, 1, DARK)
        g.rect(2, 4 + oy, 2, 4, SKIN)
        g.rect(12, 4 + oy, 2, 4, SKIN)
        g.rect(4, 11 + oy, 8, 3, RED)
        return g.img

    dy = -1 if name in ("jump", "run2", "run4", "hurt1") else 0
    legs = [(4, 20, 3, 3), (9, 20, 3, 3)]
    shoes = [(3, 22, 4), (9, 22, 4)]
    arms = [(1, 11, 2, 5), (13, 11, 2, 5)]

    if name == "run1":
        legs = [(3, 20, 3, 3), (10, 20, 3, 3)]
        shoes = [(2, 22, 4), (10, 22, 4)]
        arms = [(1, 12, 2, 4), (13, 10, 2, 4)]
    elif name == "run2":
        legs = [(5, 19, 3, 3), (8, 19, 3, 3)]
        shoes = [(4, 22, 4), (8, 22, 4)]
        arms = [(1, 11, 2, 3), (13, 11, 2, 3)]
    elif name == "run3":
        legs = [(3, 20, 3, 3), (10, 20, 3, 3)]
        shoes = [(2, 22, 4), (10, 22, 4)]
        arms = [(1, 10, 2, 4), (13, 12, 2, 4)]
    elif name == "run4":
        legs = [(5, 19, 3, 3), (8, 19, 3, 3)]
        shoes = [(4, 22, 4), (8, 22, 4)]
        arms = [(1, 11, 2, 3), (13, 11, 2, 3)]
    elif name == "jump":
        legs = [(4, 19, 3, 3), (9, 19, 3, 3)]
        shoes = [(3, 21, 4), (9, 21, 4)]
        arms = [(0, 8, 2, 4), (14, 8, 2, 4)]
    elif name == "fall":
        legs = [(3, 20, 3, 3), (10, 20, 3, 3)]
        shoes = [(2, 22, 4), (10, 22, 4)]
        arms = [(0, 11, 2, 3), (14, 11, 2, 3)]
    elif name == "skid":
        arms = [(0, 9, 2, 4), (14, 12, 2, 3)]
    elif name in ("hurt1", "hurt2"):
        arms = [(0, 8, 2, 4), (14, 8, 2, 4)]
        legs = [(3, 20, 3, 3), (10, 20, 3, 3)]
        shoes = [(2, 22, 4), (10, 22, 4)]

    g.rect(3, 1 + dy, 10, 4, cap)
    g.rect(8, 5 + dy, 7, 1, RED_D)
    g.rect(4, 2 + dy, 3, 1, RED_L)
    g.rect(4, 5 + dy, 8, 5, flash)
    g.rect(3, 6 + dy, 1, 4, HAIR)
    g.rect(11, 6 + dy, 1, 2, DARK)
    g.rect(8, 9 + dy, 4, 1, DARK)
    # 躯干
    g.rect(3, 10 + dy, 10, 5, cap)
    g.rect(4, 13 + dy, 8, 6, BLUE)
    g.rect(4, 13 + dy, 8, 1, BLUE_L)
    g.rect(6, 13 + dy, 1, 1, YELLOW)
    g.rect(9, 13 + dy, 1, 1, YELLOW)
    g.rect(6, 16 + dy, 4, 1, BLUE_D)
    for ax, ay, aw, ah in arms:
        g.rect(ax, ay + dy, aw, ah, cap)
        g.rect(ax, ay + ah - 1 + dy, aw, 1, flash)
    for x, y, w, h in legs:
        g.rect(x, y + dy, w, h, BLUE)
        g.rect(x, y + h - 1 + dy, w, 1, BLUE_D)
    for x, y, w in shoes:
        g.rect(x, y + dy, w, 2, DARK)
        g.rect(x + 1, y + dy, w - 2, 1, "#4A3230")
    if name in ("grow1", "grow2"):
        for sx, sy in ((1, 3), (14, 6), (2, 16), (13, 2)):
            g.rect(sx, sy, 1, 1, WHITE)
    return g.img


def draw_enemy(kind: str, frame: int) -> Image.Image:
    g = Grid(16, 16)
    if kind == "patrol_shroom":
        g.ellipse(2, 3, 12, 8, "#D64535")
        g.ellipse(3, 4, 10, 5, "#F06A50")
        g.rect(2, 10, 12, 1, "#8E2418")
        for sx, sy in ((4, 5), (9, 6), (7, 4)):
            g.rect(sx, sy, 2, 2, WHITE)
        g.rect(4, 10, 8, 4, "#F6D7B0")
        g.rect(6, 11, 1, 2, DARK)
        g.rect(9, 11, 1, 2, DARK)
        g.rect(5, 10, 6, 1, BROWN_D)
        fx = 3 if frame == 0 else 2
        g.rect(fx, 14, 4, 2, BROWN_D)
        g.rect(9 + (0 if frame == 0 else 1), 14, 4, 2, BROWN_D)
    elif kind == "shellbug_walk":
        g.ellipse(3, 4, 10, 8, "#2F8F4E")
        g.ellipse(4, 5, 8, 5, "#4FCB6E")
        g.rect(2, 11, 12, 2, "#1E5E34")
        g.rect(1, 8, 4, 4, "#F6D7B0")
        g.rect(2, 9, 1, 1, DARK)
        g.rect(0, 10, 1, 1, DARK)
        for i, x in enumerate((4, 7, 10)):
            yy = 13 if (frame + i) % 2 == 0 else 14
            g.rect(x, yy, 2, 2, DARK)
    elif kind == "shellbug_shell":
        g.ellipse(3, 5, 10, 8, "#2F8F4E")
        g.ellipse(4, 6, 8, 5, "#4FCB6E")
        g.rect(2, 12, 12, 2, "#1E5E34")
        g.rect(6, 7, 4, 4, "#2F8F4E")
    elif kind == "flitter":
        up = frame == 0
        if up:
            g.poly([(7, 7), (1, 2), (2, 8), (6, 10)], "#5B3A78")
            g.poly([(9, 7), (15, 2), (14, 8), (10, 10)], "#5B3A78")
        else:
            g.poly([(7, 8), (1, 11), (3, 15), (6, 11)], "#5B3A78")
            g.poly([(9, 8), (15, 11), (13, 15), (10, 11)], "#5B3A78")
        g.ellipse(5, 6, 6, 7, "#3A2348")
        g.rect(6, 8, 1, 2, WHITE)
        g.rect(9, 8, 1, 2, WHITE)
        g.rect(6, 10, 4, 1, "#C94A6A")
    elif kind == "pipe_bloom":
        g.rect(7, 8, 2, 8, GREEN)
        g.rect(5, 12, 2, 2, GREEN_D)
        g.rect(9, 13, 2, 2, GREEN_D)
        if frame == 0:
            g.ellipse(4, 1, 8, 7, "#E85D8A")
            g.ellipse(2, 3, 3, 4, "#F7A8C0")
            g.ellipse(11, 3, 3, 4, "#F7A8C0")
            g.ellipse(6, 3, 4, 4, YELLOW)
            g.rect(6, 4, 4, 2, "#E0A526")
        else:
            g.ellipse(3, 3, 10, 6, "#E85D8A")
            g.ellipse(5, 2, 6, 4, "#F7A8C0")
            g.rect(6, 3, 4, 2, YELLOW)
    return g.img


def draw_item(kind: str, frame: int) -> Image.Image:
    g = Grid(16, 16)
    if kind == "mushroom":
        g.ellipse(2, 2, 12, 7, "#E63B2E")
        g.ellipse(4, 3, 8, 4, "#F06A50")
        for sx, sy in ((4, 4), (9, 3), (10, 6)):
            g.rect(sx, sy, 2, 2, WHITE)
        g.rect(4, 9, 8, 6, "#F6E2C0")
        g.rect(4, 9, 8, 1, "#C9A97A")
        g.rect(6, 10, 1, 2, DARK)
        g.rect(9, 10, 1, 2, DARK)
    elif kind == "fire_flower":
        g.rect(7, 9, 2, 7, GREEN)
        g.rect(4, 12, 3, 1, GREEN_D)
        g.rect(9, 13, 3, 1, GREEN_D)
        if frame == 0:
            g.ellipse(3, 1, 10, 8, ORANGE)
            g.ellipse(5, 2, 6, 5, "#FFD54A")
            g.ellipse(4, 3, 3, 3, "#FFF3B0")
            g.ellipse(9, 3, 3, 3, "#FFF3B0")
        else:
            g.ellipse(3, 2, 10, 7, "#E06A1A")
            g.ellipse(5, 3, 6, 4, "#FFD54A")
            g.rect(5, 4, 2, 2, WHITE)
    elif kind == "fireball":
        cx, cy = 8, 8
        g.ellipse(4, 4, 8, 8, "#E85D1A")
        g.ellipse(5, 5, 6, 6, "#FFB03A")
        g.ellipse(6, 6, 4, 4, "#FFF3B0")
        if frame % 2 == 0:
            g.poly([(cx, cy), (cx - 5, cy - 3), (cx - 3, cy + 4)], "#FF6A58")
        else:
            g.poly([(cx, cy), (cx + 5, cy - 2), (cx + 3, cy + 4)], "#FF6A58")
        g.rect(11 if frame in (1, 2) else 4, 11, 1, 1, "#FFF3B0")
    return g.img


def build_sheet(frames: list[list[Image.Image | None]], cell_w: int, cell_h: int) -> Image.Image:
    cols = max(len(r) for r in frames)
    rows = len(frames)
    sheet = Image.new("RGBA", (cell_w * cols, cell_h * rows), (0, 0, 0, 0))
    for row, entries in enumerate(frames):
        for col, frame in enumerate(entries):
            if frame is not None:
                sheet.paste(frame, (col * cell_w, row * cell_h))
    return sheet


def make_logo() -> Image.Image:
    """128×128 逻辑像素绘制后最近邻放大 4 倍到 512×512（像素风，无柔光/模糊）。"""
    base = 128
    img = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 底部投影（硬边椭圆）
    d.ellipse([22, 96, 106, 116], fill=(0, 0, 0, 90))
    # 帽檐
    d.rectangle([18, 76, 110, 90], fill=RED_D, outline=DARK, width=2)
    d.rectangle([21, 79, 107, 86], fill=RED)
    # 帽体
    d.polygon([(27, 80), (33, 52), (48, 40), (76, 39), (95, 50), (102, 80)], fill=RED)
    d.polygon([(34, 72), (39, 54), (52, 45), (75, 44), (90, 54), (96, 72)], fill=RED_L)
    d.line([(28, 77), (35, 54), (50, 42), (76, 41), (95, 51), (101, 77)], fill=DARK, width=2)
    # 帽徽：一棵小树
    d.ellipse([54, 54, 78, 78], fill=WHITE, outline=GREEN_D, width=2)
    d.rectangle([62, 66, 68, 76], fill=BROWN, outline=BROWN_D)
    d.polygon([(66, 55), (56, 69), (76, 69)], fill=GREEN, outline=GREEN_D)
    d.polygon([(66, 59), (58, 72), (74, 72)], fill=GREEN_L)
    # 叶子
    d.line([(80, 42), (92, 29)], fill=GREEN_D, width=2)
    d.polygon([(92, 30), (86, 26), (84, 20), (86, 15), (91, 12),
               (97, 14), (101, 18), (100, 24), (96, 28)], fill=GREEN, outline=GREEN_D)
    d.line([(92, 29), (94, 15)], fill=GREEN_L)
    # 高光与火花
    d.rectangle([37, 58, 41, 76], fill="#FF9A88")
    for x, y in ((21, 30), (107, 37), (102, 95), (25, 62)):
        d.rectangle([x, y, x + 1, y + 1], fill=(255, 255, 255, 200))
    return img.resize((512, 512), Image.Resampling.NEAREST)


def _save_ico(path: Path, source: Image.Image, sizes: tuple[int, ...]) -> None:
    """手工写 ICO：每个尺寸用最近邻缩放后以 PNG 压缩存储，避免默认重采样糊掉像素边。"""
    frames: list[tuple[int, bytes]] = []
    for size in sizes:
        frame = source.resize((size, size), Image.Resampling.NEAREST)
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        frames.append((size, buf.getvalue()))
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    directory = b""
    payload = b""
    for size, png in frames:
        dim = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        payload += png
    path.write_bytes(header + directory + payload)


def make_menu_bg() -> Image.Image:
    """320×180 逻辑像素绘制后最近邻放大 4 倍到 1280×720（像素风，去柔光/暗角）。"""
    bw, bh = 320, 180
    img = Image.new("RGB", (bw, bh))
    d = ImageDraw.Draw(img, "RGBA")
    # 天空色带（硬边台阶）
    bands = 8
    for i in range(bands):
        t = i / (bands - 1)
        color = (int(8 + 18 * t), int(22 + 54 * t), int(38 + 62 * t))
        y0 = i * bh // bands
        y1 = (i + 1) * bh // bands - 1
        d.rectangle([0, y0, bw - 1, y1], fill=color)
    # 月亮（块状双圈）
    d.ellipse([252, 10, 282, 40], fill=(120, 200, 205))
    d.ellipse([258, 16, 276, 34], fill=(180, 235, 236))
    # 远景树冠（块状剪影）
    for i in range(14):
        x = i * 25 - 10
        y = 140 + (i % 4) * 5
        d.rectangle([x, y, x + 60, y + 65], fill=(10, 48, 42))
        d.rectangle([x + 12, y - 12, x + 48, y + 8], fill=(12, 54, 46))
    d.rectangle([0, 160, bw - 1, bh - 1], fill=(6, 22, 24))
    # 低亮度星点
    import random
    rng = random.Random(7)
    for _ in range(90):
        x, y = rng.randrange(bw), rng.randrange(0, 105)
        d.point((x, y), fill=(200, 240, 255))
    return img.resize((1280, 720), Image.Resampling.NEAREST)


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    small_names = [["idle", "run1", "run2", "run3", "run4", None],
                   ["jump", "fall", "skid", "hurt1", "hurt2", None],
                   ["grow1", "grow2", "dead1", "dead2", None, None],
                   [None, None, None, None, None, None]]
    big_names = [small_names[0], small_names[1], small_names[2],
                 ["crouch", None, None, None, None, None]]
    small_sheet = build_sheet([[draw_small_frame(n) if n else None for n in row] for row in small_names], 48, 48)
    big_sheet = build_sheet([[draw_big_frame(n) if n else None for n in row] for row in big_names], 48, 72)
    small_sheet.save(IMG_DIR / "player_small.png")
    big_sheet.save(IMG_DIR / "player_big.png")

    enemy_rows = [
        [draw_enemy("patrol_shroom", 0), draw_enemy("patrol_shroom", 1), None, None],
        [draw_enemy("shellbug_walk", 0), draw_enemy("shellbug_walk", 1), None, None],
        [draw_enemy("shellbug_shell", 0), None, None, None],
        [draw_enemy("flitter", 0), draw_enemy("flitter", 1), None, None],
        [draw_enemy("pipe_bloom", 0), draw_enemy("pipe_bloom", 1), None, None],
    ]
    enemy_sheet = build_sheet(enemy_rows, 48, 48)
    enemy_sheet.save(IMG_DIR / "enemies.png")

    item_rows: list[list[Image.Image | None]] = [
        [draw_item("mushroom", 0), None, None, None],
        [draw_item("fire_flower", 0), draw_item("fire_flower", 1), None, None],
        [draw_item("fireball", 0), draw_item("fireball", 1),
         draw_item("fireball", 2), draw_item("fireball", 3)],
    ]
    item_sheet = build_sheet(item_rows, 48, 48)
    item_sheet.save(IMG_DIR / "items.png")

    logo = make_logo()
    logo.save(IMG_DIR / "logo.png")
    menu_bg = make_menu_bg()
    menu_bg.save(IMG_DIR / "bg_menu.png")

    icon = logo.resize((256, 256), Image.Resampling.NEAREST)
    icon.save(IMG_DIR.parent / "icon.png")
    _save_ico(IMG_DIR.parent / "icon.ico", logo, (16, 24, 32, 48, 64, 128, 256))

    for name, sheet in (("player_small", small_sheet), ("player_big", big_sheet),
                        ("enemies", enemy_sheet), ("items", item_sheet),
                        ("logo", logo), ("bg_menu", menu_bg)):
        print(f"wrote {name}.png {sheet.size}")


if __name__ == "__main__":
    main()

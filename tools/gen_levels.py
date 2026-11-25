"""生成 4 个关卡 JSON。

关卡布局按 docs/08 §4 的设计定位编写，输出到 assets/levels/。
可重复执行；每次生成结果一致（全部使用固定坐标与固定随机种子）。
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "levels"
SOLID_FOR_ENTITY = {"#", "B", "M", "P", "?", "X"}


class Builder:
    def __init__(self, cols: int, theme: str, time: int, seed: int):
        self.cols = cols
        self.rows = 18
        self.theme = theme
        self.time = time
        self.rng = random.Random(seed)
        self.grid = [["." for _ in range(cols)] for _ in range(self.rows)]
        for y in (16, 17):
            for x in range(cols):
                self.grid[y][x] = "#"
        self.entities: list[dict] = []
        self.items: dict[str, str] = {}

    def put(self, col: int, row: int, code: str) -> None:
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.grid[row][col] = code

    def get(self, col: int, row: int) -> str:
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[row][col]
        return "#"

    def pit(self, col: int, width: int) -> None:
        for x in range(col, col + width):
            self.put(x, 16, ".")
            self.put(x, 17, ".")

    def pipe(self, col: int, height: int) -> None:
        for x in (col, col + 1):
            for y in range(16 - height, 16):
                self.put(x, y, "P")

    def row_blocks(self, col: int, row: int, codes: str) -> None:
        for i, code in enumerate(codes):
            self.put(col + i, row, code)

    def question(self, col: int, row: int, item: str) -> None:
        self.put(col, row, "?")
        self.items[f"{col},{row}"] = item

    def coin_arc(self, col: int, row: int, width: int) -> None:
        for i in range(width):
            y = row if i in (0, width - 1) else row - 1
            if self.get(col + i, y) == ".":
                self.put(col + i, y, "c")

    def coins(self, col: int, row: int, width: int) -> None:
        for i in range(width):
            if self.get(col + i, row) == ".":
                self.put(col + i, row, "c")

    def platform(self, col: int, row: int, width: int) -> None:
        for x in range(col, col + width):
            self.put(x, row, "=")

    def spikes(self, col: int, width: int) -> None:
        for x in range(col, col + width):
            if self.get(x, 15) == "." and self.get(x, 16) == "#":
                self.put(x, 15, "^")

    def enemy(self, kind: str, col: int, row: int = 15, **extra) -> None:
        if row == 15:
            for x in range(max(0, col - 1), min(self.cols, col + 2)):
                if self.grid[15][x] == "^":
                    self.grid[15][x] = "."
        item = {"type": kind, "col": col, "row": row}
        item.update(extra)
        self.entities.append(item)

    def checkpoint(self, col: int) -> None:
        self.enemy("checkpoint", col, 15)

    def goal(self, col: int) -> None:
        self.enemy("goal", col, 15)

    def build(self, level_id: str, name: str) -> dict:
        return {
            "id": level_id,
            "name": name,
            "theme": self.theme,
            "cols": self.cols,
            "rows": self.rows,
            "time": self.time,
            "spawn": [3, 15],
            "tiles": ["".join(row) for row in self.grid],
            "items": self.items,
            "entities": self.entities,
        }


def level_1() -> dict:
    b = Builder(200, "grass", 300, 101)
    for c, w in ((28, 3), (52, 4), (78, 3), (104, 4), (130, 5), (156, 3), (178, 4)):
        b.pit(c, w)
    for c, h in ((18, 2), (44, 3), (68, 2), (94, 3), (120, 2), (146, 3), (172, 2)):
        b.pipe(c, h)

    b.row_blocks(12, 12, "B?BB?")
    b.row_blocks(13, 11, "BB")
    b.question(13, 12, "coin")
    b.question(15, 12, "mushroom")
    b.question(16, 12, "coin")
    b.row_blocks(38, 12, "B?B")
    b.question(39, 12, "coin")
    b.row_blocks(60, 12, "?B?")
    b.question(60, 12, "flower")
    b.row_blocks(61, 11, "B")
    b.question(62, 12, "coin")
    b.row_blocks(86, 12, "B?B")
    b.question(87, 12, "mushroom")
    b.row_blocks(110, 12, "?B?")
    b.question(110, 12, "coin")
    b.question(112, 12, "flower")
    b.row_blocks(136, 12, "B?B")
    b.question(137, 12, "mushroom")
    b.row_blocks(162, 12, "?B?")
    b.question(162, 12, "coin")
    b.question(164, 12, "flower")

    for c, w in ((28, 3), (52, 4), (78, 3), (104, 4), (130, 5), (156, 3), (178, 4)):
        b.coin_arc(c, 12, w)
    b.coins(14, 9, 4)
    b.coins(40, 9, 3)
    b.coins(62, 9, 3)
    b.coins(88, 9, 3)
    b.coins(112, 9, 3)
    b.coins(138, 9, 3)
    b.coins(164, 9, 3)

    for c in (22, 34, 48, 58, 84, 100, 116, 126, 142, 150, 166, 182):
        b.enemy("patrol_shroom", c)
    for c in (40, 74, 108, 140, 160, 188):
        b.enemy("shellbug", c)
    b.enemy("flitter", 30, 9, amp=60, period=2.4)
    b.enemy("flitter", 118, 8, amp=70, period=2.0)
    b.enemy("moving_platform", 56, 10, path=[[56, 10], [62, 10]], speed=60)
    b.checkpoint(99)
    b.goal(194)
    return b.build("1-1", "青草平原")


def level_2() -> dict:
    b = Builder(170, "cave", 300, 202)
    for c, w in ((26, 4), (50, 5), (74, 3), (98, 4), (122, 5), (146, 3)):
        b.pit(c, w)
    for c, h in ((32, 2), (58, 3), (82, 2), (106, 3), (130, 2), (154, 3)):
        b.pipe(c, h)

    for c, w, row in ((27, 2, 12), (51, 3, 12), (74, 3, 12), (98, 3, 12), (122, 3, 12), (146, 3, 12)):
        b.platform(c, row, w)

    b.row_blocks(14, 12, "B?B")
    b.question(15, 12, "mushroom")
    b.row_blocks(44, 12, "?BB?")
    b.question(44, 12, "coin")
    b.question(47, 12, "flower")
    b.row_blocks(70, 12, "B?B")
    b.question(71, 12, "coin")
    b.row_blocks(94, 11, "B?B")
    b.question(95, 11, "mushroom")
    b.row_blocks(118, 12, "?B?")
    b.question(118, 12, "coin")
    b.question(120, 12, "flower")
    b.row_blocks(142, 12, "B?B")
    b.question(143, 12, "mushroom")
    b.row_blocks(160, 12, "?B?")
    b.question(160, 12, "coin")
    b.question(162, 12, "coin")

    for c, w in ((26, 4), (50, 5), (74, 3), (98, 4), (122, 5), (146, 3)):
        b.coin_arc(c, 11, w)
    b.coins(16, 9, 4)
    b.coins(46, 9, 4)
    b.coins(72, 9, 4)
    b.coins(96, 9, 4)
    b.coins(120, 9, 4)
    b.coins(144, 9, 4)

    for c, w in ((18, 2), (40, 3), (64, 2), (88, 3), (112, 2), (136, 3), (158, 2)):
        b.spikes(c, w)

    for c in (20, 38, 56, 66, 94, 110, 134, 152, 168):
        b.enemy("shellbug", c)
    for c in (16, 42, 72, 102, 128):
        b.enemy("patrol_shroom", c)
    b.enemy("flitter", 30, 10, amp=55, period=2.2)
    b.enemy("flitter", 84, 9, amp=65, period=2.6)
    b.enemy("flitter", 116, 8, amp=60, period=2.0)
    b.enemy("pipe_bloom", 58, 12)
    b.enemy("pipe_bloom", 130, 13)
    b.enemy("moving_platform", 52, 10, path=[[52, 10], [58, 10]], speed=55)
    b.enemy("moving_platform", 124, 10, path=[[124, 10], [130, 10]], speed=55)
    b.checkpoint(86)
    b.goal(164)
    return b.build("1-2", "回声洞窟")


def level_3() -> dict:
    b = Builder(180, "sky", 320, 303)
    for c, w in ((26, 5), (50, 5), (74, 5), (98, 5), (122, 5), (146, 5), (164, 4)):
        b.pit(c, w)
    for c, row, w in ((26, 12, 3), (50, 12, 3), (74, 12, 3), (98, 12, 3),
                      (122, 12, 3), (146, 12, 3), (164, 12, 3)):
        b.platform(c, row, w)
    for c, row, w in ((36, 10, 4), (60, 10, 4), (84, 10, 4), (108, 10, 4),
                      (132, 10, 4), (156, 10, 3)):
        b.platform(c, row, w)

    b.row_blocks(18, 12, "B?B")
    b.question(19, 12, "mushroom")
    b.row_blocks(42, 12, "?B?")
    b.question(42, 12, "coin")
    b.question(44, 12, "flower")
    b.row_blocks(66, 12, "B?B")
    b.question(67, 12, "mushroom")
    b.row_blocks(90, 12, "?B?")
    b.question(90, 12, "coin")
    b.question(92, 12, "flower")
    b.row_blocks(114, 12, "B?B")
    b.question(115, 12, "mushroom")
    b.row_blocks(138, 12, "?B?")
    b.question(138, 12, "coin")
    b.question(140, 12, "flower")
    b.row_blocks(162, 12, "B?B")
    b.question(163, 12, "mushroom")

    for c, w in ((26, 5), (50, 5), (74, 5), (98, 5), (122, 5), (146, 5), (164, 4)):
        b.coin_arc(c, 9, w)
    b.coins(36, 8, 4)
    b.coins(60, 8, 4)
    b.coins(84, 8, 4)
    b.coins(108, 8, 4)
    b.coins(132, 8, 4)
    b.coins(156, 8, 3)

    for c in (16, 40, 88, 136):
        b.enemy("patrol_shroom", c)
    for c in (32, 64, 112):
        b.enemy("shellbug", c)
    for c, row in ((20, 9), (44, 8), (68, 9), (82, 10), (96, 8), (110, 9), (134, 10), (152, 9),
                   (158, 8), (168, 10)):
        b.enemy("flitter", c, row, amp=70, period=2.2)
    b.enemy("moving_platform", 27, 11, path=[[27, 11], [32, 11]], speed=60)
    b.enemy("moving_platform", 75, 10, path=[[75, 10], [80, 10]], speed=65)
    b.enemy("moving_platform", 123, 9, path=[[123, 9], [128, 9]], speed=65)
    b.checkpoint(90)
    b.goal(174)
    return b.build("1-3", "浮云回廊")


def level_4() -> dict:
    b = Builder(190, "castle", 340, 404)
    for c, w in ((24, 5), (50, 5), (76, 5), (102, 5), (128, 5), (154, 5), (176, 4)):
        b.pit(c, w)
    for c, h in ((32, 3), (58, 3), (84, 3), (110, 3), (136, 3), (162, 2)):
        b.pipe(c, h)

    b.row_blocks(12, 12, "?BB?")
    b.question(12, 12, "mushroom")
    b.question(15, 12, "coin")
    b.row_blocks(40, 12, "B?B")
    b.question(41, 12, "flower")
    b.row_blocks(68, 11, "?B?")
    b.question(68, 11, "coin")
    b.question(70, 11, "mushroom")
    b.row_blocks(92, 12, "B?B")
    b.question(93, 12, "flower")
    b.row_blocks(118, 11, "?B?")
    b.question(118, 11, "mushroom")
    b.question(120, 11, "coin")
    b.row_blocks(144, 12, "B?B")
    b.question(145, 12, "flower")
    b.row_blocks(170, 12, "?BB?")
    b.question(170, 12, "mushroom")
    b.question(173, 12, "coin")

    for c, w in ((24, 5), (50, 5), (76, 5), (102, 5), (128, 5), (154, 5), (176, 4)):
        b.coin_arc(c, 10, w)
    b.coins(12, 9, 4)
    b.coins(40, 9, 3)
    b.coins(68, 9, 3)
    b.coins(92, 9, 3)
    b.coins(118, 9, 3)
    b.coins(144, 9, 3)
    b.coins(170, 9, 4)

    for c, w in ((18, 2), (36, 3), (44, 2), (62, 3), (70, 2), (88, 3), (96, 2),
                 (114, 3), (122, 2), (140, 3), (148, 2), (166, 3), (172, 2)):
        b.spikes(c, w)

    for c in (20, 38, 56, 72, 92, 108, 124, 150):
        b.enemy("shellbug", c)
    for c in (16, 42, 68, 100, 144):
        b.enemy("patrol_shroom", c)
    for c, row in ((28, 9), (80, 8), (132, 9)):
        b.enemy("flitter", c, row, amp=75, period=1.9)
    for c in (32, 58, 84, 110, 136):
        b.enemy("pipe_bloom", c, 12)
    b.enemy("pipe_bloom", 162, 13)
    b.enemy("moving_platform", 50, 10, path=[[50, 10], [55, 10]], speed=65)
    b.enemy("moving_platform", 128, 9, path=[[128, 9], [133, 9]], speed=70)
    b.checkpoint(96)
    b.goal(184)
    return b.build("1-4", "熔火城塞")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for level in (level_1(), level_2(), level_3(), level_4()):
        path = OUT / f"w{level['id']}.json"
        path.write_text(json.dumps(level, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {path.name}: {level['cols']}x{level['rows']}, "
              f"{len(level['entities'])} entities, {len(level['items'])} items")


if __name__ == "__main__":
    main()

"""AABB 与瓦片碰撞解算（docs/03 §3）。

纯逻辑，不引入 pygame；只允许依赖 config 与 tilemap 的只读查询。
"""

from __future__ import annotations

import math

from .config import TILE
from .tilemap import TileMap


class Body:
    """轴对齐包围盒；x/y 为左上角世界坐标，单位 px。"""

    def __init__(self, x: float, y: float, w: float, h: float,
                 vx: float = 0.0, vy: float = 0.0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.vx = vx
        self.vy = vy

    @property
    def aabb(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.x + self.w, self.y + self.h

    @property
    def bottom(self) -> float:
        return self.y + self.h


class Contacts:
    """一次 move_and_collide 的接触结果。"""

    def __init__(self):
        self.left = False
        self.right = False
        self.head = False
        self.ground = False
        self.head_tiles: list[tuple[int, int]] = []


def overlap(a: Body | tuple, b: Body | tuple) -> bool:
    a_box = a.aabb if isinstance(a, Body) else a
    b_box = b.aabb if isinstance(b, Body) else b
    return (a_box[0] < b_box[2] and b_box[0] < a_box[2]
            and a_box[1] < b_box[3] and b_box[1] < a_box[3])


def span(body: Body) -> tuple[int, int, int, int]:
    """返回体当前覆盖的瓦片列/行区间（含端点）。用 1e-6 内缩，避免贴边时把相邻格算进来。"""
    c0 = math.floor(body.x / TILE)
    c1 = math.floor((body.x + body.w - 1e-6) / TILE)
    r0 = math.floor(body.y / TILE)
    r1 = math.floor((body.y + body.h - 1e-6) / TILE)
    return c0, c1, r0, r1


def move_and_collide(body: Body, tmap: TileMap, dt: float,
                     drop_through: bool = False) -> Contacts:
    """先水平、后垂直，分别贴边。drop_through=True 时忽略单向平台（按下键下穿）。"""
    contacts = Contacts()
    prev_bottom = body.bottom

    # ——— 水平 ———
    if body.vx:
        body.x += body.vx * dt
        c0, c1, r0, r1 = span(body)
        if body.vx > 0:
            hit = [c for c in range(c0, c1 + 1)
                   if any(tmap.solid(c, r) for r in range(r0, r1 + 1))]
            if hit:
                body.x = min(hit) * TILE - body.w      # 贴住最左的实心格
                body.vx = 0.0
                contacts.right = True
        else:
            hit = [c for c in range(c1, c0 - 1, -1)
                   if any(tmap.solid(c, r) for r in range(r0, r1 + 1))]
            if hit:
                body.x = (max(hit) + 1) * TILE
                body.vx = 0.0
                contacts.left = True

    # ——— 垂直 ———
    if body.vy:
        body.y += body.vy * dt
        c0, c1, r0, r1 = span(body)
        cols = range(max(0, c0), min(tmap.cols, c1 + 1))
        if body.vy > 0:                                  # 下落
            rows = [r for r in range(r0, r1 + 1)
                    if any(tmap.solid(c, r) for c in cols)
                    or (not drop_through
                        and any(tmap.semisolid(c, r) for c in cols)
                        and prev_bottom <= r * TILE + 0.5)]
            if rows:
                body.y = min(rows) * TILE - body.h
                body.vy = 0.0
                contacts.ground = True
        else:                                            # 上升
            rows = [r for r in range(r1, r0 - 1, -1)
                    if any(tmap.solid(c, r) for c in cols)]
            if rows:
                row = max(rows)
                body.y = (row + 1) * TILE
                body.vy = 0.0
                contacts.head = True
                contacts.head_tiles = [(c, row) for c in cols
                                       if tmap.solid(c, row)]
    return contacts


def standing_on(body: Body, tmap: TileMap) -> bool:
    """脚底正好压在实心或单向平台顶面上（误差 1.5 px），用于动画与土狼时间。"""
    c0, c1, _, _ = span(body)
    row = int(round(body.bottom / TILE))
    for c in range(max(0, c0), min(tmap.cols, c1 + 1)):
        if tmap.solid(c, row) or tmap.semisolid(c, row):
            return True
    return False

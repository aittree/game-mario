"""移动平台、检查点与终点旗杆（docs/03 §5.5）。"""

from __future__ import annotations

from ..config import TILE
from .base import Entity, WorldView, place_at


class MovingPlatform(Entity):
    kind = "moving_platform"
    W, H = 120, 20

    def __init__(self, col: int, row: int, path: list, speed: float):
        super().__init__(col * TILE, row * TILE, self.W, self.H)
        self.points = [(c * TILE, r * TILE) for c, r in path]
        self.speed = speed
        self.target = 1
        self.dx = 0.0

    def update(self, dt: float, _world: WorldView) -> None:
        ox = self.body.x
        tx, ty = self.points[self.target]
        step = self.speed * dt
        dx, dy = tx - self.body.x, ty - self.body.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= step:
            self.body.x, self.body.y = tx, ty
            self.target = (self.target + 1) % len(self.points)
        elif dist > 0:
            self.body.x += dx / dist * step
            self.body.y += dy / dist * step
        self.dx = self.body.x - ox          # 载人时把位移加到玩家身上


class Checkpoint(Entity):
    kind = "checkpoint"

    def __init__(self, col: int, row: int):
        x, y = place_at(col, row, 24, 4 * TILE)
        super().__init__(x, y, 24, 4 * TILE)
        self.raised = False

    def touch(self) -> bool:
        """首次触碰返回 True（用于播放音效与记档）。"""
        if self.raised:
            return False
        self.raised = True
        return True


class Goal(Entity):
    kind = "goal"

    def __init__(self, col: int, row: int):
        x, y = place_at(col, row, 16, 9 * TILE)
        super().__init__(x, y, 16, 9 * TILE)
        self.touched = False     # 玩家是否已碰到旗杆
        self.flag_y = 0.0        # 旗帜高度偏移，通关动画用

    def touch(self) -> bool:
        """首次触碰返回 True（触发通关流程）。"""
        if self.touched:
            return False
        self.touched = True
        return True

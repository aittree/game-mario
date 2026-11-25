"""四类敌人（docs/03 §5.1～§5.3）。

统一的更新约定：`update(dt, world)` 内自行推进位移与地形解算，不依赖会话。
"""

from __future__ import annotations

import math

from ..config import (
    BLOOM_CYCLE,
    BLOOM_OUT_MS,
    FLITTER_AMP,
    FLITTER_PERIOD,
    FLITTER_SPEED,
    GRAVITY,
    MAX_FALL,
    SHELLBUG_SPEED,
    SHELL_SPEED,
    SHELL_WALL_LIMIT,
    SHROOM_SPEED,
    TILE,
)
from ..physics import move_and_collide
from .base import Entity, WorldView, place_at


class PatrolShroom(Entity):
    kind = "patrol_shroom"
    W, H, SPEED = 36, 36, SHROOM_SPEED

    def __init__(self, col: int, row: int):
        x, y = place_at(col, row, self.W, self.H)
        super().__init__(x, y, self.W, self.H)
        self.dir = -1
        self.squash_ms = 0.0

    def update(self, dt: float, world: WorldView) -> None:
        if self.squash_ms > 0:                 # 被踩扁后短暂停留再消失
            self.squash_ms -= dt * 1000
            if self.squash_ms <= 0:
                self.alive = False
            return
        self.anim_timer += dt
        self.body.vx = self.dir * self.SPEED
        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)
        contacts = move_and_collide(self.body, world.tilemap, dt)

        if contacts.left or contacts.right:
            self.dir *= -1
        elif contacts.ground and not self._ground_ahead(world.tilemap):
            self.dir *= -1                     # 平台边缘掉头，避免自杀式掉坑

    def _ground_ahead(self, tmap) -> bool:
        probe = self.body.x + self.body.w + 4 if self.dir > 0 else self.body.x - 4
        col = int(probe // TILE)
        row = int((self.body.bottom + 4) // TILE)
        return tmap.solid(col, row) or tmap.semisolid(col, row)

    def on_stomp(self) -> bool:
        self.squash_ms = 250
        self.body.vx = 0
        return True


class Shellbug(Entity):
    """WALK → SHELL_IDLE → SHELL_SLIDE；滑行撞墙 3 次后消失。"""

    kind = "shellbug"
    W, H = 44, 34

    def __init__(self, col: int, row: int):
        x, y = place_at(col, row, self.W, self.H)
        super().__init__(x, y, self.W, self.H)
        self.dir = -1
        self.state: str = "walk"
        self.wall_hits = 0

    def update(self, dt: float, world: WorldView) -> None:
        self.anim_timer += dt
        speed = {"walk": SHELLBUG_SPEED, "shell_idle": 0.0,
                 "shell_slide": SHELL_SPEED}[self.state]
        self.body.vx = self.dir * speed
        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)
        contacts = move_and_collide(self.body, world.tilemap, dt)

        if contacts.left or contacts.right:
            if self.state == "shell_slide":
                self.wall_hits += 1
                if self.wall_hits >= SHELL_WALL_LIMIT:
                    self.alive = False
                    return
            self.dir *= -1
        elif self.state == "walk" and contacts.ground and not self._ground_ahead(world.tilemap):
            self.dir *= -1

    def _ground_ahead(self, tmap) -> bool:
        probe = self.body.x + self.body.w + 4 if self.dir > 0 else self.body.x - 4
        col = int(probe // TILE)
        row = int((self.body.bottom + 4) // TILE)
        return tmap.solid(col, row) or tmap.semisolid(col, row)

    def on_stomp(self) -> bool:
        if self.state == "walk":
            self.state = "shell_idle"
            self.body.h = 24
            self.body.y += 10
        elif self.state == "shell_slide":
            self.state = "shell_idle"          # 踩滑行的壳 = 刹车
        return True

    def kick(self, direction: int) -> None:
        """玩家侧碰静止壳：壳沿远离玩家的方向滑行。"""
        if self.state == "shell_idle":
            self.state, self.dir, self.wall_hits = "shell_slide", direction, 0


class Flitter(Entity):
    kind = "flitter"
    W, H = 44, 36

    def __init__(self, col: int, row: int,
                 amp: float = FLITTER_AMP, period: float = FLITTER_PERIOD):
        x, y = place_at(col, row, self.W, self.H, bottom_aligned=False)
        super().__init__(x, y, self.W, self.H)
        self.anchor_x, self.anchor_y = self.body.x, self.body.y
        self.amp, self.period = amp, period
        self.t = 0.0
        self.dir = -1

    def update(self, dt: float, world: WorldView) -> None:
        # 飞行体不走瓦片碰撞，按参数化轨迹运动（关卡设计不得把它放在墙体内）
        self.t += dt
        self.body.x = self.anchor_x + self.dir * FLITTER_SPEED * self.t
        self.body.y = self.anchor_y + self.amp * math.sin(2 * math.pi * self.t / self.period)
        if (not (0 < self.body.x < world.width_px - self.W)
                or abs(self.body.x - self.anchor_x) > 5 * TILE):
            self.dir *= -1
            self.anchor_x = self.body.x - self.dir * FLITTER_SPEED * self.t

    def on_stomp(self) -> bool:
        return False          # 飞行体不可踩


class PipeBloom(Entity):
    kind = "pipe_bloom"
    W, H = 36, 46

    def __init__(self, col: int, row: int):
        x, y = place_at(col, row, self.W, self.H, bottom_aligned=False)
        super().__init__(x, y, self.W, self.H)
        self.base_y = y
        self.t = 0.0
        self.visible = False

    def update(self, dt: float, _world: WorldView) -> None:
        self.t = (self.t + dt) % BLOOM_CYCLE
        out = self._exposure()                       # 0（全藏）~1（全出）
        self.body.y = self.base_y + (1 - out) * self.H
        self.visible = out > 0.15

    def _exposure(self) -> float:
        up = BLOOM_OUT_MS / 1000
        t = self.t
        if t < 0.2:
            return t / 0.2                            # 0.2 s 升起
        if t < up:
            return 1.0                                # 露出 1.4 s
        if t < up + 0.25:
            return 1 - (t - up) / 0.25                # 0.25 s 收回
        return 0.0                                    # 藏起

    def on_stomp(self) -> bool:
        return False

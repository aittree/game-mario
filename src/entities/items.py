"""道具与火球（docs/03 §5.4）。"""

from __future__ import annotations

from ..config import (
    FIRE_SPEED,
    GRAVITY,
    MAX_FALL,
    STOMP_BOUNCE,
)
from ..physics import move_and_collide
from .base import Entity, WorldView, place_at

EMERGE_SPEED = 100.0   # 升起速度：400 ms 恰好升满 40 px（一格），确保完全脱离砖块


class Mushroom(Entity):
    kind = "mushroom"
    W, H, SPEED = 32, 32, 90

    def __init__(self, col: int, row: int, emerge: bool = True):
        x, y = place_at(col, row, self.W, self.H)
        super().__init__(x, y, self.W, self.H)
        self.emerge_ms = 400 if emerge else 0
        self.dir = 1

    def update(self, dt: float, world: WorldView) -> None:
        self.anim_timer += dt
        if self.emerge_ms > 0:                       # 从块中升起，期间不移动不碰撞
            self.emerge_ms -= dt * 1000
            self.body.y -= EMERGE_SPEED * dt
            return
        self.body.vx = self.dir * self.SPEED
        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)
        contacts = move_and_collide(self.body, world.tilemap, dt)
        if contacts.left or contacts.right:
            self.dir *= -1


class FireFlower(Entity):
    kind = "fire_flower"
    W, H, LIFE_MS = 32, 36, 8000

    def __init__(self, col: int, row: int, emerge: bool = True):
        x, y = place_at(col, row, self.W, self.H)
        super().__init__(x, y, self.W, self.H)
        self.emerge_ms = 400 if emerge else 0
        self.life_ms = self.LIFE_MS

    def update(self, dt: float, _world: WorldView) -> None:
        self.anim_timer += dt
        if self.emerge_ms > 0:
            self.emerge_ms -= dt * 1000
            self.body.y -= EMERGE_SPEED * dt
            return
        self.life_ms -= dt * 1000
        if self.life_ms <= 0:
            self.alive = False


class Fireball(Entity):
    kind = "fireball"
    W, H = 20, 20

    def __init__(self, cx: float, cy: float, direction: int):
        super().__init__(cx - self.W / 2, cy - self.H / 2, self.W, self.H)
        self.body.vx = direction * FIRE_SPEED
        self.body.vy = 120
        self.life_ms = 3000
        self.events: list[str] = []

    def update(self, dt: float, world: WorldView) -> None:
        self.life_ms -= dt * 1000
        if self.life_ms <= 0:
            self.alive = False
            return
        self.anim_timer += dt
        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)
        contacts = move_and_collide(self.body, world.tilemap, dt)
        if contacts.ground:
            self.body.vy = -STOMP_BOUNCE * 0.85      # 地面持续弹跳，不再限定弹跳次数
        if contacts.left or contacts.right:
            self.alive = False                       # 撞到侧面墙壁：爆炸消失（SMB1）
            self.events.append("spark")
        if self.body.x < -100 or self.body.x > world.width_px + 100:
            self.alive = False                       # 飞出关卡边界

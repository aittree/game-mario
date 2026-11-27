"""玩家实体（docs/03 §4.2）。

输入→速度、可变跳跃、土狼时间、跳跃缓冲、踩踏、变形、受伤与火球。
模型的每一步（PHYSICS_DT）都由会话驱动一次 `update()`，内部完成位移与地形解算。
"""

from __future__ import annotations

import math
from typing import Protocol

from ..config import (
    AIR_ACC,
    COYOTE_MS,
    FIRE_COOLDOWN_MS,
    FRICTION,
    GRAVITY,
    GROUND_ACC,
    INVINCIBLE_MS,
    JUMP_BUFFER_MS,
    JUMP_CUT,
    JUMP_SPEED_BONUS,
    JUMP_VEL,
    MAX_FALL,
    MAX_SPRINT,
    MAX_WALK,
    PLY_H_BIG,
    PLY_H_SMALL,
    PLY_W_BIG,
    PLY_W_SMALL,
    SKID_DEC,
    SPRINT_ACC,
    STOMP_BOUNCE,
    TILE,
    TRANSFORM_MS,
)
from ..physics import Body, Contacts, move_and_collide, span, standing_on
from .base import AnimState, Entity, InputIntent, PowerState, WorldView


class _Hittable(Protocol):
    """踩踏判定只依赖 body 的 AABB，测试桩也可传入。"""

    body: Body


class Player(Entity):
    kind = "player"

    def __init__(self, col: int, row: int, power: PowerState = PowerState.SMALL):
        super().__init__(0, 0, PLY_W_SMALL, PLY_H_SMALL)
        self.power = power
        self.body.x = col * TILE + (TILE - self.body.w) / 2
        self.body.y = (row + 1) * TILE - self.body.h
        if power is not PowerState.SMALL:
            self.apply_size()
        self.on_ground = False
        self.coyote_ms = 0.0
        self.buffer_ms = 0.0
        self.jump_vel = JUMP_VEL                  # 本次起跳的实际初速（含冲刺加成）
        self.invincible_ms = 0.0
        self.transform_ms = 0.0
        self.fire_cd_ms = 0.0
        self.stomp_chain = 0
        self.dead = False
        self.anim_state = AnimState.IDLE
        self.events: list[str] = []
        self.spawn_requests: list[tuple] = []     # ("fireball", x, y, dir)

    @property
    def is_big(self) -> bool:
        return self.power is not PowerState.SMALL

    # —— 几何 ——

    def apply_size(self) -> None:
        """切换体型时保持脚底不动、水平居中，避免变形后突然陷入地形或悬空。"""
        bottom = self.body.bottom
        w, h = ((PLY_W_BIG, PLY_H_BIG) if self.power is not PowerState.SMALL
                else (PLY_W_SMALL, PLY_H_SMALL))
        cx = self.body.x + self.body.w / 2
        self.body.w, self.body.h = w, h
        self.body.x = cx - w / 2
        self.body.y = bottom - h

    # —— 每步推进 ——

    def update(self, dt: float, intent: InputIntent, world: WorldView) -> Contacts:
        if self.dead:
            self._update_dead(dt)
            return Contacts()

        self._tick_timers(dt)
        self._horizontal(dt, intent)
        self._vertical(dt, intent)
        self._try_fire(intent)

        # 按下 ↓ 且为大体型时忽略单向平台（下穿）；小体型保持站立。
        drop = intent.down and self.power is not PowerState.SMALL
        contacts = move_and_collide(self.body, world.tilemap, dt, drop_through=drop)

        if contacts.ground:
            self.on_ground = True
            self.stomp_chain = 0
        elif self.body.vy > 0:
            self.on_ground = False
        # 走出平台边缘时 move_and_collide 不会报 ground，主动复核避免“悬空仍算在地面”。
        if self.on_ground and not standing_on(self.body, world.tilemap):
            self.on_ground = False

        # 土狼时间：离开地面后仍保留一小段可起跳窗口，手感更宽容。
        if self.on_ground:
            self.coyote_ms = COYOTE_MS
        else:
            self.coyote_ms = max(0.0, self.coyote_ms - dt * 1000)

        self._pick_anim(intent)
        return contacts

    def _tick_timers(self, dt: float) -> None:
        ms = dt * 1000
        self.invincible_ms = max(0.0, self.invincible_ms - ms)
        self.transform_ms = max(0.0, self.transform_ms - ms)
        self.fire_cd_ms = max(0.0, self.fire_cd_ms - ms)
        self.buffer_ms = max(0.0, self.buffer_ms - ms)
        self.anim_timer += dt

    def _horizontal(self, dt: float, intent: InputIntent) -> None:
        dir_in = (1 if intent.right else 0) - (1 if intent.left else 0)
        target = MAX_SPRINT if intent.sprint else MAX_WALK
        vx0 = self.body.vx
        # 已在当前上限之外（例如刚松开冲刺）：本步只回收、不再加速，
        # 否则「加速度 > 摩擦力」会让速度反而越滑越快，一直顶到冲刺上限。
        over_same_dir = abs(vx0) > target and vx0 * dir_in > 0

        if dir_in:
            self.facing = dir_in
            if over_same_dir:
                self.body.vx = vx0 - dir_in * FRICTION * dt
            else:
                if self.on_ground and vx0 * dir_in < 0:
                    acc = SKID_DEC                      # 反向输入先用更大的刹车加速度
                elif self.on_ground:
                    acc = SPRINT_ACC if intent.sprint else GROUND_ACC
                else:
                    acc = AIR_ACC
                self.body.vx = vx0 + dir_in * acc * dt
                # 本步加速撞上限时直接贴住；反向刹车时保留速度交给 SKID_DEC。
                if abs(self.body.vx) > target and self.body.vx * dir_in > 0:
                    self.body.vx = math.copysign(target, self.body.vx)
        else:
            if self.on_ground:
                self._decay(FRICTION * dt)               # 地面摩擦
            else:
                self._decay(FRICTION * 0.35 * dt)        # 空中阻力很小

        self.body.vx = max(-MAX_SPRINT, min(MAX_SPRINT, self.body.vx))

    def _decay(self, amount: float) -> None:
        if self.body.vx > 0:
            self.body.vx = max(0.0, self.body.vx - amount)
        elif self.body.vx < 0:
            self.body.vx = min(0.0, self.body.vx + amount)

    def _vertical(self, dt: float, intent: InputIntent) -> None:
        if intent.jump_pressed:
            self.buffer_ms = JUMP_BUFFER_MS
        # 起跳：有缓冲，且站在地面或仍处于土狼窗口内。
        if self.buffer_ms > 0 and (self.on_ground or self.coyote_ms > 0):
            # 冲刺加成：按起跳瞬间水平速度在 MAX_WALK～MAX_SPRINT 之间线性提升初速，
            # 走路/站立起跳仍是基础高度，只有真正跑起来才跳得更高。
            speed = abs(self.body.vx)
            ratio = min(1.0, max(0.0, (speed - MAX_WALK) / (MAX_SPRINT - MAX_WALK)))
            self.jump_vel = JUMP_VEL * (1.0 + JUMP_SPEED_BONUS * ratio)
            self.body.vy = -self.jump_vel
            self.on_ground = False
            self.coyote_ms = 0.0
            self.buffer_ms = 0.0
            self.events.append("jump")

        # 可变跳跃高度：松开跳跃键即裁剪上升速度；阈值按本次起跳初速缩放。
        if (not intent.jump_held) and self.body.vy < -self.jump_vel * JUMP_CUT:
            self.body.vy = -self.jump_vel * JUMP_CUT

        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)

    def _try_fire(self, intent: InputIntent) -> None:
        if not intent.fire_pressed:
            return
        if self.power is not PowerState.FIRE or self.fire_cd_ms > 0:
            return
        self.fire_cd_ms = FIRE_COOLDOWN_MS
        cx = self.body.x + self.body.w / 2
        cy = self.body.y + self.body.h * 0.4
        self.spawn_requests.append(("fireball", cx, cy, self.facing))
        self.events.append("fire")

    def _pick_anim(self, intent: InputIntent) -> None:
        if self.transform_ms > 0:
            self.anim_state = AnimState.GROW
        elif self.invincible_ms > 0:
            self.anim_state = AnimState.HURT
        elif not self.on_ground:
            self.anim_state = AnimState.JUMP if self.body.vy < 0 else AnimState.FALL
        elif intent.down and self.power is not PowerState.SMALL and abs(self.body.vx) < 1:
            self.anim_state = AnimState.CROUCH
        elif abs(self.body.vx) > 20 and (intent.left or intent.right):
            dir_in = (1 if intent.right else 0) - (1 if intent.left else 0)
            if self.body.vx * dir_in < 0:
                self.anim_state = AnimState.SKID
            else:
                self.anim_state = AnimState.RUN
        else:
            self.anim_state = AnimState.IDLE

    # —— 踩踏、受伤、变形、死亡 ——

    def can_stomp(self, enemy: _Hittable) -> bool:
        """玩家下落、脚底落在敌人上半身内，且水平重叠 ≥ 4 px（放宽擦边容错）。"""
        if self.body.vy <= 0:
            return False
        top = enemy.body.y
        if not (top - 12 <= self.body.bottom <= top + enemy.body.h * 0.6):
            return False
        ox = (min(self.body.x + self.body.w, enemy.body.x + enemy.body.w)
              - max(self.body.x, enemy.body.x))
        return ox >= 4

    def bounce(self) -> None:
        self.body.vy = -STOMP_BOUNCE
        self.on_ground = False
        self.coyote_ms = 0.0

    def hurt(self, _source: str = "contact") -> str:
        """返回结果：'none'（无敌/变形中） / 'shrink' / 'die'。"""
        if self.invincible_ms > 0 or self.transform_ms > 0:
            return "none"
        if self.power is PowerState.FIRE:
            self.power = PowerState.BIG
            self._enter_hurt()
            return "shrink"
        if self.power is PowerState.BIG:
            self.power = PowerState.SMALL
            self._enter_hurt()
            return "shrink"
        self.kill()
        return "die"

    def _enter_hurt(self) -> None:
        self.apply_size()
        self.invincible_ms = INVINCIBLE_MS
        self.transform_ms = TRANSFORM_MS
        self.events.append("hurt")

    def grow(self, to_fire: bool = False) -> bool:
        """吃道具：返回是否真的发生变化（用于计分）。"""
        if to_fire:
            if self.power is PowerState.FIRE:
                return False
            self.power = PowerState.FIRE
        else:
            if self.power is not PowerState.SMALL:
                return False
            self.power = PowerState.BIG
        self.apply_size()
        self.transform_ms = TRANSFORM_MS
        self.invincible_ms = max(self.invincible_ms, TRANSFORM_MS)
        self.events.append("grow")
        return True

    def kill(self) -> None:
        if self.dead:
            return
        self.dead = True
        self.anim_state = AnimState.DEAD
        self.anim_timer = 0.0
        self.body.vx = 0.0
        self.body.vy = -520.0
        self.events.append("death")

    def _update_dead(self, dt: float) -> None:
        self.anim_timer += dt
        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)
        self.body.y += self.body.vy * dt       # 死亡后忽略地形，直接落出画面


def push_out_of_tiles(body: Body, tmap) -> None:
    """体型变大后若与实心格重叠，逐格向上顶出（最多 3 格），避免卡进天花板。"""
    for _ in range(3):
        c0, c1, r0, r1 = span(body)
        hits = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                if tmap.solid(c, r)]
        if not hits:
            return
        body.y = min(r for r, _ in hits) * TILE - body.h - 0.01

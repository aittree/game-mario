"""关卡会话（docs/03 §6）。

应用层核心：加载关卡、生成实体、固定物理子步、相机、计分与生死流程。
本模块不 import pygame / audio / storage / ui，音效与存档由 main.py 消费事件后处理。
"""

from __future__ import annotations

import json
from enum import Enum, auto

from .camera import Camera
from .config import (
    CANVAS_W,
    CLEAR_SLIDE_MS,
    COINS_PER_LIFE,
    DEATH_MS,
    FIRE_MAX_ONSCREEN,
    FLITTER_AMP,
    FLITTER_PERIOD,
    GRAVITY,
    LIVES_START,
    MAX_FALL,
    RESPAWN_INVINCIBLE_MS,
    SCORE_BRICK,
    SCORE_BUMP,
    SCORE_CLEAR_FIXED,
    SCORE_COIN,
    SCORE_FIREKILL,
    TILE,
    TIME_START,
    TIME_TICK_MS,
    BRICK,
    QUESTION,
    stomp_score,
    time_to_score,
)
from .entities.base import AnimState, InputIntent, PowerState, WorldView
from .entities.enemies import Flitter, PatrolShroom, PipeBloom, Shellbug
from .entities.items import FireFlower, Fireball, Mushroom
from .entities.player import Player, push_out_of_tiles
from .entities.props import Checkpoint, Goal, MovingPlatform
from .physics import Body, overlap, span
from .tilemap import LevelError, TileMap


class SessionState(Enum):
    RUNNING = auto()
    DYING = auto()
    CLEARED = auto()
    FAILED = auto()


class GameEvent:
    """模型层单帧产生的事件，由 main.py 翻译成音效与特效。"""

    def __init__(self, kind: str, data: dict | None = None):
        self.kind = kind            # coin/stomp/brick_break/bump/powerup/powerdown/fire/death/checkpoint/oneup/clear/gameover/jump
        self.data = data


class _Knocked:
    """被火球/滑行壳击飞的敌人：上下翻转、弹起后掉出画面（纯表现，不参与碰撞）。"""
    is_knocked = True

    def __init__(self, kind: str, body: Body, direction: int):
        self.kind = kind
        self.body = Body(body.x, body.y, body.w, body.h)
        self.body.vx = direction * 70.0
        self.body.vy = -380.0
        self.facing = direction
        self.anim_state = AnimState.IDLE
        self.anim_frame = 0
        self.alive = True
        self.timer_ms = 1600.0

    def update(self, dt: float, max_y: float) -> None:
        self.timer_ms -= dt * 1000
        self.body.vy = min(self.body.vy + GRAVITY * dt, MAX_FALL)
        self.body.x += self.body.vx * dt
        self.body.y += self.body.vy * dt
        if self.timer_ms <= 0 or self.body.y > max_y:
            self.alive = False


class LevelSnapshot:
    """渲染层读取的只读快照。"""

    def __init__(self, tilemap: TileMap, theme: str,
                 player_x: float, player_y: float,
                 player_w: float, player_h: float,
                 player_power: PowerState, player_anim: AnimState,
                 player_frame: int, player_facing_left: bool,
                 player_invincible: bool, entities: list[tuple],
                 camera_x: float, score: int, coins: int, lives: int,
                 time_units: int, level_id: str, state: SessionState,
                 clear_bonus: int | None):
        self.tilemap = tilemap                 # 只读引用
        self.theme = theme
        self.player_x = player_x
        self.player_y = player_y
        self.player_w = player_w
        self.player_h = player_h
        self.player_power = player_power
        self.player_anim = player_anim
        self.player_frame = player_frame
        self.player_facing_left = player_facing_left
        self.player_invincible = player_invincible
        self.entities = entities               # (kind, x, y, w, h, anim_state, frame, facing, extra)
        self.camera_x = camera_x
        self.score = score
        self.coins = coins
        self.lives = lives
        self.time_units = time_units
        self.level_id = level_id
        self.state = state
        self.clear_bonus = clear_bonus


def spawn_entity(spec: dict):
    kind = spec["type"]
    col, row = spec["col"], spec["row"]
    if kind == "patrol_shroom":
        return PatrolShroom(col, row)
    if kind == "shellbug":
        return Shellbug(col, row)
    if kind == "flitter":
        return Flitter(col, row, spec.get("amp", FLITTER_AMP),
                       spec.get("period", FLITTER_PERIOD))
    if kind == "pipe_bloom":
        return PipeBloom(col, row)
    if kind == "moving_platform":
        return MovingPlatform(col, row, spec["path"], spec.get("speed", 90))
    if kind == "checkpoint":
        return Checkpoint(col, row)
    if kind == "goal":
        return Goal(col, row)
    return None            # 未知类型：忽略，不阻断加载


class LevelSession:
    def __init__(self, level_path: str, profile, lives: int = LIVES_START,
                 score: int = 0):
        self.level_path = level_path
        self.profile = profile
        self.lives = lives
        self.score = score
        self.coins = 0
        self.state = SessionState.RUNNING
        self.events: list[GameEvent] = []
        self.effects_hooks: list[tuple] = []
        self.death_ms = 0.0
        self.clear_ms = 0.0
        self.clear_bonus: int | None = None
        self.raw = self._load_raw()
        self.level_id = self.raw["id"]
        self.spawn_col, self.spawn_row = self.raw["spawn"]
        self.checkpoint = None
        self._oneup_marks = profile.coins_total // COINS_PER_LIFE
        self.enemies: list = []
        self.items: list = []
        self.fireballs: list[Fireball] = []
        self.knocked: list[_Knocked] = []
        self.shell_chain = 0
        self._build_world()

    def _load_raw(self) -> dict:
        try:
            with open(self.level_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as exc:
            raise LevelError(str(exc)) from exc

    @classmethod
    def from_dict(cls, data: dict, profile, lives: int = LIVES_START,
                  score: int = 0) -> "LevelSession":
        """测试与主循环共用的构造入口。"""
        self = cls.__new__(cls)
        self.level_path = None
        self.profile = profile
        self.lives = lives
        self.score = score
        self.coins = 0
        self.state = SessionState.RUNNING
        self.events = []
        self.effects_hooks = []
        self.death_ms = 0.0
        self.clear_ms = 0.0
        self.clear_bonus = None
        self.raw = data
        self.level_id = data.get("id", "test")
        self.spawn_col, self.spawn_row = data["spawn"]
        self.checkpoint = None
        self._oneup_marks = profile.coins_total // COINS_PER_LIFE
        self.enemies = []
        self.items = []
        self.fireballs = []
        self.knocked = []
        self.shell_chain = 0
        self._build_world()
        return self

    def _build_world(self) -> None:
        self.tilemap = TileMap.from_dict(self.raw)
        self.time_units = int(self.raw.get("time", TIME_START))
        self.time_acc = 0.0
        # 有检查点时从检查点重生，否则从关卡出生点开始
        if isinstance(self.checkpoint, tuple):
            spawn = self.checkpoint
        else:
            spawn = (self.spawn_col, self.spawn_row)
        self.player = Player(*spawn)
        self.player.invincible_ms = RESPAWN_INVINCIBLE_MS if self.checkpoint else 0
        self.enemies, self.items, self.props = [], [], []
        for spec in self.raw.get("entities", []):
            ent = spawn_entity(spec)
            if ent is None:
                continue
            if isinstance(ent, (PatrolShroom, Shellbug, Flitter, PipeBloom)):
                self.enemies.append(ent)
            elif isinstance(ent, (MovingPlatform, Checkpoint, Goal)):
                self.props.append(ent)
        self.fireballs = []
        self.knocked: list[_Knocked] = []
        self.shell_chain = 0
        self.goal = next((p for p in self.props if isinstance(p, Goal)), None)
        if not hasattr(self, "camera"):             # 重载时复用，保留旧关卡宽度无影响
            self.camera = Camera(self.tilemap.width_px)
        else:
            self.camera.level_width = self.tilemap.width_px
            self.camera.max_x = max(0, self.tilemap.width_px - CANVAS_W)
        self.camera.snap_to(self.player.body.x)

    # —— 固定步长推进 ——

    def step(self, intent: InputIntent, dt: float) -> None:
        """dt 恒为 PHYSICS_DT；所有时间与物理推进都在这里。"""
        if self.state is SessionState.FAILED:
            return
        if self.state is SessionState.DYING:
            self._step_dying(dt)
            return
        if self.state is SessionState.CLEARED:
            self._step_clear(dt)
            return

        world = WorldView(self.tilemap, self.camera.x,
                          self.player.body.x, self.tilemap.width_px)

        # 1. 玩家
        contacts = self.player.update(dt, intent, world, len(self.fireballs))
        self._drain_player_output()
        for col, row in contacts.head_tiles:
            self.handle_bump(col, row)

        # 2. 敌人
        for e in self.enemies:
            if not e.alive:
                continue
            if not e.active and e.body.x < self.camera.x + 32 * TILE + 200:
                e.active = True
            e.update(dt, world)

        # 3. 道具
        for i in self.items:
            if i.alive:
                i.update(dt, world)

        # 4. 火球（位移、弹跳、寿命；此前漏更新，导致火球原地驻留）
        for f in self.fireballs:
            if f.alive:
                f.update(dt, world)

        # 4.5 被火球/滑行壳击飞的敌人：翻倒弹起后掉出画面（纯表现）
        for k in self.knocked:
            if k.alive:
                k.update(dt, self.tilemap.height_px + 200)

        # 5. 平台载人（先于接触结算）
        self._update_props(dt, world)

        # 6. 接触结算
        self._resolve_player_tiles()
        self._resolve_entities()
        self._resolve_fireballs()

        # 7. 计时与镜头
        self._tick_time(dt)
        self.camera.follow(self.player.body.x, dt)

        # 7. 死亡与通关判定
        if self.player.body.y > self.tilemap.height_px + 200:
            self.player.kill()
        if self.player.dead and self.state is SessionState.RUNNING:
            self.state = SessionState.DYING
            self.death_ms = 0.0
        if self.goal and self.goal.touched and self.state is SessionState.RUNNING:
            self._begin_clear()

        # 8. 清理已消失的实体，避免快照里出现幽灵精灵
        self.enemies = [e for e in self.enemies if e.alive]
        self.items = [i for i in self.items if i.alive]
        self.fireballs = [f for f in self.fireballs if f.alive]
        self.knocked = [k for k in self.knocked if k.alive]

    # —— 接触结算 ——

    def _resolve_player_tiles(self) -> None:
        c0, c1, r0, r1 = span(self.player.body)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if self.tilemap.coin(c, r):
                    self.tilemap.take_coin(c, r)
                    self._add_coin(1)
                elif self.tilemap.hazard(c, r):
                    # 尖刺图形只占格内下方 28 px，脚底未进入可视尖刺高度不算受伤
                    if self.player.body.bottom > r * TILE + (TILE - 28):
                        self._player_hurt("hazard")

    @staticmethod
    def _can_kick_shell(enemy) -> bool:
        """侧面碰到静止的壳时可踢出（受伤无敌期间同样可踢）。"""
        return isinstance(enemy, Shellbug) and enemy.state == "shell_idle"

    def _resolve_entities(self) -> None:
        player = self.player
        for e in self.enemies:
            if not e.alive:
                continue
            if getattr(e, "squash_ms", 0.0) > 0:
                continue                      # 已被踩扁，等待消失，不再参与碰撞与计分
            touching = overlap(player.body, e.body)
            if isinstance(e, Shellbug) and e.kick_grace and not touching:
                e.kick_grace = False          # 壳已与玩家分离，恢复常规判定
            if not touching:
                continue
            if isinstance(e, Shellbug) and e.kick_grace:
                continue                      # 刚踢出的壳尚未离开玩家，不结算伤害
            was_shell_idle = isinstance(e, Shellbug) and e.state == "shell_idle"
            if player.can_stomp(e) and e.on_stomp():
                if was_shell_idle:
                    e.kick(player.facing)     # 踩静止壳：按玩家朝向把它踢出去
                player.bounce()
                # 把脚底贴到敌人头顶：否则弹起后的下一帧仍然重叠，
                # can_stomp 因 vy<0 返回 False，会被同一只敌人判定为受伤。
                player.body.y = e.body.y - player.body.h - 0.01
                self.score += stomp_score(player.stomp_chain)
                player.stomp_chain += 1
                self.events.append(GameEvent("stomp", {"kind": e.kind, "cells": e.aabb}))
            elif self._can_kick_shell(e):
                e.kick(1 if e.body.x > player.body.x else -1)
                self.events.append(GameEvent("stomp", {"kind": "shell_kick", "cells": e.aabb}))
            else:
                self._player_hurt("enemy")

        # 滑行壳撞其它敌人
        if not any(isinstance(e, Shellbug) and e.state == "shell_slide"
                   for e in self.enemies):
            self.shell_chain = 0              # 没有滑行壳时重置连击
        for shell in (e for e in self.enemies
                      if isinstance(e, Shellbug) and e.state == "shell_slide"):
            for other in self.enemies:
                if other is shell or not other.alive or not overlap(shell.body, other.body):
                    continue
                if isinstance(other, PipeBloom) and not other.visible:
                    continue                  # 隐藏的水管花不应被隔空击杀
                self._knock_enemy(other, shell.dir)
                self.score += stomp_score(self.shell_chain)
                self.shell_chain += 1
                self.events.append(GameEvent("stomp", {"kind": other.kind, "cells": other.aabb}))
                self.score += SCORE_FIREKILL
                self.events.append(GameEvent("stomp", {"kind": other.kind, "cells": other.aabb}))

        # 道具拾取
        for item in self.items:
            if not item.alive or item.emerge_ms > 0 or not overlap(player.body, item.body):
                continue
            item.alive = False
            changed = player.grow(to_fire=isinstance(item, FireFlower))
            self.score += 100 if not changed else 0
            self.events.append(GameEvent("powerup", {"type": item.kind}))
            push_out_of_tiles(player.body, self.tilemap)

        # 检查点与终点
        for p in self.props:
            if isinstance(p, Checkpoint) and overlap(player.body, p.body) and p.touch():
                col = int((p.body.x + p.body.w / 2) // TILE)
                self.checkpoint = (col, int(p.body.bottom // TILE) - 1)
                self.events.append(GameEvent("checkpoint"))
            if isinstance(p, Goal) and overlap(player.body, p.body):
                p.touch()   # 终点由 step 末尾统一触发，避免这里重复结算

    def _knock_enemy(self, enemy, direction: int) -> None:
        """把敌人替换为「翻倒弹起掉落」的表现实体，并标记死亡（SMB1 的击飞表现）。"""
        self.knocked.append(_Knocked(enemy.kind, enemy.body, direction))
        enemy.alive = False

    def _resolve_fireballs(self) -> None:
        for ball in self.fireballs:
            if not ball.alive:
                continue
            for e in self.enemies:
                if not e.alive or not overlap(ball.body, e.body):
                    continue
                direction = 1 if ball.body.vx >= 0 else -1
                self._knock_enemy(e, direction)
                ball.alive = False
                self.score += SCORE_FIREKILL
                self.events.append(GameEvent("firekill", {"kind": e.kind, "cells": e.aabb}))
                break

    def _player_hurt(self, source: str) -> None:
        result = self.player.hurt(source)
        if result == "shrink":
            self.events.append(GameEvent("powerdown"))
        elif result == "die":
            self.state = SessionState.DYING
            self.death_ms = 0.0

    def _update_props(self, dt: float, world: WorldView) -> None:
        for p in self.props:
            if not isinstance(p, MovingPlatform):
                continue
            p.update(dt, world)
            # 玩家站在平台顶面上时随平台横移（垂直位移交给地形解算处理）
            if (self.player.on_ground
                    and abs(self.player.body.bottom - p.body.y) <= 4
                    and self.player.body.x + self.player.body.w > p.body.x
                    and self.player.body.x < p.body.x + p.body.w):
                self.player.body.x += p.dx

    # —— 死亡、重生、通关 ——

    def _step_dying(self, dt: float) -> None:
        self.death_ms += dt * 1000
        self.player.update(dt, InputIntent(),
                           WorldView(self.tilemap, 0, 0, self.tilemap.width_px))
        self._drain_player_events()      # 死亡事件在进入 DYING 前产生，必须在这里消费
        if self.death_ms < DEATH_MS:
            return
        self.lives -= 1
        if self.lives <= 0:
            self.state = SessionState.FAILED
            self.events.append(GameEvent("gameover"))
            return
        self.state = SessionState.RUNNING
        self._build_world()                      # 整关重载：地形/敌人/金币全部复位
        self.player.invincible_ms = RESPAWN_INVINCIBLE_MS
        self.camera.snap_to(self.player.body.x)

    def _begin_clear(self) -> None:
        self.state = SessionState.CLEARED
        self.clear_ms = 0.0
        self.player.body.vx = 0
        self.player.body.vy = 0
        bonus = SCORE_CLEAR_FIXED + time_to_score(self.time_units)
        self.score += bonus
        self.clear_bonus = bonus
        self.events.append(GameEvent("clear", {"bonus": bonus, "time": self.time_units,
                                               "coins": self.coins}))

    def _step_clear(self, dt: float) -> None:
        self.clear_ms += dt * 1000
        if self.clear_ms <= CLEAR_SLIDE_MS:            # 沿杆下滑
            if self.goal:
                limit = self.goal.body.y + self.goal.body.h - self.player.body.h
                self.player.body.y = min(self.player.body.y + 120 * dt, limit)
                self.goal.flag_y = min(1.0, self.clear_ms / CLEAR_SLIDE_MS)

    # —— 计分、时间、顶砖 ——

    def _add_coin(self, n: int) -> None:
        self.coins += n
        self.score += SCORE_COIN * n
        self.profile.coins_total += n
        self.events.append(GameEvent("coin"))
        if self.profile.coins_total // COINS_PER_LIFE > self._oneup_marks:
            self._oneup_marks += 1
            self.lives += 1
            self.events.append(GameEvent("oneup"))

    def _drain_player_events(self) -> None:
        for name in self.player.events:
            self.events.append(GameEvent(name))
        self.player.events.clear()

    def _drain_player_output(self) -> None:
        self._drain_player_events()
        for req in self.player.spawn_requests:
            if req[0] == "fireball" and len(self.fireballs) < FIRE_MAX_ONSCREEN:
                self.fireballs.append(Fireball(req[1], req[2], req[3]))
        self.player.spawn_requests.clear()

    def _tick_time(self, dt: float) -> None:
        self.time_acc += dt * 1000
        while self.time_acc >= TIME_TICK_MS:
            self.time_acc -= TIME_TICK_MS
            if self.time_units > 0:
                self.time_units -= 1
        if self.time_units <= 0 and not self.player.dead:
            self.player.kill()
            self.state = SessionState.DYING
            self.death_ms = 0.0

    def handle_bump(self, col: int, row: int) -> None:
        tile = self.tilemap.tile_at(col, row)
        if tile == BRICK:
            if self.player.power is PowerState.SMALL:
                self.effects_hooks.append(("bump", (col, row)))
                self.events.append(GameEvent("bump"))
            else:
                self.tilemap.remove(col, row)
                self.score += SCORE_BRICK
                self.effects_hooks.append(("brick", (col, row)))
                self.events.append(GameEvent("brick_break"))
        elif tile == QUESTION:
            self.tilemap.use_question(col, row)
            self.score += SCORE_BUMP
            self._release_item(col, row)
            self.effects_hooks.append(("bump", (col, row)))
            self.events.append(GameEvent("bump"))
        else:
            self.events.append(GameEvent("bump", {"solid": True}))

    def _release_item(self, col: int, row: int) -> None:
        kind = self.raw.get("items", {}).get(f"{col},{row}", "coin")
        if kind == "coin":
            self._add_coin(1)
            self.effects_hooks.append(("coin_pop", (col, row)))
        elif kind == "mushroom":
            self.items.append(Mushroom(col, row))
        elif kind == "flower":
            self.items.append(FireFlower(col, row))

    # —— 对外 ——

    def take_events(self) -> list[GameEvent]:
        events, self.events = self.events, []
        return events

    def snapshot(self) -> LevelSnapshot:
        player = self.player
        entities: list[tuple] = []
        for ent in (*self.enemies, *self.items, *self.props, *self.fireballs,
                    *self.knocked):
            entities.append((ent.kind, ent.body.x, ent.body.y, ent.body.w, ent.body.h,
                             ent.anim_state, ent.anim_frame, ent.facing,
                             self._entity_extra(ent)))
        return LevelSnapshot(
            self.tilemap,
            theme=self.tilemap.theme,
            player_x=player.body.x,
            player_y=player.body.y,
            player_w=player.body.w,
            player_h=player.body.h,
            player_power=player.power,
            player_anim=player.anim_state,
            player_frame=0,
            player_facing_left=player.facing < 0,
            player_invincible=player.invincible_ms > 0,
            entities=entities,
            camera_x=self.camera.x,
            score=self.score,
            coins=self.coins,
            lives=self.lives,
            time_units=self.time_units,
            level_id=self.level_id,
            state=self.state,
            clear_bonus=self.clear_bonus,
        )

    @staticmethod
    def _entity_extra(ent) -> dict | None:
        """表现层需要的少量只读状态；模型逻辑不依赖它。"""
        if getattr(ent, "is_knocked", False):
            return {"dir": ent.facing, "flip": True}
        kind = ent.kind
        if kind == "shellbug":
            return {"dir": ent.dir, "state": ent.state}
        if kind in ("patrol_shroom", "flitter"):
            return {"dir": ent.dir, "squash": ent.squash_ms > 0}
        if kind == "pipe_bloom":
            return {"visible": ent.visible}
        if kind == "checkpoint":
            return {"raised": ent.raised}
        return None

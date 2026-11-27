"""玩家状态机测试（docs/05 §2.3 UT-P-01～UT-P-14）。

只依赖模型层：不需要显示设备，也不 import pygame。
`update()` 内部已包含 move_and_collide，测试按会话的调用方式每步只调一次。
"""

import pytest

from src.config import INVINCIBLE_MS, MAX_SPRINT, MAX_WALK, PHYSICS_DT, TILE
from src.entities.base import AnimState, InputIntent, PowerState, WorldView
from src.entities.player import Player
from src.physics import Body
from src.tilemap import TileMap

ROWS, COLS = 18, 60
GROUND_ROW = 17


def make_tmap(gaps: tuple[int, ...] = ()) -> TileMap:
    """第 17 行整行地面；gaps 中的列挖空，用于制造平台边缘。"""
    grid = ["." * COLS for _ in range(ROWS)]
    grid[GROUND_ROW] = "".join("." if c in gaps else "#" for c in range(COLS))
    return TileMap.from_dict({
        "id": "t", "name": "测试", "theme": "grass",
        "cols": COLS, "rows": ROWS, "time": 300,
        "spawn": [2, 16], "tiles": grid, "items": {}, "entities": [],
    })


def world(tmap: TileMap) -> WorldView:
    return WorldView(tmap, 0.0, 0.0, tmap.width_px)


def run(player: Player, intent: InputIntent, tmap: TileMap, steps: int) -> None:
    for _ in range(steps):
        player.update(PHYSICS_DT, intent, world(tmap))


def settled(tmap: TileMap, power: PowerState = PowerState.SMALL) -> Player:
    player = Player(2, 16, power)
    run(player, InputIntent(), tmap, 1)      # 落到地面，on_ground 变 True
    return player


def jump_height(player: Player, tmap: TileMap, hold_steps: int) -> float:
    """起跳后返回最大上升高度（px）。hold_steps=1 表示轻按后立即松开。"""
    start = player.body.y
    peak = start
    for i in range(120):
        intent = InputIntent(jump_held=i < hold_steps)
        player.update(PHYSICS_DT, intent, world(tmap))
        peak = min(peak, player.body.y)
    return start - peak


class Dummy:
    """只提供 body 的假敌人，用于踩踏判定。"""

    def __init__(self, x: float, y: float, w: float = 36, h: float = 36):
        self.body = Body(x, y, w, h)


# —— UT-P-01～04 水平手感 ——

def test_walk_speed_cap():
    tmap = make_tmap()
    player = settled(tmap)
    run(player, InputIntent(right=True), tmap, 30)
    assert player.body.vx == pytest.approx(MAX_WALK, abs=1.0)


def test_release_stops_in_about_20ms():
    tmap = make_tmap()
    player = settled(tmap)
    run(player, InputIntent(right=True), tmap, 30)
    run(player, InputIntent(), tmap, 30)          # 0.25 s > 0.2 s
    assert player.body.vx == 0.0


def test_sprint_speed_cap():
    tmap = make_tmap()
    player = settled(tmap)
    run(player, InputIntent(right=True, sprint=True), tmap, 40)
    assert player.body.vx == pytest.approx(MAX_SPRINT, abs=1.0)
    assert player.body.vx <= MAX_SPRINT


def test_skid_when_turning():
    tmap = make_tmap()
    player = settled(tmap)
    run(player, InputIntent(right=True), tmap, 30)
    before = player.body.vx
    player.update(PHYSICS_DT, InputIntent(left=True), world(tmap))
    assert 0 < player.body.vx < before          # 先减速，未瞬间反向
    assert player.anim_state is AnimState.SKID
    run(player, InputIntent(left=True), tmap, 20)
    assert player.body.vx < 0                   # 平滑过零


# —— UT-P-05～06 可变跳跃高度 ——

def test_short_hop_height():
    tmap = make_tmap()
    player = settled(tmap)
    player.update(PHYSICS_DT, InputIntent(jump_pressed=True, jump_held=True),
                  world(tmap))
    height = jump_height(player, tmap, hold_steps=0)
    assert 1.5 * TILE <= height <= 2.5 * TILE


def test_full_jump_height():
    tmap = make_tmap()
    player = settled(tmap)
    player.update(PHYSICS_DT, InputIntent(jump_pressed=True, jump_held=True),
                  world(tmap))
    height = jump_height(player, tmap, hold_steps=120)
    assert 3.5 * TILE <= height <= 4.6 * TILE


def test_death_air_hold_before_falling():
    """死亡后先在空中暂留，再上弹坠落。"""
    tmap = make_tmap()
    player = Player(2, 16)
    player.kill()
    y0 = player.body.y
    run(player, InputIntent(), tmap, 30)      # 0.25s，仍在暂留期
    assert player.body.y == pytest.approx(y0)
    run(player, InputIntent(), tmap, 30)      # 越过暂留：应上弹（y 变小）
    assert player.body.y < y0


def test_sprint_jump_is_higher():
    """满冲刺起跳比站立起跳高约一格（JUMP_SPEED_BONUS=0.12）。"""
    tmap = make_tmap()
    player = settled(tmap)
    run(player, InputIntent(right=True, sprint=True), tmap, 40)
    assert player.body.vx == pytest.approx(MAX_SPRINT, abs=1.0)
    player.update(PHYSICS_DT, InputIntent(jump_pressed=True, jump_held=True),
                  world(tmap))
    height = jump_height(player, tmap, hold_steps=120)
    assert 4.5 * TILE <= height <= 5.5 * TILE


# —— UT-P-07～09 土狼时间与跳跃缓冲 ——

def _walk_off_edge(tmap: TileMap) -> Player:
    """站到平台右边缘并走出，返回刚离地的那一帧。"""
    player = settled(tmap)
    guard = 0
    while player.on_ground and guard < 300:
        player.update(PHYSICS_DT, InputIntent(right=True), world(tmap))
        guard += 1
    assert not player.on_ground
    return player


def test_jump_within_coyote_window():
    tmap = make_tmap(gaps=tuple(range(6, COLS)))
    player = _walk_off_edge(tmap)
    run(player, InputIntent(right=True), tmap, 4)    # 离地约 42 ms，仍在窗口内
    player.update(PHYSICS_DT, InputIntent(jump_pressed=True, jump_held=True),
                  world(tmap))
    assert player.body.vy < 0


def test_jump_after_coyote_expires():
    tmap = make_tmap(gaps=tuple(range(6, COLS)))
    player = _walk_off_edge(tmap)
    run(player, InputIntent(right=True), tmap, 24)   # 约 200 ms，窗口已过期
    player.update(PHYSICS_DT, InputIntent(jump_pressed=True, jump_held=True),
                  world(tmap))
    assert player.body.vy > 0                        # 仍在自由下落，未起跳


def test_jump_buffer_triggers_on_landing():
    tmap = make_tmap()
    player = Player(10, 16)
    player.body.y = GROUND_ROW * TILE - player.body.h - 30
    player.body.vy = 500.0
    player.on_ground = False
    player.update(PHYSICS_DT, InputIntent(jump_pressed=True, jump_held=True),
                  world(tmap))
    jumped = False
    for _ in range(20):                              # 130 ms 窗口内落地并起跳
        player.update(PHYSICS_DT, InputIntent(jump_held=True), world(tmap))
        if player.body.vy < 0:
            jumped = True
            break
    assert jumped


# —— UT-P-10～11 踩踏判定 ——

def test_can_stomp_when_falling_onto_head():
    player = Player(2, 16)
    enemy = Dummy(100.0, 500.0)
    player.body.x = 100.0
    player.body.y = enemy.body.y + 8 - player.body.h
    player.body.vy = 300.0
    assert player.can_stomp(enemy) is True


def test_cannot_stomp_while_rising():
    player = Player(2, 16)
    enemy = Dummy(100.0, 500.0)
    player.body.x = 100.0
    player.body.y = enemy.body.y + 8 - player.body.h
    player.body.vy = -300.0
    assert player.can_stomp(enemy) is False


# —— UT-P-12～14 受伤与变形 ——

def test_small_hurt_dies():
    player = Player(2, 16)
    assert player.hurt() == "die"
    assert player.dead is True


def test_big_hurt_shrinks_and_gets_invincible():
    player = Player(2, 16, PowerState.BIG)
    assert player.hurt() == "shrink"
    assert player.power is PowerState.SMALL
    assert player.invincible_ms == pytest.approx(INVINCIBLE_MS)
    assert player.hurt() == "none"                  # 无敌期内不再掉级


def test_fire_hurt_steps_down_one_level():
    player = Player(2, 16, PowerState.FIRE)
    assert player.hurt() == "shrink"
    assert player.power is PowerState.BIG
    player.invincible_ms = 0.0                      # 跳过无敌，验证下一级
    player.transform_ms = 0.0
    assert player.hurt() == "shrink"
    assert player.power is PowerState.SMALL
    player.invincible_ms = 0.0
    player.transform_ms = 0.0
    assert player.hurt() == "die"

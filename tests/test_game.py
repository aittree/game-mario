"""会话测试（docs/05 §2.4 UT-G-01～UT-G-16）。

人造 18×20 关卡，不需要显示设备；step 的 dt 固定为 PHYSICS_DT。
"""

import pytest

from src.config import PHYSICS_DT, RESPAWN_INVINCIBLE_MS, SCORE_FIREKILL, TILE
from src.entities.base import InputIntent, PowerState
from src.entities.enemies import Shellbug
from src.entities.items import Mushroom
from src.game import LevelSession, SessionState
from src.storage import Profile

ROWS, COLS = 18, 20
GROUND_ROW = 17
DT = PHYSICS_DT


def make_tiles(ground: bool = True, coins: tuple[tuple[int, int], ...] = ()) -> list[str]:
    rows = ["." * COLS for _ in range(ROWS)]
    if ground:
        rows[GROUND_ROW] = "#" * COLS
    for col, row in coins:
        line = list(rows[row])
        line[col] = "c"
        rows[row] = "".join(line)
    return rows


def make_session(tiles=None, spawn=(2, 16), entities=None, items=None,
                 profile=None, lives=3) -> LevelSession:
    tiles = tiles if tiles is not None else make_tiles()
    data = {
        "id": "test", "name": "测试", "theme": "grass",
        "cols": len(tiles[0]), "rows": len(tiles),
        "time": 300, "spawn": list(spawn), "tiles": tiles,
        "entities": entities or [], "items": items or {},
    }
    return LevelSession.from_dict(data, profile or Profile(), lives)


def step(session: LevelSession, intent: InputIntent, n: int = 1) -> None:
    for _ in range(n):
        session.step(intent, DT)


def shroom(col: int, row: int = 16) -> dict:
    return {"type": "patrol_shroom", "col": col, "row": row}


def place_above(player, target) -> None:
    """把玩家放到目标敌人头顶（脚底进入可踩带），并给一个下落速度。"""
    player.body.x = target.body.x
    player.body.y = target.body.y + 6 - player.body.h
    player.body.vy = 200.0
    player.on_ground = False


def event_kinds(session: LevelSession) -> list[str]:
    return [e.kind for e in session.take_events()]


# —— UT-G-01～03 加载与静止 ——

def test_load_entities_and_stand_on_ground():
    session = make_session(entities=[
        shroom(6),
        {"type": "checkpoint", "col": 8, "row": 16},
        {"type": "goal", "col": 12, "row": 16},
    ])
    assert len(session.enemies) == 1
    assert len(session.props) == 2
    assert session.goal is not None
    assert session.player.body.bottom == pytest.approx(GROUND_ROW * TILE)


def test_idle_one_second_no_sink_no_drift():
    session = make_session()
    x0, y0 = session.player.body.x, session.player.body.y
    step(session, InputIntent(), 120)
    assert session.player.body.x == pytest.approx(x0)
    assert session.player.body.y == pytest.approx(y0)


def test_long_run_no_accumulated_error():
    session = make_session()
    bottom0 = session.player.body.bottom
    step(session, InputIntent(), 600)
    assert abs(session.player.body.bottom - bottom0) <= 2
    assert session.player.body.x == pytest.approx(87.0)      # 2*40 + (40-26)/2


# —— UT-G-04～08 踩踏、连击、火球 ——

def test_stomp_shroom_scores_and_removes_it():
    session = make_session(entities=[shroom(6)])
    place_above(session.player, session.enemies[0])
    session.step(InputIntent(), DT)
    assert session.score == 100
    assert session.player.stomp_chain == 1
    assert session.player.body.vy < 0
    assert "stomp" in event_kinds(session)
    step(session, InputIntent(), 50)                        # 等待 squash（350ms）结束
    assert session.enemies == []


def test_stomp_chain_scores_100_then_200():
    session = make_session(entities=[shroom(6), shroom(9)])
    place_above(session.player, session.enemies[0])
    session.step(InputIntent(), DT)
    place_above(session.player, session.enemies[1])
    session.step(InputIntent(), DT)
    assert session.score == 300
    assert session.player.stomp_chain == 2


def test_stomp_chain_resets_after_landing():
    session = make_session(entities=[shroom(6), shroom(9), shroom(13)])
    place_above(session.player, session.enemies[0])
    session.step(InputIntent(), DT)
    place_above(session.player, session.enemies[1])
    session.step(InputIntent(), DT)
    for _ in range(240):                                    # 落回地面
        session.step(InputIntent(), DT)
        if session.player.on_ground:
            break
    assert session.player.on_ground
    assert session.player.stomp_chain == 0
    place_above(session.player, session.enemies[0])
    session.step(InputIntent(), DT)
    assert session.score == 400                             # 300 + 重新从 100 起


def test_fireball_kills_shroom():
    session = make_session(entities=[shroom(8)])
    session.player.power = PowerState.FIRE
    session.player.spawn_requests.append(
        ("fireball", session.enemies[0].body.x + 10, session.enemies[0].body.y + 18, 1))
    session.step(InputIntent(), DT)                         # 生成火球
    step(session, InputIntent(), 2)
    assert session.enemies == []
    assert session.score >= SCORE_FIREKILL


def test_fireball_cooldown_and_onscreen_cap():
    session = make_session()
    session.player.power = PowerState.FIRE
    session.step(InputIntent(fire_pressed=True), DT)
    assert len(session.fireballs) == 1
    session.step(InputIntent(fire_pressed=True), DT)        # 冷却期内
    assert len(session.fireballs) == 1
    session.player.fire_cd_ms = 0.0
    session.step(InputIntent(fire_pressed=True), DT)
    assert len(session.fireballs) == 2
    session.player.fire_cd_ms = 0.0
    session.step(InputIntent(fire_pressed=True), DT)        # 屏上已达上限
    assert len(session.fireballs) == 2


# —— UT-G-09～11 顶砖 ——

def _bump_session(power: PowerState = PowerState.SMALL, items=None) -> LevelSession:
    tiles = make_tiles()
    line = list(tiles[14])
    line[4] = "B"
    tiles[14] = "".join(line)
    session = make_session(tiles, spawn=(4, 16), items=items)
    if power is not PowerState.SMALL:
        session.player.power = power
        session.player.apply_size()
        session.player.body.y = GROUND_ROW * TILE - session.player.body.h
    return session


def test_small_bump_keeps_brick():
    session = _bump_session()
    for _ in range(480):
        session.step(InputIntent(jump_held=True, jump_pressed=True), DT)
        if "bump" in event_kinds(session):
            break
    assert session.tilemap.tile_at(4, 14) == "B"
    assert session.score == 0


def test_big_bump_breaks_brick():
    session = _bump_session(PowerState.BIG)
    broke = False
    for _ in range(480):
        session.step(InputIntent(jump_held=True, jump_pressed=True), DT)
        if "brick_break" in event_kinds(session):
            broke = True
            break
    assert broke
    assert session.tilemap.tile_at(4, 14) == "."
    assert session.score >= 50


def test_question_block_releases_mushroom():
    tiles = make_tiles()
    line = list(tiles[14])
    line[4] = "?"
    tiles[14] = "".join(line)
    session = make_session(tiles, spawn=(4, 16), items={"4,14": "mushroom"})
    for _ in range(480):
        session.step(InputIntent(jump_held=True, jump_pressed=True), DT)
        if "bump" in event_kinds(session):
            break
    assert session.tilemap.tile_at(4, 14) == "X"
    assert session.score == 50
    assert any(i.kind == "mushroom" for i in session.items)


def test_mushroom_moves_right_after_emerging():
    """顶出后应升到砖顶再向右走，而不是卡在实心砖里被弹向左。"""
    tiles = make_tiles()
    line = list(tiles[14])
    line[4:11] = "X" * 7               # 一段实心砖平台，蘑菇从最左格升起
    tiles[14] = "".join(line)
    session = make_session(tiles, spawn=(2, 16))
    session.items.append(Mushroom(4, 14))
    mushroom = session.items[-1]
    for _ in range(120):               # 0.4 s 升起 + 0.6 s 行走
        session.step(InputIntent(), DT)
    assert mushroom.dir == 1
    assert mushroom.body.x > 4 * TILE + 4


def test_stomp_idle_shell_launches_it():
    """踩静止壳应把它踢出去（按玩家朝向），而不是原地反复弹跳。"""
    session = make_session(make_tiles(), spawn=(2, 16))
    shell = Shellbug(3, 16)
    shell.state = "shell_idle"
    shell.body.h = 24
    shell.body.y += 10
    session.enemies.append(shell)
    player = session.player
    player.body.x = shell.body.x
    player.body.y = shell.body.y - player.body.h + 2   # 轻微压入壳顶，确保 AABB 重叠
    player.body.vy = 120.0
    session.step(InputIntent(), DT)
    assert shell.state == "shell_slide"
    assert shell.dir == player.facing


# —— UT-G-12～13 金币 ——

def test_coin_collect():
    session = make_session(make_tiles(coins=((2, 16),)))
    session.step(InputIntent(), DT)
    assert session.coins == 1
    assert session.score == 100
    assert session.tilemap.tile_at(2, 16) == "."


def test_hundredth_coin_gives_extra_life():
    profile = Profile(coins_total=99)
    session = make_session(make_tiles(coins=((2, 16),)), profile=profile)
    session.step(InputIntent(), DT)
    assert session.lives == 4
    assert "oneup" in event_kinds(session)


# —— UT-G-14～16 死亡、检查点、通关 ——

def test_fall_out_then_respawn():
    session = make_session(make_tiles(ground=False), spawn=(2, 0))
    for _ in range(600):
        session.step(InputIntent(), DT)
        if session.state is SessionState.DYING:
            break
    assert session.state is SessionState.DYING
    for _ in range(300):
        session.step(InputIntent(), DT)
        if session.state is SessionState.RUNNING:
            break
    assert session.state is SessionState.RUNNING
    assert session.lives == 2
    assert session.player.body.bottom == pytest.approx(TILE)
    assert session.player.invincible_ms == pytest.approx(RESPAWN_INVINCIBLE_MS)


def test_checkpoint_respawn_restores_tiles():
    tiles = make_tiles(coins=((4, 16),))
    session = make_session(tiles, entities=[{"type": "checkpoint", "col": 6, "row": 16}])
    checkpoint = session.props[0]
    session.player.body.x = checkpoint.body.x
    session.step(InputIntent(), DT)
    assert session.checkpoint == (6, 16)

    session.player.body.x = 4 * TILE                        # 去吃金币
    session.step(InputIntent(), DT)
    assert session.coins == 1

    session.player.kill()
    session.step(InputIntent(), DT)
    assert session.state is SessionState.DYING
    for _ in range(300):
        session.step(InputIntent(), DT)
        if session.state is SessionState.RUNNING:
            break
    assert session.state is SessionState.RUNNING
    assert session.player.body.x == pytest.approx(6 * TILE + 7)
    assert session.tilemap.tile_at(4, 16) == "c"            # 地形与金币复位


def test_goal_triggers_clear_bonus():
    session = make_session(entities=[{"type": "goal", "col": 10, "row": 16}])
    assert session.goal is not None
    session.player.body.x = session.goal.body.x
    session.step(InputIntent(), DT)
    assert session.state is SessionState.CLEARED
    bonus = session.clear_bonus or 0
    assert bonus == 1000 + 10 * 300
    assert session.score >= bonus

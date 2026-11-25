"""physics 单元测试（docs/05 §2.1 UT-F-01～UT-F-12）。

全部使用 40 px 瓦片、1/120 s 物理步长，不依赖 pygame 与显示设备。
"""

from collections.abc import Mapping
from typing import Any

import pytest

from src.config import PHYSICS_DT, TILE
from src.physics import Body, move_and_collide, overlap, standing_on
from src.tilemap import TileMap

ROWS, COLS = 18, 20


def make_tmap(cells: Mapping[Any, str]) -> TileMap:
    """按 (col,row) 放置图块，其余为空。"""
    grid = ["." * COLS for _ in range(ROWS)]
    for (col, row), code in cells.items():
        line = list(grid[row])
        line[col] = code
        grid[row] = "".join(line)
    return TileMap.from_dict({
        "id": "t", "name": "测试", "theme": "grass",
        "cols": COLS, "rows": ROWS, "time": 300,
        "spawn": [1, 15], "tiles": grid, "items": {}, "entities": [],
    })


def test_horizontal_free_move():
    """UT-F-01：空地图水平移动按 vx*dt 前进，四向接触均为 False。"""
    tmap = make_tmap({})
    body = Body(100.0, 200.0, 26, 36, vx=240.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert body.x == pytest.approx(100.0 + 240.0 * PHYSICS_DT)
    assert body.y == pytest.approx(200.0)
    assert not (contacts.left or contacts.right or contacts.head or contacts.ground)


def test_hit_wall_on_right():
    """UT-F-02：向右撞墙后右边缘精确贴住墙左边界。"""
    # 墙在第 10 列、第 5 行；体底边与墙同高，右边缘距墙 0.5 px
    tmap = make_tmap({(10, 5): "#"})
    body = Body(10 * TILE - 26 - 0.5, 5 * TILE, 26, 36, vx=200.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert body.x + body.w == pytest.approx(10 * TILE)
    assert body.vx == 0.0
    assert contacts.right is True
    assert contacts.left is False


def test_hit_wall_on_left():
    """UT-F-03：向左撞墙后左边缘精确贴住墙右边界。"""
    tmap = make_tmap({(5, 5): "#"})
    body = Body(6 * TILE, 5 * TILE, 26, 36, vx=-200.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert body.x == pytest.approx(6 * TILE)
    assert body.vx == 0.0
    assert contacts.left is True
    assert contacts.right is False


def test_land_on_ground():
    """UT-F-04：从空中落到地面，脚底贴地面顶面且 vy=0。"""
    tmap = make_tmap({(c, 16): "#" for c in range(COLS)})
    body = Body(100.0, 600.0, 26, 36, vy=600.0)   # 底边 636，下落 5 px 后进入第 16 行
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert contacts.ground is True
    assert body.bottom == pytest.approx(16 * TILE)
    assert body.y == pytest.approx(16 * TILE - 36)
    assert body.vy == 0.0


def test_fast_fall_does_not_tunnel():
    """UT-F-05：780 px/s 单步位移 6.5 px，薄地面也不会被穿过。"""
    # 自由下落：位移应为 v*dt
    tmap = make_tmap({})
    free = Body(100.0, 500.0, 26, 36, vy=780.0)
    move_and_collide(free, tmap, PHYSICS_DT)
    assert free.y == pytest.approx(500.0 + 780.0 * PHYSICS_DT)

    # 紧贴地面下落：被 40 px 厚地面接住，不会穿过
    tmap = make_tmap({(c, 16): "#" for c in range(COLS)})
    body = Body(100.0, 16 * TILE - 36 - 1, 26, 36, vy=780.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT)
    assert contacts.ground is True
    assert body.bottom == pytest.approx(16 * TILE)


def test_head_bump_single_brick():
    """UT-F-06：上升顶到砖块，y 对齐砖块下沿并置 head。"""
    tmap = make_tmap({(10, 8): "B"})
    body = Body(10 * TILE + 7, 9 * TILE, 26, 36, vy=-300.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert contacts.head is True
    assert body.y == pytest.approx((8 + 1) * TILE)
    assert body.vy == 0.0
    assert (10, 8) in contacts.head_tiles


def test_head_bump_two_adjacent_bricks():
    """UT-F-07：同时顶到两块相邻砖，head_tiles 含两个坐标。"""
    tmap = make_tmap({(10, 8): "B", (11, 8): "B"})
    body = Body(10 * TILE, 9 * TILE, 44, 36, vy=-300.0)   # 宽 44 跨 10/11 两列
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert contacts.head is True
    assert {(10, 8), (11, 8)} <= set(contacts.head_tiles)
    assert body.y == pytest.approx(9 * TILE)


def test_pass_through_platform_upward():
    """UT-F-08：从下方穿过单向平台，不被阻挡。"""
    tmap = make_tmap({(c, 10): "=" for c in range(5, 9)})
    body = Body(6 * TILE, 11 * TILE, 26, 36, vy=-300.0)   # 第 11 行向上进入第 10 行
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert contacts.ground is False
    assert contacts.head is False
    assert body.y == pytest.approx(11 * TILE - 300.0 * PHYSICS_DT)


def test_land_on_platform_from_above():
    """UT-F-09：从平台上方落下，站在平台顶面。"""
    tmap = make_tmap({(c, 10): "=" for c in range(5, 9)})
    body = Body(6 * TILE, 10 * TILE - 36 - 4, 26, 36, vy=600.0)  # 底边高于平台顶面
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert contacts.ground is True
    assert body.bottom == pytest.approx(10 * TILE)
    assert body.vy == 0.0


def test_drop_through_platform():
    """UT-F-10：按下穿越时站在平台上也直接下穿。"""
    tmap = make_tmap({(c, 10): "=" for c in range(5, 9)})
    body = Body(6 * TILE, 10 * TILE - 36 - 1, 26, 36, vy=600.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT, drop_through=True)

    assert contacts.ground is False
    assert body.vy == pytest.approx(600.0)
    assert body.y == pytest.approx(10 * TILE - 36 - 1 + 600.0 * PHYSICS_DT)


def test_platform_is_not_horizontal_wall():
    """UT-F-11：水平穿越单向平台不被阻挡。"""
    tmap = make_tmap({(c, 10): "=" for c in range(5, 9)})
    body = Body(5 * TILE - 15, 10 * TILE, 26, 36, vx=240.0)
    contacts = move_and_collide(body, tmap, PHYSICS_DT)

    assert contacts.left is False
    assert contacts.right is False
    assert body.x == pytest.approx(5 * TILE - 15 + 240.0 * PHYSICS_DT)


def test_level_bounds_are_walls():
    """UT-F-12：左右越界被当作实心墙，x 不越界。"""
    tmap = make_tmap({})

    left = Body(0.0, 200.0, 26, 36, vx=-200.0)
    left_contacts = move_and_collide(left, tmap, PHYSICS_DT)
    assert left.x == pytest.approx(0.0)
    assert left.vx == 0.0
    assert left_contacts.left is True

    right = Body(COLS * TILE - 26, 200.0, 26, 36, vx=200.0)
    right_contacts = move_and_collide(right, tmap, PHYSICS_DT)
    assert right.x == pytest.approx(COLS * TILE - 26)
    assert right.vx == 0.0
    assert right_contacts.right is True


def test_overlap_and_standing_on():
    """补充：AABB 相交与站立检测。"""
    a = Body(0, 0, 20, 20)
    b = Body(10, 10, 20, 20)
    c = Body(21, 0, 20, 20)
    assert overlap(a, b) is True
    assert overlap(a, c) is False
    assert overlap(a.aabb, b) is True          # 支持直接传元组

    tmap = make_tmap({(c_, 16): "#" for c_ in range(COLS)})
    body = Body(100.0, 16 * TILE - 36, 26, 36)  # 正好站在地面上
    assert standing_on(body, tmap) is True
    body.y -= 24
    assert standing_on(body, tmap) is False     # 悬空超过半格，不再算站立

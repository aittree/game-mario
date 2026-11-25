"""相机死区、边界与视差（docs/03 §7）。

只依赖纯逻辑层，不 import pygame。
"""

import pytest

from src.camera import Camera
from src.config import CAM_DEAD_MAX, CAM_DEAD_MIN, CANVAS_W


def test_snap_to_clamps_at_level_start():
    cam = Camera(4000)
    cam.snap_to(10)
    assert cam.x == 0


def test_snap_to_clamps_at_level_end():
    cam = Camera(2000)
    cam.snap_to(1990)
    assert cam.x == cam.max_x == 2000 - CANVAS_W


def test_follow_ignores_player_inside_dead_zone():
    cam = Camera(4000)
    cam.x = 200
    middle = CANVAS_W * (CAM_DEAD_MIN + CAM_DEAD_MAX) / 2
    cam.follow(cam.x + middle, 1 / 60)
    assert cam.x == 200


def test_follow_moves_when_player_passes_right_dead_edge():
    cam = Camera(4000)
    cam.follow(CANVAS_W * CAM_DEAD_MAX + 100, 1 / 60)
    assert cam.x > 0


def test_follow_moves_when_player_passes_left_dead_edge():
    cam = Camera(4000)
    cam.x = 1000
    cam.follow(1000 + CANVAS_W * CAM_DEAD_MIN - 100, 1 / 60)
    assert cam.x < 1000


def test_follow_never_leaves_level_bounds():
    cam = Camera(2000)
    for _ in range(120):
        cam.follow(1990, 1 / 60)
    assert cam.x <= cam.max_x

    cam = Camera(2000)
    for _ in range(120):
        cam.follow(0, 1 / 60)
    assert cam.x >= 0


def test_parallax_factors():
    cam = Camera(4000)
    cam.x = 100
    assert cam.parallax(0.35) == pytest.approx(-35)
    assert cam.parallax(0.70) == pytest.approx(-70)


def test_to_screen():
    cam = Camera(4000)
    cam.x = 120
    assert cam.to_screen(300) == 180

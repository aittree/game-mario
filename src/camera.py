"""死区跟随相机（docs/03 §7）。"""

from __future__ import annotations

from .config import CAM_DEAD_MAX, CAM_DEAD_MIN, CAM_LERP, CANVAS_W


class Camera:
    def __init__(self, level_width: int):
        self.x = 0.0
        self.level_width = level_width
        self.max_x = max(0, level_width - CANVAS_W)

    def snap_to(self, player_x: float) -> None:
        self.x = self._clamp(player_x - CANVAS_W * 0.45)

    def follow(self, player_x: float, dt: float) -> None:
        screen_x = player_x - self.x
        if screen_x < CAM_DEAD_MIN * CANVAS_W:
            target = player_x - CAM_DEAD_MIN * CANVAS_W
        elif screen_x > CAM_DEAD_MAX * CANVAS_W:
            target = player_x - CAM_DEAD_MAX * CANVAS_W
        else:
            return
        # 目标位置硬钳制，再小幅插值，避免高速冲刺时相机抖动
        self.x += (self._clamp(target) - self.x) * min(1.0, CAM_LERP * 60 * dt)

    def _clamp(self, x: float) -> float:
        return max(0.0, min(self.max_x, x))

    def to_screen(self, world_x: float) -> float:
        return world_x - self.x

    def parallax(self, factor: float) -> float:
        """背景层偏移：factor 越小越远。"""
        return -self.x * factor

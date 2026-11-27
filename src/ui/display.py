"""窗口与画布缩放（docs/03 §9.5）。

逻辑画布固定 CANVAS_W×CANVAS_H；窗口与全屏都等比缩放并居中留黑边，
鼠标坐标通过 `to_canvas()` 反向映射回画布坐标。
"""

from __future__ import annotations

import pygame

from ..config import APP_NAME, CANVAS_H, CANVAS_W


class Display:
    def __init__(self, fullscreen: bool = False, title: str = APP_NAME):
        pygame.display.set_caption(title)
        self.fullscreen = False
        self.scale = 1.0
        self.offset = (0, 0)
        self.scaled: pygame.Surface | None = None
        self.window = pygame.Surface((CANVAS_W, CANVAS_H))   # apply_mode 会立即替换
        self.apply_mode(fullscreen)
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H)).convert()

    def apply_mode(self, fullscreen: bool) -> None:
        """切换窗口/全屏；窗口尺寸按桌面分辨率自适应，避免小屏被裁切。"""
        self.fullscreen = fullscreen
        if fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            desk_w, desk_h = self._desktop_size()
            scale = min(1.0, (desk_w - 40) / CANVAS_W, (desk_h - 120) / CANVAS_H)
            size = (int(CANVAS_W * scale), int(CANVAS_H * scale))
            self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
        self._layout()

    def set_fullscreen(self, enabled: bool) -> None:
        """F11 / 设置页切换全屏的入口。"""
        if enabled != self.fullscreen:
            self.apply_mode(enabled)

    @staticmethod
    def _desktop_size() -> tuple[int, int]:
        """取桌面分辨率做窗口自适应；无显示设备（离屏测试）时退回逻辑画布尺寸。"""
        try:
            return pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError):
            return CANVAS_W, CANVAS_H

    def _layout(self) -> None:
        """按当前窗口实际尺寸重算缩放与黑边偏移。"""
        win_w, win_h = self.window.get_size()
        self.scale = min(win_w / CANVAS_W, win_h / CANVAS_H)
        draw_w = max(1, int(CANVAS_W * self.scale))
        draw_h = max(1, int(CANVAS_H * self.scale))
        self.offset = ((win_w - draw_w) // 2, (win_h - draw_h) // 2)
        if (win_w, win_h) == (CANVAS_W, CANVAS_H):
            self.scaled = None
        elif self.scaled is None or self.scaled.get_size() != (draw_w, draw_h):
            self.scaled = pygame.Surface((draw_w, draw_h))

    def present(self) -> None:
        self._layout()
        if self.scaled is not None:
            pygame.transform.scale(self.canvas, self.scaled.get_size(), self.scaled)   # 最近邻，保持像素锐利
            self.window.fill((0, 0, 0))
            self.window.blit(self.scaled, self.offset)
        else:
            self.window.blit(self.canvas, (0, 0))
        pygame.display.flip()

    def to_canvas(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """窗口坐标 → 画布坐标；点在黑边或画布外时返回 None。"""
        x = (pos[0] - self.offset[0]) / self.scale
        y = (pos[1] - self.offset[1]) / self.scale
        if 0 <= x < CANVAS_W and 0 <= y < CANVAS_H:
            return int(x), int(y)
        return None

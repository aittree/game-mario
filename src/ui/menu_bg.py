"""菜单动态背景：暗色视差，纯代码绘制、不抗锯齿（docs/03 §9）。

所有元素用整数坐标与实色块，保证像素锐利；不加载外部贴图。
"""

from __future__ import annotations

import math
import random

import pygame

from ..config import ACCENT, CANVAS_H, CANVAS_W

# 暗色氛围色盘
_SKY_TOP = (10, 14, 31)
_SKY_MID = (22, 32, 56)
_SKY_BOT = (30, 42, 74)
_HILL_FAR = (27, 39, 66)
_HILL_NEAR = (42, 58, 94)
_HORIZON = (120, 140, 190)

_STAR_COUNT = 150
_DUST_COUNT = 28


class MenuBackground:
    def __init__(self, size: tuple[int, int] = (CANVAS_W, CANVAS_H)):
        self.size = size
        self.t = 0.0
        self._stars = [
            (random.random(), random.random() * 0.62,
             random.choice((1, 1, 2)),
             random.random() * 0.4 + 0.1)
            for _ in range(_STAR_COUNT)
        ]
        self._dust = [
            (random.random(), random.random(),
             random.random() * 0.018 + 0.005,
             random.choice((2, 2, 3)),
             random.random() * 0.5 + 0.25)
            for _ in range(_DUST_COUNT)
        ]
        self._sky: pygame.Surface | None = None

    def update(self, dt: float) -> None:
        self.t += dt

    # —— 绘制 ——

    def _build_sky(self) -> pygame.Surface:
        sky = pygame.Surface(self.size)
        w, h = self.size
        height = max(1, h - 1)
        for y in range(h):
            t = y / height
            if t < 0.55:
                k = t / 0.55
                top, bot = _SKY_TOP, _SKY_MID
            else:
                k = (t - 0.55) / 0.45
                top, bot = _SKY_MID, _SKY_BOT
            color = tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3))
            pygame.draw.line(sky, color, (0, y), (w, y))
        return sky

    def draw(self, surface: pygame.Surface) -> None:
        sky = self._sky
        if sky is None:
            sky = self._build_sky()
            self._sky = sky
        surface.blit(sky, (0, 0))
        w, h = self.size
        t = self.t

        # 视差星点（闪烁 + 缓慢右移）
        for sx, sy, s, p in self._stars:
            x = (sx * w + t * p * 14) % w
            a = 0.35 + 0.65 * abs(math.sin(t * 1.8 + sx * 12))
            v = int(255 * a)
            pygame.draw.rect(surface, (v, v, v), (int(x), int(sy * h), s, s))

        # 双层远山（正弦起伏，不同速度形成视差）
        self._draw_hill(surface, t, h * 0.78, _HILL_FAR, 26, 40, 0.00025)
        self._draw_hill(surface, t, h * 0.86, _HILL_NEAR, 18, 30, 0.0005)
        # 地平线高光
        pygame.draw.line(surface, _HORIZON, (0, int(h * 0.78)), (w, int(h * 0.78)))

        # 飘动光尘（金色像素块，正弦上下浮动）
        for dx, dy, v, sz, a in self._dust:
            nx = (dx + v * t) % 1.0
            ny = (dy + math.sin(t * 0.9 + dx * 18) * 0.012) % 1.0
            col = (int(ACCENT[0] * a), int(ACCENT[1] * a), int(ACCENT[2] * a))
            pygame.draw.rect(surface, col, (int(nx * w), int(ny * h), sz, sz))

    @staticmethod
    def _draw_hill(surface: pygame.Surface, t: float, base_y: float,
                   color: tuple[int, int, int], amp: float, step: int,
                   speed: float) -> None:
        w, h = surface.get_size()
        pts: list[tuple[float, float]] = [(0, h)]
        x = 0
        while x <= w:
            y = base_y + math.sin((x / w) * 4.0 + t * speed) * amp \
                + math.sin(x * 0.02 + t * speed * 2) * amp * 0.3
            pts.append((x, y))
            x += step
        pts.append((w, h))
        pygame.draw.polygon(surface, color, pts)

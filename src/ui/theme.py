"""字体与文本绘制（docs/03 §9.1）。

字体统一走 `assets/fonts/zpix.ttf`（最像素）；缺失时退回 pygame 默认字体，保证不崩。
"""

from __future__ import annotations

import pygame

from ..resource import resource_path

_fonts: dict[tuple[int, bool], pygame.font.Font] = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    cached = _fonts.get(key)
    if cached is None:
        try:
            cached = pygame.font.Font(resource_path("assets", "fonts", "zpix.ttf"), size)
        except (OSError, pygame.error):
            cached = pygame.font.SysFont(None, size)
        cached.set_bold(bold)
        _fonts[key] = cached
    return cached


def text(surface: pygame.Surface, content: str, size: int, color,
         pos, anchor: str = "topleft", bold: bool = False) -> pygame.Rect:
    image = font(size, bold).render(content, False, color)   # 像素字体关闭抗锯齿
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
    return rect

"""菜单按钮（docs/03 §10）。

按钮只描述「动作 + 矩形 + 是否可用」，点击分发与界面流转由 `main.py` 决定。
视觉为像素风：直角、双层描边、实色位移阴影，无圆角无抗锯齿。
"""

from __future__ import annotations

import pygame

from ..config import ACCENT, HUD_TEXT
from . import theme

_FILL = (14, 20, 36, 225)
_FILL_SELECTED = (28, 42, 70, 238)
_BORDER = (72, 92, 130)
_TEXT_OFF = (112, 120, 134)
_FILL_OFF = (22, 24, 30, 200)
_HI = (255, 255, 255, 38)          # 像素高光（左上）
_LO = (0, 0, 0, 92)                # 像素暗边（右下）


class Button:
    def __init__(self, action: str, label: str, rect: pygame.Rect,
                 enabled: bool = True):
        self.action = action
        self.label = label
        self.rect = rect
        self.enabled = enabled


def draw_button(surface: pygame.Surface, button: Button, selected: bool = False,
                time: float = 0.0) -> None:
    if button.enabled:
        fill = _FILL_SELECTED if selected else _FILL
        border = ACCENT if selected else _BORDER
        text_color = ACCENT if selected else HUD_TEXT
    else:
        fill, border, text_color = _FILL_OFF, (56, 60, 70), _TEXT_OFF

    r = button.rect
    # 实色位移阴影（像素阴影，不用 blur）
    shadow = pygame.Surface(r.size, pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 110))
    surface.blit(shadow, (r.x + 4, r.y + 4))

    # 主体 + 双层描边（直角）
    body = pygame.Surface(r.size, pygame.SRCALPHA)
    body.fill(fill)
    border_w = 3 if selected else 2
    pygame.draw.rect(body, border, body.get_rect(), width=border_w)
    # 左上高光 / 右下暗边，形成像素立体感
    pygame.draw.line(body, _HI, (border_w, border_w), (r.w - border_w - 1, border_w))
    pygame.draw.line(body, _HI, (border_w, border_w), (border_w, r.h - border_w - 1))
    pygame.draw.line(body, _LO, (border_w, r.h - border_w - 1),
                     (r.w - border_w - 1, r.h - border_w - 1))
    pygame.draw.line(body, _LO, (r.w - border_w - 1, border_w),
                     (r.w - border_w - 1, r.h - border_w - 1))
    surface.blit(body, r.topleft)

    # 选中指示箭头（闪烁，像素三角形，不依赖字体字形）
    if button.enabled and selected and int(time * 3) % 2 == 0:
        ax, ay = r.x + 18, r.centery
        pygame.draw.polygon(surface, ACCENT,
                            [(ax, ay - 6), (ax, ay + 6), (ax + 10, ay)])

    theme.text(surface, button.label, 24, text_color, r.center,
               anchor="center", bold=selected)


def hit(buttons: list[Button], pos: tuple[int, int]) -> Button | None:
    """返回命中的按钮；禁用的按钮也返回，交由调用方决定是否响应。"""
    for button in buttons:
        if button.rect.collidepoint(pos):
            return button
    return None

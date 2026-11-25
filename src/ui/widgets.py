"""菜单按钮（docs/03 §10）。

按钮只描述「动作 + 矩形 + 是否可用」，点击分发与界面流转由 `main.py` 决定。
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


class Button:
    def __init__(self, action: str, label: str, rect: pygame.Rect,
                 enabled: bool = True):
        self.action = action
        self.label = label
        self.rect = rect
        self.enabled = enabled


def draw_button(surface: pygame.Surface, button: Button, selected: bool = False) -> None:
    if button.enabled:
        fill = _FILL_SELECTED if selected else _FILL
        border = ACCENT if selected else _BORDER
        text_color = ACCENT if selected else HUD_TEXT
    else:
        fill, border, text_color = _FILL_OFF, (56, 60, 70), _TEXT_OFF

    layer = pygame.Surface(button.rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, fill, layer.get_rect(), border_radius=12)
    pygame.draw.rect(layer, border, layer.get_rect(), width=3 if selected else 2,
                     border_radius=12)
    surface.blit(layer, button.rect.topleft)
    theme.text(surface, button.label, 24, text_color,
               button.rect.center, anchor="center", bold=selected)


def hit(buttons: list[Button], pos: tuple[int, int]) -> Button | None:
    """返回命中的按钮；禁用的按钮也返回，交由调用方决定是否响应。"""
    for button in buttons:
        if button.rect.collidepoint(pos):
            return button
    return None

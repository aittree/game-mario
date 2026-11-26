"""按键 → 意图（docs/03 §8.4）。

只依赖 pygame 的键值常量与 `entities/base.py` 的纯数据类型 `InputIntent`，
不触碰实体业务逻辑。
"""

from __future__ import annotations

import pygame

from .entities.base import InputIntent

MOVE_LEFT = (pygame.K_LEFT, pygame.K_a)
MOVE_RIGHT = (pygame.K_RIGHT, pygame.K_d)
JUMP = (pygame.K_UP, pygame.K_w, pygame.K_SPACE)
SPRINT = (pygame.K_LSHIFT, pygame.K_RSHIFT)
FIRE = (pygame.K_x, pygame.K_f)
DOWN = (pygame.K_DOWN, pygame.K_s)

GAME_KEYS = MOVE_LEFT + MOVE_RIGHT + JUMP + SPRINT + FIRE + DOWN

# 设置 / 暂停界面展示用（只读，单一来源；改键位只改这里与上面的常量）
KEY_LEGEND: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("左右移动", MOVE_LEFT + MOVE_RIGHT),
    ("下蹲", DOWN),
    ("跳跃", JUMP),
    ("冲刺", SPRINT),
    ("射击 / 火球", FIRE),
)


def key_name(key: int) -> str:
    """把 pygame 键值转成展示用名称（用于设置 / 暂停界面）。"""
    special = {
        pygame.K_LEFT: "←", pygame.K_RIGHT: "→",
        pygame.K_UP: "↑", pygame.K_DOWN: "↓",
        pygame.K_SPACE: "空格",
        pygame.K_RETURN: "回车", pygame.K_KP_ENTER: "回车",
        pygame.K_ESCAPE: "ESC",
        pygame.K_LSHIFT: "L-Shift", pygame.K_RSHIFT: "R-Shift",
        pygame.K_LCTRL: "L-Ctrl", pygame.K_RCTRL: "R-Ctrl",
        pygame.K_LALT: "L-Alt", pygame.K_RALT: "R-Alt",
    }
    if key in special:
        return special[key]
    name = pygame.key.name(key) or ""
    return name.upper() if len(name) == 1 else name


class Keymap:
    def __init__(self):
        self.held: set[int] = set()
        self._jump_pressed = False
        self._fire_pressed = False

    def keydown(self, key: int) -> bool:
        """返回 True 表示本模块消费了该键（界面键由 main 处理）。"""
        self.held.add(key)
        if key in JUMP:
            self._jump_pressed = True
        if key in FIRE:
            self._fire_pressed = True
        return key in GAME_KEYS

    def keyup(self, key: int) -> None:
        self.held.discard(key)

    def sample(self) -> InputIntent:
        intent = InputIntent(
            left=any(k in self.held for k in MOVE_LEFT),
            right=any(k in self.held for k in MOVE_RIGHT),
            jump_held=any(k in self.held for k in JUMP),
            sprint=any(k in self.held for k in SPRINT),
            down=any(k in self.held for k in DOWN),
            jump_pressed=self._jump_pressed,
            fire_pressed=self._fire_pressed,
        )
        self._jump_pressed = self._fire_pressed = False   # 边沿只生效一帧
        return intent

    def clear(self) -> None:
        """切界面时清空按住状态，防止回到游戏后「继续按住」。"""
        self.held.clear()
        self._jump_pressed = self._fire_pressed = False

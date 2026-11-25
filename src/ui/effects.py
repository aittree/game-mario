"""粒子与屏幕反馈（docs/03 §9.4）。

只读快照与事件、只写自身状态：特效永远不修改地形或实体，保证「特效不影响逻辑」。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from ..config import ACCENT, BRICK_RGB, COIN_RGB, SCORE_COIN, TILE
from .theme import font

if TYPE_CHECKING:                       # 仅类型标注：运行期不反向依赖 game
    from ..game import GameEvent, LevelSnapshot

# 各类特效生命周期（毫秒）与参数
BUMP_MS = 180.0
BUMP_HEIGHT = 8
FRAGMENT_MS = 500.0
FRAGMENT_GRAVITY = 900.0
COIN_POP_MS = 200.0
RING_MS = 250.0
SPARK_MS = 300.0
POPUP_MS = 600.0
FLASH_MS = 50.0                      # 约 2～3 帧，保证先 update 后 draw 的帧序下仍可见
FLASH_ALPHA = 180


class _Fragment:
    """砖块碎片：重力下落 + 自旋。"""

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 spin: float, angle: float, ms: float):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.spin = spin
        self.angle = angle
        self.ms = ms


class _CoinPop:
    def __init__(self, x: float, y: float, ms: float):
        self.x = x
        self.y = y
        self.ms = ms


class _Ring:
    def __init__(self, x: float, y: float, ms: float):
        self.x = x
        self.y = y
        self.ms = ms


class _Spark:
    def __init__(self, x: float, y: float, vx: float, vy: float, ms: float):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.ms = ms


class _Popup:
    def __init__(self, text: str, x: float, y: float, ms: float):
        self.text = text
        self.x = x
        self.y = y
        self.ms = ms


class Effects:
    def __init__(self):
        self.bumps: dict[tuple[int, int], float] = {}
        self.fragments: list[_Fragment] = []
        self.coin_pops: list[_CoinPop] = []
        self.rings: list[_Ring] = []
        self.sparks: list[_Spark] = []
        self.popups: list[_Popup] = []
        self.flash_ms = 0.0

    # —— 输入：模型钩子与游戏事件 ——

    def on_model_hook(self, hook: tuple, _snap: "LevelSnapshot") -> None:
        """消费 game.effects_hooks：('bump'|'brick'|'coin_pop', (col, row))。"""
        kind, cell = hook
        col, row = cell
        if kind == "bump":
            self.bumps[(col, row)] = BUMP_MS
        elif kind == "brick":
            self._spawn_fragments(col, row)
        elif kind == "coin_pop":
            self.coin_pops.append(
                _CoinPop((col + 0.5) * TILE, (row + 0.5) * TILE, COIN_POP_MS))

    def on_event(self, ev: "GameEvent", snap: "LevelSnapshot") -> None:
        """消费 GameEvent 补充特效（踩踏、火球击杀、变身、金币）。"""
        data = ev.data or {}
        if ev.kind == "stomp":
            x, y, w, h = data.get("cells", (0, 0, 0, 0))
            self.rings.append(_Ring(x + w / 2, y + h / 2, RING_MS))
        elif ev.kind == "firekill":
            x, y, w, h = data.get("cells", (0, 0, 0, 0))
            self._burst_sparks(x + w / 2, y + h / 2)
        elif ev.kind == "powerup":
            self.flash_ms = FLASH_MS
        elif ev.kind == "coin":
            self.popups.append(_Popup(f"+{SCORE_COIN}",
                                      snap.player_x + snap.player_w / 2,
                                      snap.player_y - 8, POPUP_MS))

    def _spawn_fragments(self, col: int, row: int) -> None:
        cx, cy = (col + 0.5) * TILE, (row + 0.5) * TILE
        for vx, vy, spin in ((-150, -300, -8), (150, -300, 8),
                             (-90, -220, -5), (90, -220, 5)):
            self.fragments.append(_Fragment(cx, cy, vx, vy, spin, 0.0, FRAGMENT_MS))

    def _burst_sparks(self, x: float, y: float) -> None:
        for i in range(8):
            angle = math.pi * 2 * i / 8
            self.sparks.append(_Spark(x, y, math.cos(angle) * 180,
                                      math.sin(angle) * 180 - 60, SPARK_MS))

    # —— 推进 ——

    def update(self, dt: float) -> None:
        ms = dt * 1000.0
        for cell in list(self.bumps):
            left = self.bumps[cell] - ms
            if left <= 0:
                del self.bumps[cell]
            else:
                self.bumps[cell] = left

        for f in self.fragments:
            f.ms -= ms
            f.vy += FRAGMENT_GRAVITY * dt
            f.x += f.vx * dt
            f.y += f.vy * dt
            f.angle += f.spin * 60 * dt
        self.fragments = [f for f in self.fragments if f.ms > 0]

        for c in self.coin_pops:
            c.ms -= ms
            c.y -= 60 * dt
        self.coin_pops = [c for c in self.coin_pops if c.ms > 0]

        for r in self.rings:
            r.ms -= ms
        self.rings = [r for r in self.rings if r.ms > 0]

        for s in self.sparks:
            s.ms -= ms
            s.vy += FRAGMENT_GRAVITY * dt
            s.x += s.vx * dt
            s.y += s.vy * dt
        self.sparks = [s for s in self.sparks if s.ms > 0]

        for p in self.popups:
            p.ms -= ms
            p.y -= 30 * dt
        self.popups = [p for p in self.popups if p.ms > 0]

        self.flash_ms = max(0.0, self.flash_ms - ms)

    # —— 查询：供渲染器偏移地形 ——

    def bump_offset(self, col: int, row: int) -> tuple[int, int]:
        """顶砖上抛偏移：0 → 8 px → 0 的正弦曲线。"""
        left = self.bumps.get((col, row))
        if left is None:
            return 0, 0
        progress = 1.0 - left / BUMP_MS
        return 0, -int(BUMP_HEIGHT * math.sin(math.pi * progress))

    # —— 绘制 ——

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        for c in self.coin_pops:
            progress = 1.0 - c.ms / COIN_POP_MS
            x = int(c.x - camera_x)
            y = int(c.y - 18 * progress)
            pygame.draw.circle(surface, COIN_RGB, (x, y), 9)
            pygame.draw.circle(surface, (255, 247, 200), (x - 3, y - 3), 3)

        for f in self.fragments:
            life = f.ms / FRAGMENT_MS
            size = max(3, int(8 * (0.5 + 0.5 * life)))
            chip = pygame.Surface((size, size), pygame.SRCALPHA)
            chip.fill((*BRICK_RGB, int(255 * life)))
            chip = pygame.transform.rotate(chip, f.angle)
            surface.blit(chip, (int(f.x - camera_x - size / 2),
                                int(f.y - size / 2)))

        for s in self.sparks:
            life = s.ms / SPARK_MS
            color = (255, int(160 + 60 * life), 60, int(255 * life))
            layer = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(layer, color, (4, 4), 3)
            surface.blit(layer, (int(s.x - camera_x - 4), int(s.y - 4)))

        for r in self.rings:
            progress = 1.0 - r.ms / RING_MS
            radius = int(8 + 26 * progress)
            alpha = int(200 * (1.0 - progress))
            layer = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*ACCENT, alpha),
                               (radius + 2, radius + 2), radius, 3)
            surface.blit(layer, (int(r.x - camera_x - radius - 2),
                                 int(r.y - radius - 2)))

        for p in self.popups:
            alpha = int(255 * min(1.0, p.ms / POPUP_MS))
            image = font(20, True).render(p.text, True, ACCENT)
            image.set_alpha(alpha)
            surface.blit(image, (int(p.x - camera_x - image.get_width() / 2),
                                 int(p.y - image.get_height())))

        if self.flash_ms > 0:
            flash = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, FLASH_ALPHA))
            surface.blit(flash, (0, 0))

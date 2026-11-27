"""世界与界面绘制（docs/03 §9.3）。

只读取 `LevelSnapshot`，不得修改模型层状态。
绘制顺序：天空与视差背景 → 地形 → 实体 → 玩家 → HUD。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from ..config import (
    ACCENT,
    APP_NAME,
    APP_NAME_EN,
    BRICK,
    CANVAS_H,
    CANVAS_W,
    COIN,
    DANGER,
    EMPTY,
    GROUND,
    HUD_BG,
    HUD_H,
    HUD_SUB,
    HUD_TEXT,
    METAL,
    PARALLAX_FAR,
    PARALLAX_NEAR,
    PIPE,
    PLATFORM,
    QUESTION,
    SPIKE,
    THEMES,
    TILE,
    TIME_LOW,
    USED,
    VERSION,
    VIEW_COLS,
)
from ..entities.base import AnimState, PowerState
from ..keymap import KEY_LEGEND, key_name
from ..levels import LevelInfo
from ..resource import resource_path
from .anim import (
    COIN_FRAME_SECONDS,
    ENEMY_ANIMS,
    ITEM_ANIMS,
    QUESTION_FRAME_SECONDS,
    clip_frame,
    player_clip,
)
from .theme import font as get_font, text as draw_text
from .widgets import Button, draw_button

# 菜单布局单一来源：调间距只改这里，避免散落魔法数字漂移
MENU_LOGO_SIZE = 120

if TYPE_CHECKING:                       # 只读快照类型：运行期不反向依赖 game
    from ..game import LevelSnapshot
    from ..storage import Profile, Settings
    from ..tilemap import TileMap

# 非动态图块的瓦片集索引（docs/08 §2.2）；问号块、金币、水管另行计算。
_TILE_INDEX = {
    GROUND: 0,
    BRICK: 1,
    METAL: 2,
    USED: 5,
    PLATFORM: 10,
    SPIKE: 11,
}


class Renderer:
    def __init__(self, size: tuple[int, int] = (CANVAS_W, CANVAS_H)):
        self.size = size
        self.time = 0.0
        self._player_t = 0.0
        self._player_state: AnimState | None = None
        self._tilesets: dict[str, list[pygame.Surface]] = {}
        self._backgrounds: dict[str, tuple[pygame.Surface, pygame.Surface, pygame.Surface]] = {}
        self._skies: dict[str, pygame.Surface] = {}
        self._player_frames = {
            "small": self._slice_sheet("player_small.png", 48, 48),
            "big": self._slice_sheet("player_big.png", 48, 72),
        }
        self._enemy_frames = self._slice_sheet("enemies.png", 48, 48)
        self._item_frames = self._slice_sheet("items.png", 48, 48)
        self._logo: pygame.Surface | None = None
        self._menu_anim = None   # 菜单动态视差背景（懒加载）

    # —— 资源加载 ——

    @staticmethod
    def _load_image(name: str) -> pygame.Surface:
        image = pygame.image.load(resource_path("assets", "images", name))
        try:
            return image.convert_alpha()
        except pygame.error:               # 无显示设备（离屏测试）时保持原始格式
            return image

    def _slice_sheet(self, name: str, frame_w: int, frame_h: int) -> list[pygame.Surface]:
        sheet = self._load_image(name)
        frames: list[pygame.Surface] = []
        for row in range(sheet.get_height() // frame_h):
            for col in range(sheet.get_width() // frame_w):
                rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
                frames.append(sheet.subsurface(rect).copy())
        return frames

    def _tileset(self, theme_key: str) -> list[pygame.Surface]:
        frames = self._tilesets.get(theme_key)
        if frames is None:
            name = THEMES[theme_key]["tiles"]
            frames = self._slice_sheet(name, TILE, TILE)
            self._tilesets[theme_key] = frames
        return frames

    def _sky(self, theme_key: str) -> pygame.Surface:
        sky = self._skies.get(theme_key)
        if sky is None:
            top, bottom = THEMES[theme_key]["sky"]
            sky = pygame.Surface(self.size)
            height = max(1, self.size[1] - 1)
            for y in range(self.size[1]):
                t = y / height
                color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
                pygame.draw.line(sky, color, (0, y), (self.size[0], y))
            self._skies[theme_key] = sky
        return sky

    def _bg_layers(self, theme_key: str) -> tuple[pygame.Surface, pygame.Surface, pygame.Surface]:
        layers = self._backgrounds.get(theme_key)
        if layers is None:
            base = THEMES[theme_key]["bg"]
            layers = (self._sky(theme_key),
                      self._load_image(f"{base}_far.png"),
                      self._load_image(f"{base}_near.png"))
            self._backgrounds[theme_key] = layers
        return layers

    # —— 帧推进 ——

    def update(self, dt: float) -> None:
        """推进动画计时器；与模型推进无关，只影响画面。"""
        self.time += dt
        self._player_t += dt
        if self._menu_anim is not None:
            self._menu_anim.update(dt)

    # —— 世界 ——

    def draw_world(self, surface: pygame.Surface, snap: LevelSnapshot,
                   effects=None) -> None:
        self._draw_background(surface, snap)
        bump_offset = getattr(effects, "bump_offset", None)
        self._draw_tiles(surface, snap, bump_offset)
        self._draw_entities(surface, snap)
        self._draw_player(surface, snap)
        if effects is not None:
            effects.draw(surface, snap.camera_x)
        self.draw_hud(surface, snap)

    def _draw_background(self, surface: pygame.Surface, snap: LevelSnapshot) -> None:
        sky, far, near = self._bg_layers(snap.theme)
        surface.blit(sky, (0, 0))
        self._blit_tiled(surface, far, snap.camera_x * PARALLAX_FAR)
        self._blit_tiled(surface, near, snap.camera_x * PARALLAX_NEAR)

    @staticmethod
    def _blit_tiled(surface: pygame.Surface, layer: pygame.Surface,
                    scrolled: float) -> None:
        """远/近景层按相机偏移水平平铺；取模保证任意相机位置都能覆盖整屏。"""
        width = layer.get_width()
        start = -int(scrolled) % width - width
        x = start
        while x < surface.get_width():
            surface.blit(layer, (x, 0))
            x += width

    def _draw_tiles(self, surface: pygame.Surface, snap: LevelSnapshot, bump_offset) -> None:
        tmap = snap.tilemap
        frames = self._tileset(snap.theme)
        cam = int(snap.camera_x)
        c_start = max(0, cam // TILE - 1)
        c_end = min(tmap.cols, c_start + VIEW_COLS + 3)
        for row in range(tmap.rows):
            base_y = row * TILE
            for col in range(c_start, c_end):
                code = tmap.grid[row][col]
                if code == EMPTY:
                    continue
                index = self._tile_index(tmap, code, col, row)
                dx, dy = bump_offset(col, row) if bump_offset else (0, 0)
                surface.blit(frames[index], (col * TILE - cam + dx, base_y + dy))

    def _tile_index(self, tmap: TileMap, code: str, col: int, row: int) -> int:
        """按图块码与邻居选瓦片帧；水管与问号块/金币的帧规则见 docs/08 §2.2。"""
        if code == QUESTION:
            return 3 + int(self.time / QUESTION_FRAME_SECONDS) % 2
        if code == COIN:
            return 12 + int(self.time / COIN_FRAME_SECONDS) % 4
        if code == PIPE:
            if tmap.solid(col, row - 1):
                return 6                    # 上方还有水管 → 管身
            if tmap.tile_at(col + 1, row) == PIPE:
                return 7                    # 2 格宽管口的左半
            if tmap.tile_at(col - 1, row) == PIPE:
                return 8                    # 2 格宽管口的右半
            return 9                        # 单列管口
        return _TILE_INDEX[code]

    def _draw_entities(self, surface: pygame.Surface, snap: LevelSnapshot) -> None:
        cam = snap.camera_x
        # 按脚底 y 从大到小绘制，保证下方实体覆盖上方实体
        for ent in sorted(snap.entities, key=lambda e: e[2] + e[4], reverse=True):
            kind, x, y, w, h, _state, _frame, _facing, extra = ent
            if kind == "pipe_bloom" and not (extra and extra.get("visible")):
                continue
            if kind in ENEMY_ANIMS or kind == "shellbug":
                key = self._enemy_key(kind, extra)
                frame = self._enemy_frames[clip_frame(ENEMY_ANIMS[key], self.time)]
                if extra and extra.get("squash"):
                    # 被踩扁：纵向压到一半，底边对齐，做出“拍扁”观感（无需额外美术帧）
                    frame = pygame.transform.scale(
                        frame, (frame.get_width(), max(1, frame.get_height() // 2)))
                flip = bool(extra and extra.get("dir", -1) > 0)
                self._blit_bottom(surface, frame, x, y, w, h, cam, flip)
            elif kind in ITEM_ANIMS:
                frame = self._item_frames[clip_frame(ITEM_ANIMS[kind], self.time)]
                if kind == "fireball":
                    self._blit_center(surface, frame, x, y, w, h, cam)
                else:
                    self._blit_bottom(surface, frame, x, y, w, h, cam)
            else:
                self._draw_prop(surface, kind, x, y, w, h, cam, extra)

    @staticmethod
    def _enemy_key(kind: str, extra: dict | None) -> str:
        """甲壳虫缩壳后改用壳帧（行 2），其余敌人直接用自身 kind。"""
        if kind == "shellbug" and extra and extra.get("state") != "walk":
            return "shell"
        return kind

    @staticmethod
    def _blit_bottom(surface: pygame.Surface, image: pygame.Surface, x: float, y: float,
                     w: float, h: float, cam: float, flip: bool = False) -> None:
        """精灵底边对齐碰撞盒底边、水平居中（脚底对齐，docs/03 §9.3）。"""
        if flip:
            image = pygame.transform.flip(image, True, False)
        dx = x + (w - image.get_width()) / 2 - cam
        dy = y + h - image.get_height()
        surface.blit(image, (int(dx), int(dy)))

    @staticmethod
    def _blit_center(surface: pygame.Surface, image: pygame.Surface, x: float, y: float,
                     w: float, h: float, cam: float) -> None:
        """火球等小实体：精灵实体在帧内居中，因此按碰撞盒中心对齐。"""
        dx = x + w / 2 - image.get_width() / 2 - cam
        dy = y + h / 2 - image.get_height() / 2
        surface.blit(image, (int(dx), int(dy)))

    @staticmethod
    def _draw_prop(surface: pygame.Surface, kind: str, x: float, y: float,
                   w: float, h: float, cam: float, extra: dict | None) -> None:
        sx = int(x - cam)
        if kind == "moving_platform":
            rect = pygame.Rect(sx, int(y), int(w), int(h))
            pygame.draw.rect(surface, (122, 78, 42), rect, border_radius=4)
            pygame.draw.rect(surface, (196, 138, 79), (rect.x, rect.y, rect.w, 5),
                             border_radius=2)
            pygame.draw.rect(surface, (74, 46, 26), rect, width=2, border_radius=4)
            for bolt_x in (rect.x + 8, rect.right - 12):
                pygame.draw.circle(surface, (222, 184, 122), (bolt_x, rect.centery), 3)
        elif kind == "checkpoint":
            pole_x = sx + int(w // 2)
            pygame.draw.rect(surface, (214, 222, 233), (pole_x - 2, int(y), 4, int(h)))
            raised = bool(extra and extra.get("raised"))
            flag_y = int(y) + (4 if raised else int(h * 0.45))
            flag = [(pole_x + 2, flag_y), (pole_x + 26, flag_y + 9), (pole_x + 2, flag_y + 18)]
            pygame.draw.polygon(surface, ACCENT if raised else (150, 160, 178), flag)
        elif kind == "goal":
            pole_x = sx + 8
            pygame.draw.rect(surface, (224, 232, 244), (pole_x - 2, int(y), 4, int(h)))
            pygame.draw.circle(surface, ACCENT, (pole_x, int(y)), 6)
            flag = [(pole_x + 2, int(y) + 6), (pole_x + 34, int(y) + 16),
                    (pole_x + 2, int(y) + 26)]
            pygame.draw.polygon(surface, ACCENT, flag)

    def _draw_player(self, surface: pygame.Surface, snap: LevelSnapshot) -> None:
        if self._player_state is not snap.player_anim:
            self._player_state = snap.player_anim
            self._player_t = 0.0
        # 无敌闪烁：每 60 ms 跳过一次绘制，与逻辑无关
        if snap.player_invincible and int(self.time * 1000) % 120 < 60:
            return
        sheet = "small" if snap.player_power is PowerState.SMALL else "big"
        frames = self._player_frames[sheet]
        index = clip_frame(player_clip(sheet, snap.player_anim), self._player_t)
        image = frames[min(index, len(frames) - 1)]
        if snap.player_facing_left:
            image = pygame.transform.flip(image, True, False)
        dx = snap.player_x + (snap.player_w - image.get_width()) / 2 - snap.camera_x
        dy = snap.player_y + snap.player_h - image.get_height()
        surface.blit(image, (int(dx), int(dy)))

    # —— HUD ——

    def draw_hud(self, surface: pygame.Surface, snap: LevelSnapshot) -> None:
        panel = pygame.Surface((CANVAS_W, HUD_H), pygame.SRCALPHA)
        panel.fill((*HUD_BG, 214))
        surface.blit(panel, (0, 0))
        pygame.draw.line(surface, ACCENT, (0, HUD_H - 3), (CANVAS_W, HUD_H - 3), 2)

        draw_text(surface, "分数", 18, HUD_SUB, (40, 36), anchor="midleft")
        draw_text(surface, f"{snap.score:06d}", 28, HUD_TEXT, (300, 36),
                  anchor="midright", bold=True)

        coin_icon = pygame.transform.scale(self._tileset(snap.theme)[12], (28, 28))
        surface.blit(coin_icon, (330, 22))
        draw_text(surface, f"× {snap.coins}", 28, HUD_TEXT, (368, 36),
                  anchor="midleft", bold=True)

        draw_text(surface, f"世界 {snap.level_id}", 24, HUD_TEXT, (600, 36),
                  anchor="midleft", bold=True)

        self._draw_stopwatch(surface, 820, 22)
        if snap.time_units <= TIME_LOW:
            pulse = 0.5 + 0.5 * math.sin(self.time * 4 * math.pi)   # 0.5 s 周期脉动
            time_color = tuple(int(DANGER[i] + (HUD_TEXT[i] - DANGER[i]) * 0.3 * pulse)
                               for i in range(3))
        else:
            time_color = HUD_TEXT
        draw_text(surface, f"{snap.time_units:03d}", 28, time_color, (856, 36),
                  anchor="midleft", bold=True)

        avatar = pygame.transform.scale(self._player_frames["small"][0], (30, 30))
        surface.blit(avatar, (1040, 21))
        draw_text(surface, f"× {snap.lives}", 28, HUD_TEXT, (1078, 36),
                  anchor="midleft", bold=True)

    @staticmethod
    def _draw_stopwatch(surface: pygame.Surface, x: int, y: int) -> None:
        center = (x + 11, y + 15)
        pygame.draw.circle(surface, HUD_TEXT, center, 10, 2)
        pygame.draw.line(surface, HUD_TEXT, (center[0], center[1]), (center[0], center[1] - 6), 2)
        pygame.draw.line(surface, HUD_TEXT, (center[0], center[1]), (center[0] + 4, center[1]), 2)
        pygame.draw.line(surface, HUD_TEXT, (center[0] - 3, y + 1), (center[0] + 3, y + 1), 2)

    # —— 菜单类界面 ——

    def draw_menu(self, surface: pygame.Surface, profile: Profile,
                  selected: int = 0) -> list[Button]:
        self._draw_menu_bg(surface)
        # —— 菜单垂直布局（单一来源：调间距只改这里）——
        logo_y = 40
        sub_y = 192
        title_y = 250
        best_y = 310
        btn_w, btn_h = 300, 50
        btn_x = CANVAS_W // 2 - btn_w // 2
        btn_y0 = 420
        btn_pitch = 60
        foot_y = 688

        logo = self._logo_image()
        if logo is not None:
            surface.blit(logo, (CANVAS_W // 2 - logo.get_width() // 2, logo_y))
        draw_text(surface, APP_NAME_EN.upper(), 16, HUD_SUB,
                  (CANVAS_W // 2, sub_y), anchor="center")
        self._draw_pixel_title(surface, APP_NAME, CANVAS_W // 2, title_y)
        draw_text(surface, f"最高分 {profile.best_score:06d}", 22, HUD_SUB,
                  (CANVAS_W // 2, best_y), anchor="center")
        entries = (("开始游戏", "start"), ("设置", "open_settings"),
                   ("退出", "quit"))
        buttons = []
        for i, (label, action) in enumerate(entries):
            rect = pygame.Rect(btn_x, btn_y0 + i * btn_pitch, btn_w, btn_h)
            button = Button(action, label, rect)
            buttons.append(button)
            draw_button(surface, button, i == selected, self.time)
        draw_text(surface, "↑↓ 选择 / Enter 确认", 16, HUD_SUB,
                  (CANVAS_W // 2, foot_y), anchor="center")
        draw_text(surface, f"v{VERSION}", 16, HUD_SUB, (24, foot_y))
        return buttons

    def draw_level_select(self, surface: pygame.Surface, profile: Profile,
                          levels: list[LevelInfo], selected: int = 0) -> list[Button]:
        self._draw_menu_bg(surface)
        playable = [i for i, info in enumerate(levels)
                    if i < profile.unlocked and info.available]
        continue_index = playable[-1] if playable else 0
        draw_text(surface, "继续游玩", 40, ACCENT, (CANVAS_W // 2, 58),
                  anchor="center", bold=True)
        buttons: list[Button] = []
        for i, info in enumerate(levels):
            rect = pygame.Rect(110 + (i % 2) * 540, 176 + (i // 2) * 196, 520, 168)
            is_open = i < profile.unlocked and info.available
            buttons.append(Button(f"level:{i}", info.name, rect, enabled=is_open))
            self._draw_level_card(surface, rect, info, profile, is_open,
                                  i == selected, i == continue_index)
        back = Button("back", "返回主菜单", pygame.Rect(CANVAS_W // 2 - 130, 620, 260, 50))
        buttons.append(back)
        draw_button(surface, back, selected == len(levels))
        return buttons

    @staticmethod
    def _draw_key_legend(surface: pygame.Surface, x: int, y: int) -> int:
        """绘制只读按键说明（设置界面与暂停设置共用），返回结束 y。"""
        draw_text(surface, "按键说明", 22, ACCENT, (x, y),
                  anchor="topleft", bold=True)
        y += 34
        for desc, keys in KEY_LEGEND:
            draw_text(surface, desc, 19, HUD_TEXT, (x, y), anchor="topleft")
            draw_text(surface, " / ".join(key_name(k) for k in keys), 19,
                      HUD_SUB, (x + 320, y), anchor="topleft")
            y += 30
        extras = (("暂停 / 返回", "ESC / P"), ("选择 / 确认", "↑ ↓ / 回车"))
        for desc, keys in extras:
            draw_text(surface, desc, 19, HUD_TEXT, (x, y), anchor="topleft")
            draw_text(surface, keys, 19, HUD_SUB, (x + 320, y), anchor="topleft")
            y += 30
        return y

    def draw_settings(self, surface: pygame.Surface, settings: Settings,
                      selected: int = 0) -> list[Button]:
        self._draw_menu_bg(surface)
        panel = pygame.Rect(180, 40, 920, 640)
        self._panel(surface, panel)
        cx = panel.centerx
        draw_text(surface, "设置", 40, ACCENT, (cx, panel.y + 42),
                  anchor="center", bold=True)
        buttons: list[Button] = []
        rows = (("音乐音量", "music", settings.music),
                ("音效音量", "sfx", settings.sfx))
        for row, (label, key, value) in enumerate(rows):
            y = panel.y + 112 + row * 54
            draw_text(surface, label, 24, HUD_TEXT,
                      (panel.x + 50, y + 22), anchor="midleft")
            minus = Button(f"{key}-", "−", pygame.Rect(panel.x + 460, y, 52, 44))
            plus = Button(f"{key}+", "＋", pygame.Rect(panel.x + 620, y, 52, 44))
            buttons.extend((minus, plus))
            draw_button(surface, minus, selected == len(buttons) - 2)
            draw_button(surface, plus, selected == len(buttons) - 1)
            draw_text(surface, str(value), 28, ACCENT,
                      (panel.x + 540, y + 22), anchor="center", bold=True)
        mode_label = "全屏" if settings.fullscreen else "窗口"
        full = Button("fullscreen", f"显示模式：{mode_label}",
                      pygame.Rect(panel.x + 460, panel.y + 226, 212, 44))
        buttons.append(full)
        draw_button(surface, full, selected == len(buttons) - 1)
        pygame.draw.line(surface, (72, 92, 130),
                         (panel.x + 40, panel.y + 296),
                         (panel.right - 40, panel.y + 296), 1)
        self._draw_key_legend(surface, panel.x + 50, panel.y + 322)
        back = Button("back", "返回主菜单",
                      pygame.Rect(cx - 130, panel.bottom - 66, 260, 48))
        buttons.append(back)
        draw_button(surface, back, selected == len(buttons) - 1)
        return buttons

    def draw_overlay(self, surface: pygame.Surface, title: str, lines: list[str],
                     actions: list[tuple[str, str]] | None = None,
                     selected: int = 0) -> list[Button]:
        """模态浮层（暂停/二次确认/结算）；返回可点击按钮。"""
        dim = pygame.Surface(self.size, pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        surface.blit(dim, (0, 0))
        actions = actions or []
        panel_h = 150 + len(lines) * 32 + len(actions) * 58
        panel = pygame.Rect((CANVAS_W - 640) // 2, (CANVAS_H - panel_h) // 2, 640, panel_h)
        self._panel(surface, panel)
        draw_text(surface, title, 40, ACCENT, (panel.centerx, panel.y + 48),
                  anchor="center", bold=True)
        y = panel.y + 98
        for line in lines:
            draw_text(surface, line, 22, HUD_TEXT, (panel.x + 70, y))
            y += 32
        y += 12
        buttons: list[Button] = []
        for i, (label, action) in enumerate(actions):
            rect = pygame.Rect(panel.centerx - 140, y + i * 58, 280, 46)
            button = Button(action, label, rect)
            buttons.append(button)
            draw_button(surface, button, i == selected)
        return buttons

    def draw_pause_settings(self, surface: pygame.Surface, settings: Settings,
                            selected: int = 0) -> list[Button]:
        """暂停态下的设置浮层：按键说明 + 音量/显示模式即时调整。"""
        dim = pygame.Surface(self.size, pygame.SRCALPHA)
        dim.fill((0, 0, 0, 185))
        surface.blit(dim, (0, 0))
        panel = pygame.Rect((CANVAS_W - 760) // 2, (CANVAS_H - 600) // 2, 760, 600)
        self._panel(surface, panel)
        draw_text(surface, "设置", 36, ACCENT, (panel.centerx, panel.y + 38),
                  anchor="center", bold=True)
        buttons: list[Button] = []
        rows = (("音乐音量", "music", settings.music),
                ("音效音量", "sfx", settings.sfx))
        for row, (label, key, value) in enumerate(rows):
            y = panel.y + 100 + row * 50
            draw_text(surface, label, 22, HUD_TEXT,
                      (panel.x + 44, y + 20), anchor="midleft")
            minus = Button(f"{key}-", "−", pygame.Rect(panel.x + 430, y, 48, 40))
            plus = Button(f"{key}+", "＋", pygame.Rect(panel.x + 590, y, 48, 40))
            buttons.extend((minus, plus))
            draw_button(surface, minus, selected == len(buttons) - 2)
            draw_button(surface, plus, selected == len(buttons) - 1)
            draw_text(surface, str(value), 26, ACCENT,
                      (panel.x + 510, y + 20), anchor="center", bold=True)
        mode_label = "全屏" if settings.fullscreen else "窗口"
        full = Button("fullscreen", f"显示模式：{mode_label}",
                      pygame.Rect(panel.x + 430, panel.y + 212, 188, 40))
        buttons.append(full)
        draw_button(surface, full, selected == len(buttons) - 1)
        pygame.draw.line(surface, (72, 92, 130),
                         (panel.x + 36, panel.y + 282),
                         (panel.right - 36, panel.y + 282), 1)
        self._draw_key_legend(surface, panel.x + 44, panel.y + 302)
        back = Button("cancel", "返回",
                      pygame.Rect(panel.centerx - 110, panel.bottom - 58, 220, 42))
        buttons.append(back)
        draw_button(surface, back, selected == len(buttons) - 1)
        return buttons

    # —— 菜单辅助 ——

    def _draw_menu_bg(self, surface: pygame.Surface) -> None:
        # 纯代码绘制的暗色视差动态背景（无贴图、无抗锯齿）
        if self._menu_anim is None:
            from .menu_bg import MenuBackground
            self._menu_anim = MenuBackground((CANVAS_W, CANVAS_H))
        self._menu_anim.draw(surface)

    def _logo_image(self) -> pygame.Surface | None:
        if self._logo is None:
            try:
                image = self._load_image("logo.png")
                self._logo = pygame.transform.scale(
                    image, (MENU_LOGO_SIZE, MENU_LOGO_SIZE))   # nearest 像素锐利
            except (OSError, pygame.error):
                return None
        return self._logo

    def _draw_pixel_title(self, surface: pygame.Surface, text: str,
                          cx: int, cy: int) -> None:
        """呼吸缩放 + 硬边像素描边阴影的标题。"""
        scale = 1.0 + 0.05 * (0.5 + 0.5 * math.sin(self.time * 1.6))
        base = int(52 * scale)
        f = get_font(base, bold=True)
        color = ACCENT
        # 硬边描边阴影（偏移实色块，逐方向重绘，无 blur）
        offsets = ((-3, -3), (3, -3), (-3, 3), (3, 3), (0, -4), (0, 4),
                   (-4, 0), (4, 0))
        img_shadow = f.render(text, False, (8, 10, 24))
        sw, sh = img_shadow.get_size()
        dx = sw // 2
        for ox, oy in offsets:
            surface.blit(img_shadow, (cx - dx + ox, cy - sh // 2 + oy))
        img = f.render(text, False, color)
        surface.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))

    @staticmethod
    def _panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, (10, 15, 27, 232), layer.get_rect(), border_radius=18)
        pygame.draw.rect(layer, ACCENT, layer.get_rect(), width=2, border_radius=18)
        surface.blit(layer, rect.topleft)

    def _draw_level_card(self, surface: pygame.Surface, rect: pygame.Rect,
                         info: LevelInfo, profile: Profile, unlocked: bool,
                         selected: bool, is_continue: bool = False) -> None:
        fill = (24, 34, 54, 235) if unlocked else (22, 24, 30, 215)
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, fill, layer.get_rect(), border_radius=16)
        pygame.draw.rect(layer, ACCENT if selected else (72, 92, 130),
                         layer.get_rect(), width=3 if selected else 2, border_radius=16)
        surface.blit(layer, rect.topleft)
        id_color = ACCENT if unlocked else (120, 128, 142)
        draw_text(surface, info.id, 34, id_color, (rect.x + 28, rect.y + 22), bold=True)
        draw_text(surface, info.name, 24, HUD_TEXT if unlocked else (120, 128, 142),
                  (rect.x + 28, rect.y + 70))
        theme_name = THEMES.get(info.theme, {}).get("name", info.theme)
        draw_text(surface, f"主题 {theme_name}", 18, HUD_SUB, (rect.x + 28, rect.y + 112))
        best = profile.best_times.get(info.id)
        draw_text(surface, "最佳 " + (self._format_time(best) if best else "--:--.-"),
                  18, HUD_SUB, (rect.x + 28, rect.y + 138))
        if not info.available:
            draw_text(surface, "暂不可用", 22, DANGER,
                      (rect.right - 24, rect.y + 40), anchor="topright")
        elif not unlocked:
            draw_text(surface, "未解锁", 22, (140, 148, 162),
                      (rect.right - 24, rect.y + 40), anchor="topright")
        elif is_continue:
            draw_text(surface, "继续", 20, ACCENT,
                      (rect.right - 22, rect.y + 38), anchor="topright", bold=True)

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes = int(seconds // 60)
        return f"{minutes:02d}:{seconds % 60:04.1f}"


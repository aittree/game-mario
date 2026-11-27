# -*- coding: utf-8 -*-
"""程序入口与主循环（docs/02 §2 应用层 / docs/03 §10）。

界面状态：menu / select / settings / game / clear / over；
暂停与二次确认用 `dialog` 模态，除游戏外任何界面都不推进游戏时间。
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import pygame

from src.audio import Audio
from src.config import (
    APP_NAME,
    CANVAS_H,
    CANVAS_W,
    CLEAR_HOLD_MS,
    CLEAR_SLIDE_MS,
    FPS,
    LIVES_START,
    MAX_SUBSTEPS,
    PHYSICS_DT,
)
from src.game import LevelError, LevelSession, SessionState
from src.keymap import Keymap
from src.levels import LevelInfo, load_level_data, load_level_index
from src.resource import resource_path
from src.storage import (
    Profile,
    load_profile,
    record_time,
    save_profile,
    unlock_next,
)
from src.ui.display import Display
from src.ui.effects import Effects
from src.ui.renderer import Renderer
from src.ui.widgets import Button, hit

# 事件 → 音效（唯一的声音入口，docs/03 §10）
SFX_BY_EVENT = {
    "jump": "jump", "coin": "coin", "stomp": "stomp", "bump": "bump",
    "brick_break": "brick", "powerup": "powerup", "powerdown": "powerdown",
    "fire": "fire", "death": "death", "clear": "clear",
    "checkpoint": "checkpoint", "oneup": "oneup", "gameover": "death",
}


def _enable_dpi_awareness() -> None:
    """Windows 高 DPI 下避免系统把画面二次拉伸（MAN-40）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass


def _format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes:02d}:{seconds % 60:04.1f}"


class GameApp:
    def __init__(self):
        _enable_dpi_awareness()
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.profile: Profile = load_profile()
        self.display = Display(self.profile.settings.fullscreen, APP_NAME)
        # 关闭文本输入/输入法组词：否则中文输入法会把 X 等字母键当成拼音输入吞掉，
        # 表现为按键无反应、角色无法移动，ESC 第一次只关掉输入法候选框。
        pygame.key.stop_text_input()
        try:
            pygame.display.set_icon(
                pygame.image.load(resource_path("assets", "icon.png")))
        except (OSError, pygame.error):
            pass                                      # 缺图标不影响启动
        self.audio = Audio(self.profile.settings.music, self.profile.settings.sfx)
        self.renderer = Renderer()
        self.keymap = Keymap()
        self.clock = pygame.time.Clock()
        self.levels = load_level_index()

        self.screen = "menu"
        self.dialog: str | None = None                # None / pause / restart
        self.session: LevelSession | None = None
        self.level_index = 0
        self.level_base_score = 0
        self.selected = 0
        self.buttons: list[Button] = []
        self.accumulator = 0.0
        self.play_seconds = 0.0
        self.clear_wait = 0.0
        self.result: dict | None = None
        self.result_snap = None
        self.effects = Effects()
        self.running = True

        # 黑幕转场：淡出(到黑)→执行关卡切换→淡入(回显)
        self._fade_alpha = 0
        self._fade_phase: str | None = None        # None / "out" / "in"
        self._fade_pending: Callable[[], None] | None = None
        self._black = pygame.Surface((CANVAS_W, CANVAS_H))
        self._black.fill((0, 0, 0))

    # —— 主循环 ——

    def run(self) -> None:
        while self.running:
            frame_ms = self.clock.tick(FPS)
            dt = min(frame_ms / 1000.0, 0.05)          # 切窗口后防瞬移
            for event in pygame.event.get():
                self._handle_event(event)
            self._update(dt)
            self._draw()
            self.display.present()
        self._shutdown()

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self._on_key(event.key)
        elif event.type == pygame.KEYUP:
            self.keymap.keyup(event.key)
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.keymap.clear()            # 失焦清空按住状态，避免按键「卡住」
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.display.to_canvas(event.pos)
            if pos is not None:
                self._on_click(pos)
        elif event.type == pygame.MOUSEMOTION:
            pos = self.display.to_canvas(event.pos)
            if pos is not None:
                self._on_hover(pos)

    def _on_key(self, key: int) -> None:
        if key == pygame.K_F11:
            self._toggle_fullscreen()
            return
        if self.screen == "game":
            if self.dialog is None:
                if key in (pygame.K_ESCAPE, pygame.K_p):
                    self._open_pause()
                else:
                    self.keymap.keydown(key)           # 游戏键由 keymap 记录
                return
            if key in (pygame.K_ESCAPE, pygame.K_p):
                if self.dialog == "restart":
                    self.dialog = "pause"
                    self.selected = 0
                elif self.dialog == "pause_settings":
                    self.dialog = "pause"
                    self.selected = 0
                else:
                    self._resume_game()
                return
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._activate_selected()
            else:
                self._move_selection(key)
            return

        if key == pygame.K_ESCAPE:
            if self.screen == "menu":
                self.running = False
            else:
                self._go_menu()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._activate_selected()
        else:
            self._move_selection(key)

    def _move_selection(self, key: int) -> None:
        if not self.buttons:
            return
        if key in (pygame.K_UP, pygame.K_LEFT):
            step = -1
        elif key in (pygame.K_DOWN, pygame.K_RIGHT):
            step = 1
        else:
            return
        index = self.selected
        for _ in range(len(self.buttons)):
            index = (index + step) % len(self.buttons)
            if self.buttons[index].enabled:
                break
        if index != self.selected:
            self.selected = index
            self.audio.play("menu")

    def _activate_selected(self) -> None:
        if 0 <= self.selected < len(self.buttons):
            button = self.buttons[self.selected]
            if button.enabled:
                self._activate(button.action)

    def _on_hover(self, pos: tuple[int, int]) -> None:
        button = hit(self.buttons, pos)
        if button is None:
            return
        index = self.buttons.index(button)
        if index != self.selected:
            self.selected = index
            if button.enabled:
                self.audio.play("menu")

    def _on_click(self, pos: tuple[int, int]) -> None:
        button = hit(self.buttons, pos)
        if button is None or not button.enabled:
            return
        self.selected = self.buttons.index(button)
        self.audio.play("menu")
        self._activate(button.action)

    # —— 动作分发 ——

    def _activate(self, action: str) -> None:
        if action == "quit":
            self.running = False
        elif action == "start":
            playable = [i for i, info in enumerate(self.levels)
                        if i < self.profile.unlocked and info.available]
            self._change_screen("select", playable[-1] if playable else 0)
        elif action == "open_settings":
            self._change_screen("settings")
        elif action == "back":
            self._go_menu()
        elif action.startswith("level:"):
            self._select_level(int(action.split(":", 1)[1]))
        elif action in ("music-", "music+", "sfx-", "sfx+"):
            self._adjust_volume(action)
        elif action == "fullscreen":
            self._toggle_fullscreen()
        elif action == "resume":
            self._resume_game()
        elif action == "pause_settings":
            self.dialog = "pause_settings"
            self.selected = 0
        elif action == "restart":
            self.dialog = "restart"
            self.selected = 0
        elif action == "confirm_restart":
            self.dialog = None
            if self.session is not None:
                lives = self.session.snapshot().lives
                self._request_start(self.level_index, lives, self.level_base_score)
        elif action == "cancel":
            self.dialog = "pause"
            self.selected = 0
        elif action == "menu":
            self._go_menu()
        elif action == "next":
            self._next_level()
        elif action == "retry":
            self._retry()

    def _select_level(self, index: int) -> None:
        if not (0 <= index < len(self.levels)):
            return
        if index >= self.profile.unlocked or not self.levels[index].available:
            return
        self._request_start(index, LIVES_START, 0)

    def _next_level(self) -> None:
        if self.result_snap is None:
            return
        if self.level_index + 1 < len(self.levels):
            self._request_start(self.level_index + 1,
                                self.result_snap.lives, self.result_snap.score)

    def _retry(self) -> None:
        """结算页重玩：通关后保留生命与已得分数，失败后从头开始。"""
        if self.screen == "clear" and self.result_snap is not None:
            self._request_start(self.level_index, self.result_snap.lives,
                                self.level_base_score)
        else:
            self._request_start(self.level_index, LIVES_START, 0)

    # —— 界面切换 ——

    def _change_screen(self, screen: str, selected: int = 0) -> None:
        self.screen = screen
        self.dialog = None
        self.selected = max(0, selected)
        self.buttons = []
        self.keymap.clear()
        self.audio.stop_bgm()

    def _go_menu(self) -> None:
        self.session = None
        self.result = None
        self.result_snap = None
        self._change_screen("menu")

    def _open_pause(self) -> None:
        self.dialog = "pause"
        self.selected = 0
        self.keymap.clear()
        self.audio.play("pause")
        self.audio.pause()

    def _resume_game(self) -> None:
        self.dialog = None
        self.selected = 0
        self.keymap.clear()
        self.audio.play("pause")
        self.audio.resume()

    def _toggle_fullscreen(self) -> None:
        enabled = not self.profile.settings.fullscreen
        self.profile.settings.fullscreen = enabled
        self.display.set_fullscreen(enabled)
        pygame.key.stop_text_input()          # 重建窗口后再次禁用输入法
        save_profile(self.profile)

    def _adjust_volume(self, action: str) -> None:
        delta = 10 if action.endswith("+") else -10
        settings = self.profile.settings
        if action.startswith("music"):
            settings.music = max(0, min(100, settings.music + delta))
            self.audio.set_music_volume(settings.music)
        else:
            settings.sfx = max(0, min(100, settings.sfx + delta))
            self.audio.set_sfx_volume(settings.sfx)
        save_profile(self.profile)
        if self.dialog is not None:              # 暂停态下保持 BGM 暂停，避免调高音量时误播放
            self.audio.pause()

    # —— 关卡流程 ——

    def _start_level(self, index: int, lives: int, score: int) -> None:
        if not (0 <= index < len(self.levels)):
            return
        info = self.levels[index]
        if not info.available:
            return
        try:
            session = LevelSession.from_dict(load_level_data(info), self.profile,
                                             lives=lives, score=score)
        except (OSError, ValueError, LevelError):
            self.levels[index] = LevelInfo(info.path, info.id, "暂不可用",
                                           info.theme, info.cols, False)
            return
        self.session = session
        self.level_index = index
        self.level_base_score = score
        self.screen = "game"
        self.dialog = None
        self.selected = 0
        self.buttons = []
        self.accumulator = 0.0
        self.play_seconds = 0.0
        self.clear_wait = 0.0
        self.result = None
        self.result_snap = None
        self.effects = Effects()
        self.keymap.clear()
        self.audio.stop_bgm()
        self.audio.play_bgm(info.theme)

    # —— 黑幕转场 ——

    _FADE_SPEED = 900                              # alpha/秒，约 0.28s 到全黑

    def _request_start(self, index: int, lives: int, score: int) -> None:
        """请求切入关卡：先淡出到黑，再切换，最后淡入。"""
        if self._fade_phase is not None:
            return
        self._fade_pending = lambda idx=index, lv=lives, sc=score: \
            self._start_level(idx, lv, sc)
        self._fade_alpha = 0
        self._fade_phase = "out"

    def _advance_fade(self, dt: float) -> None:
        if self._fade_phase == "out":
            self._fade_alpha = min(255, self._fade_alpha + int(self._FADE_SPEED * dt))
            if self._fade_alpha >= 255 and self._fade_pending is not None:
                cb = self._fade_pending
                self._fade_pending = None
                cb()                                   # 全黑后切换关卡
                self._fade_phase = "in"
        elif self._fade_phase == "in":
            self._fade_alpha = max(0, self._fade_alpha - int(self._FADE_SPEED * dt))
            if self._fade_alpha <= 0:
                self._fade_phase = None

    def _update(self, dt: float) -> None:
        self._advance_fade(dt)
        if self._fade_phase == "out":
            # 淡出期间保持当前界面动画，不推进游戏逻辑
            self.renderer.update(dt)
            return
        if self.screen != "game" or self.session is None or self.dialog is not None:
            self.renderer.update(dt)              # 菜单/设置等界面推进背景与按钮动画
            return
        intent = self.keymap.sample()
        self.accumulator += dt
        steps = 0
        while self.accumulator >= PHYSICS_DT and steps < MAX_SUBSTEPS:
            self.session.step(intent, PHYSICS_DT)
            if self.session.state is SessionState.RUNNING:
                self.play_seconds += PHYSICS_DT
            self.accumulator -= PHYSICS_DT
            steps += 1
        if steps == MAX_SUBSTEPS:
            self.accumulator = 0.0                    # 丢弃积压，避免穿透地形
        # 死亡时停掉 BGM，重生（重新回到 RUNNING）后恢复关卡 BGM
        if (self.session.state is SessionState.RUNNING
                and self.audio.current_bgm is None):
            self.audio.play_bgm(self.levels[self.level_index].theme)
        self._consume_events()
        self.effects.update(dt)
        self.renderer.update(dt)

        snap = self.session.snapshot()
        if snap.state is SessionState.CLEARED:
            self.clear_wait += dt
            if self.clear_wait >= (CLEAR_SLIDE_MS + CLEAR_HOLD_MS) / 1000.0:
                self._finish_clear(snap)
        elif snap.state is SessionState.FAILED:
            self._finish_game_over(snap)

    def _consume_events(self) -> None:
        assert self.session is not None
        snap = self.session.snapshot()
        for hook in self.session.effects_hooks:
            self.effects.on_model_hook(hook, snap)
        self.session.effects_hooks.clear()
        for event in self.session.take_events():
            if event.kind == "death":
                self.audio.stop_bgm()                 # 死亡即停 BGM，只留死亡 jingle
            sound = SFX_BY_EVENT.get(event.kind)
            if sound:
                self.audio.play(sound)
            self.effects.on_event(event, snap)

    def _finish_clear(self, snap) -> None:
        info = self.levels[self.level_index]
        new_best = record_time(self.profile, snap.level_id, self.play_seconds)
        unlocked = unlock_next(self.profile, self.level_index, len(self.levels))
        self.profile.best_score = max(self.profile.best_score, snap.score)
        save_profile(self.profile)
        self.result_snap = snap
        self.result = {"level": info, "best": new_best, "unlocked": unlocked,
                       "all_clear": self.level_index >= len(self.levels) - 1}
        self.screen = "clear"
        self.dialog = None
        self.selected = 0
        self.buttons = []
        self.keymap.clear()
        self.audio.stop_bgm()

    def _finish_game_over(self, snap) -> None:
        info = self.levels[self.level_index]
        self.profile.best_score = max(self.profile.best_score, snap.score)
        save_profile(self.profile)
        self.result_snap = snap
        self.result = {"level": info, "all_clear": False}
        self.screen = "over"
        self.dialog = None
        self.selected = 0
        self.buttons = []
        self.keymap.clear()
        self.audio.stop_bgm()

    # —— 绘制 ——

    def _draw(self) -> None:
        canvas = self.display.canvas
        if self.screen == "menu":
            self.buttons = self.renderer.draw_menu(canvas, self.profile, self.selected)
        elif self.screen == "select":
            self.buttons = self.renderer.draw_level_select(
                canvas, self.profile, self.levels, self.selected)
        elif self.screen == "settings":
            self.buttons = self.renderer.draw_settings(
                canvas, self.profile.settings, self.selected)
        elif self.screen == "game":
            self._draw_game(canvas)
        elif self.screen in ("clear", "over"):
            self._draw_result(canvas)
        if self._fade_alpha > 0:
            self._black.set_alpha(self._fade_alpha)
            canvas.blit(self._black, (0, 0))

    def _draw_game(self, canvas: pygame.Surface) -> None:
        if self.session is None:
            canvas.fill((0, 0, 0))
            return
        snap = self.session.snapshot()
        self.renderer.draw_world(canvas, snap, self.effects)
        if self.dialog == "pause":
            lines = [f"分数 {snap.score:06d}", f"金币 ×{snap.coins}",
                     f"关卡 {snap.level_id}　时间 {snap.time_units}"]
            self.buttons = self.renderer.draw_overlay(
                canvas, "暂停", lines,
                [("继续", "resume"), ("设置", "pause_settings"),
                 ("重玩本关", "restart"), ("返回主菜单", "menu")],
                self.selected)
        elif self.dialog == "pause_settings":
            self.buttons = self.renderer.draw_pause_settings(
                canvas, self.profile.settings, self.selected)
        elif self.dialog == "restart":
            self.buttons = self.renderer.draw_overlay(
                canvas, "确认重玩", ["重玩后本关分数清零，生命保持不变。"],
                [("确认重玩", "confirm_restart"), ("取消", "cancel")], self.selected)
        else:
            self.buttons = []

    def _draw_result(self, canvas: pygame.Surface) -> None:
        if self.session is not None:
            self.renderer.draw_world(canvas, self.result_snap or self.session.snapshot(),
                                     self.effects)
        else:
            canvas.fill((10, 14, 24))
        result = self.result or {}
        info = result.get("level")
        snap = self.result_snap
        if snap is None:
            self.buttons = []
            return
        level_label = (f"{info.id} {info.name}"
                       if isinstance(info, LevelInfo) else snap.level_id)
        if self.screen == "clear":
            title = "全部通关" if result.get("all_clear") else "关卡完成"
            lines = [f"{level_label}",
                     f"本关分数 {snap.score:06d}　金币 ×{snap.coins}",
                     f"剩余时间 {snap.time_units}　时间奖励 +{snap.clear_bonus or 0}",
                     f"本关用时 {_format_time(self.play_seconds)}"]
            best_time = self.profile.best_times.get(snap.level_id)
            best_note = "（新纪录）" if result.get("best") else ""
            lines.append(f"本关最佳 {_format_time(best_time or self.play_seconds)}{best_note}")
            actions = []
            if not result.get("all_clear"):
                actions.append(("下一关", "next"))
            actions += [("重玩本关", "retry"), ("返回主菜单", "menu")]
        else:
            title = "游戏结束"
            lines = [f"{level_label}",
                     f"最终分数 {snap.score:06d}　金币 ×{snap.coins}",
                     f"用时 {_format_time(self.play_seconds)}"]
            actions = [("重新开始", "retry"), ("返回主菜单", "menu")]
        self.buttons = self.renderer.draw_overlay(canvas, title, lines, actions,
                                                  self.selected)

    def _shutdown(self) -> None:
        save_profile(self.profile)
        pygame.quit()


def main() -> None:
    GameApp().run()


if __name__ == "__main__":
    main()

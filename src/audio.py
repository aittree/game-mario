"""BGM / 音效（docs/03 §8.3）。

无声卡或缺少单个文件时安全降级，不影响游戏逻辑与帧率。
"""

from __future__ import annotations

import pygame

from .resource import resource_path

SFX_FILES = {
    "jump": "sfx_jump.wav", "coin": "sfx_coin.wav", "stomp": "sfx_stomp.wav",
    "bump": "sfx_bump.wav", "brick": "sfx_brick.wav", "powerup": "sfx_powerup.wav",
    "powerdown": "sfx_powerdown.wav", "fire": "sfx_fire.wav", "death": "sfx_death.wav",
    "clear": "sfx_clear.wav", "checkpoint": "sfx_checkpoint.wav", "oneup": "sfx_oneup.wav",
    "menu": "sfx_menu.wav", "pause": "sfx_pause.wav",
}
BGM_FILES = {
    "grass": "bgm_grass.wav", "cave": "bgm_cave.wav",
    "sky": "bgm_sky.wav", "castle": "bgm_castle.wav",
}


class Audio:
    def __init__(self, music_volume: int = 70, sfx_volume: int = 80):
        self.available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music_volume = music_volume
        self.sfx_volume = sfx_volume
        self.current_bgm: str | None = None
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.available = True
        except pygame.error:
            return                                  # 无声卡：所有调用降级为空操作
        for key, name in SFX_FILES.items():
            try:
                self.sounds[key] = pygame.mixer.Sound(
                    resource_path("assets", "audio", name))
            except (pygame.error, FileNotFoundError):
                continue                            # 缺单个音效不影响其他
        pygame.mixer.music.set_volume(self.music_volume / 100)

    def play(self, name: str) -> None:
        if not self.available or self.sfx_volume == 0:
            return
        snd = self.sounds.get(name)
        if snd:
            snd.set_volume(self.sfx_volume / 100)
            snd.play()

    def play_bgm(self, key: str) -> None:
        """切主题 BGM：同一首不重播。"""
        if not self.available or key == self.current_bgm:
            return
        try:
            pygame.mixer.music.load(resource_path("assets", "audio", BGM_FILES[key]))
        except (pygame.error, FileNotFoundError, KeyError):
            self.current_bgm = None
            return
        pygame.mixer.music.set_volume(self.music_volume / 100)
        pygame.mixer.music.play(-1)
        self.current_bgm = key

    def pause(self) -> None:
        if self.available:
            pygame.mixer.music.pause()

    def resume(self) -> None:
        if self.available and self.music_volume > 0:
            pygame.mixer.music.unpause()

    def stop_bgm(self) -> None:
        """返回菜单或结算时停止当前 BGM（下次进入关卡会重新播放）。"""
        if not self.available:
            return
        pygame.mixer.music.stop()
        self.current_bgm = None

    def set_music_volume(self, value: int) -> None:
        self.music_volume = max(0, min(100, value))
        if not self.available:
            return
        pygame.mixer.music.set_volume(self.music_volume / 100)
        if self.music_volume == 0:
            pygame.mixer.music.pause()
        else:
            pygame.mixer.music.unpause()

    def set_sfx_volume(self, value: int) -> None:
        self.sfx_volume = max(0, min(100, value))

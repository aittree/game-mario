"""存档与进度（docs/03 §8.2）。

路径：%APPDATA%\\SuperTreeio\\save.json。
容错原则：读失败一律降级为默认 Profile；写失败只记录，不抛出。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .config import APP_ID

APP_DIR = Path(os.environ.get("APPDATA", ".")) / APP_ID
SAVE_FILE = APP_DIR / "save.json"
TMP_FILE = APP_DIR / "save.tmp"
CRASH_FILE = APP_DIR / "crash.log"


class Settings:
    def __init__(self, fullscreen: bool = False, music: int = 70,
                 sfx: int = 80):
        self.fullscreen = fullscreen
        self.music = music
        self.sfx = sfx


class Profile:
    def __init__(self, best_score: int = 0, coins_total: int = 0,
                 unlocked: int = 1, best_times: dict[str, float] | None = None,
                 settings: Settings | None = None):
        self.best_score = best_score
        self.coins_total = coins_total
        self.unlocked = unlocked
        self.best_times = best_times if best_times is not None else {}
        self.settings = settings if settings is not None else Settings()


def _log(message: str) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(CRASH_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
    except OSError:
        pass


def _as_int(value, default: int = 0) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def load_profile() -> Profile:
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Profile()
    if not isinstance(data, dict):
        return Profile()

    profile = Profile(
        best_score=max(0, _as_int(data.get("best_score"))),
        coins_total=max(0, _as_int(data.get("coins_total"))),
        unlocked=_clamp(_as_int(data.get("unlocked"), 1), 1, 4),
    )

    times = data.get("best_times")
    if isinstance(times, dict):
        for level_id, seconds in times.items():
            if isinstance(level_id, str) and isinstance(seconds, (int, float)) and seconds > 0:
                profile.best_times[level_id] = float(seconds)

    settings = data.get("settings")
    if isinstance(settings, dict):
        profile.settings = Settings(
            fullscreen=bool(settings.get("fullscreen", False)),
            music=_clamp(_as_int(settings.get("music"), 70), 0, 100),
            sfx=_clamp(_as_int(settings.get("sfx"), 80), 0, 100),
        )
    return profile


def save_profile(profile: Profile) -> None:
    payload = {
        "best_score": profile.best_score,
        "coins_total": profile.coins_total,
        "unlocked": _clamp(profile.unlocked, 1, 4),
        "best_times": profile.best_times,
        "settings": {
            "fullscreen": profile.settings.fullscreen,
            "music": _clamp(profile.settings.music, 0, 100),
            "sfx": _clamp(profile.settings.sfx, 0, 100),
        },
    }
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        TMP_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        os.replace(TMP_FILE, SAVE_FILE)
    except OSError as exc:
        _log(f"save_profile failed: {exc}")


def record_time(profile: Profile, level_id: str, seconds: float) -> bool:
    """只在更快时写入最佳用时，返回是否为新纪录。"""
    if seconds <= 0:
        return False
    old = profile.best_times.get(level_id)
    if old is None or seconds < old:
        profile.best_times[level_id] = float(seconds)
        return True
    return False


def unlock_next(profile: Profile, level_index: int, total: int) -> bool:
    """通关第 level_index（0 起）后解锁下一关，返回解锁进度是否变化。"""
    if total <= 0:
        return False
    nxt = _clamp(level_index + 2, 1, min(total, 4))
    if nxt > profile.unlocked:
        profile.unlocked = nxt
        return True
    return False

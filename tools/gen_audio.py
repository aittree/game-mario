"""生成 4 首 BGM 与 14 个音效（22050 Hz / 单声道 / 16-bit）。

文件名与时长见 docs/08 §3；BGM 首尾各做 0.3 s 淡入淡出，便于无缝循环。
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 22050
OUT = Path(__file__).resolve().parents[1] / "assets" / "audio"
RNG = np.random.default_rng(20261125)


def midi(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def oscillator(freq: np.ndarray | float, n: int, kind: str = "square", duty: float = 0.5) -> np.ndarray:
    f = np.full(n, freq, dtype=np.float64) if np.isscalar(freq) else np.asarray(freq, dtype=np.float64)
    phase = np.cumsum(f) / SR
    frac = phase - np.floor(phase)
    if kind == "sine":
        return np.sin(2 * np.pi * phase)
    if kind == "triangle":
        return 2 * np.abs(2 * frac - 1) - 1
    if kind == "saw":
        return 2 * frac - 1
    return np.where(frac < duty, 1.0, -1.0)


def envelope(n: int, attack: float = 0.008, release: float = 0.06, sustain: float = 0.75) -> np.ndarray:
    env = np.full(n, sustain, dtype=np.float64)
    a = min(n, max(1, int(attack * SR)))
    r = min(n - a, max(1, int(release * SR)))
    env[:a] = np.linspace(0, sustain, a)
    if r > 0:
        env[-r:] = np.linspace(sustain, 0, r)
    return env


def tone(freq: float, dur: float, kind: str = "square", gain: float = 0.3,
         duty: float = 0.5, attack: float = 0.008, release: float = 0.06) -> np.ndarray:
    n = max(1, int(dur * SR))
    return oscillator(freq, n, kind, duty) * envelope(n, attack, release) * gain


def sweep(f0: float, f1: float, dur: float, kind: str = "square", gain: float = 0.3) -> np.ndarray:
    n = max(1, int(dur * SR))
    freq = np.linspace(f0, f1, n)
    t = np.arange(n) / SR
    sig = oscillator(freq, n, kind) * np.exp(-3.5 * t) * gain
    return sig


def noise(dur: float, gain: float = 0.2, decay: float = 26.0, highpass: bool = False) -> np.ndarray:
    n = max(1, int(dur * SR))
    sig = RNG.standard_normal(n)
    if highpass:
        sig = np.diff(sig, prepend=0.0)
    t = np.arange(n) / SR
    return sig * np.exp(-decay * t) * gain


def mix(*parts: np.ndarray, length: int | None = None) -> np.ndarray:
    if length is None:
        length = max(len(p) for p in parts)
    out = np.zeros(length, dtype=np.float64)
    for part in parts:
        out[:min(length, len(part))] += part[:length]
    return out


def normalize(sig: np.ndarray, peak: float = 0.8) -> np.ndarray:
    m = float(np.max(np.abs(sig))) if len(sig) else 0.0
    if m > 0:
        sig = sig / m * peak
    return sig


def add(buf: np.ndarray, start: float, sig: np.ndarray) -> None:
    i = int(start * SR)
    if i >= len(buf) or i < 0:
        return
    end = min(len(buf), i + len(sig))
    buf[i:end] += sig[:end - i]


def write_wav(name: str, sig: np.ndarray, seconds: float) -> None:
    n = int(seconds * SR)
    out = np.zeros(n, dtype=np.float64)
    out[:min(n, len(sig))] = sig[:n]
    out = normalize(out, 0.82)
    data = np.clip(out * 32767, -32768, 32767).astype("<i2")
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"wrote {path.name} {seconds:.2f}s")


def build_bgm(seconds: float, bpm: float, roots: list[int], melody: list[int],
              step_beats: float, kind: str = "square", pad: bool = True,
              drums: str = "normal") -> np.ndarray:
    total = np.zeros(int(seconds * SR), dtype=np.float64)
    beat = 60.0 / bpm
    bar = beat * 4
    bar_idx = 0
    t = 0.0
    while t < seconds - 0.01:
        root = roots[bar_idx % len(roots)]
        # 低音
        add(total, t, tone(midi(root), bar * 0.92, "triangle", 0.20, release=0.12))
        add(total, t + beat * 2, tone(midi(root - 5), bar * 0.42, "triangle", 0.12, release=0.10))
        # 和弦铺底
        if pad:
            for interval in (0, 3, 7):
                add(total, t, tone(midi(root + 12 + interval), bar * 0.88, "triangle", 0.035,
                                   attack=0.08, release=0.2))
        # 琶音
        chord = (0, 3, 7, 12)
        for i in range(8):
            note = root + 12 + chord[i % len(chord)]
            add(total, t + i * beat / 2, tone(midi(note), beat * 0.38, "square", 0.045,
                                              duty=0.25, release=0.04))
        # 旋律
        for i, note in enumerate(melody):
            start = t + i * step_beats * beat
            if start >= t + bar:
                break
            add(total, start, tone(midi(note), beat * step_beats * 0.82, kind, 0.16, release=0.08))
        # 打击
        if drums != "none":
            for i in range(4):
                bt = t + i * beat
                if drums == "normal":
                    if i in (0, 2):
                        add(total, bt, sweep(130, 55, 0.14, "sine", 0.22))
                    if i in (1, 3):
                        add(total, bt, mix(noise(0.08, 0.12, 30, True),
                                           tone(180, 0.08, "triangle", 0.08)))
                elif drums == "castle":
                    add(total, bt, sweep(150, 55, 0.12, "sine", 0.18))
                    if i in (1, 3):
                        add(total, bt, noise(0.07, 0.10, 32, True))
                elif drums == "cave":
                    if i == 0:
                        add(total, bt, sweep(100, 45, 0.18, "sine", 0.14))
                for h in (0.5, 1.5):
                    add(total, bt + h * beat, noise(0.03, 0.025, 55, True))
        t += bar
        bar_idx += 1

    n = int(0.3 * SR)
    total[:n] *= np.linspace(0, 1, n)
    total[-n:] *= np.linspace(1, 0, n)
    return total


def sfx_jump() -> np.ndarray:
    return sweep(360, 760, 0.12, "square", 0.32)


def sfx_stomp() -> np.ndarray:
    return mix(noise(0.08, 0.22, 30), sweep(180, 60, 0.08, "square", 0.26))


def sfx_coin() -> np.ndarray:
    return mix(np.concatenate([tone(midi(83), 0.05, "square", 0.22),
                               np.zeros(int(0.01 * SR)),
                               tone(midi(88), 0.05, "square", 0.22)]))


def sfx_powerup() -> np.ndarray:
    notes = [72, 74, 76, 79, 81, 84, 86, 91]
    out = np.zeros(int(0.40 * SR))
    for i, note in enumerate(notes):
        add(out, i * 0.045, tone(midi(note), 0.08, "square", 0.22))
    return out


def sfx_powerdown() -> np.ndarray:
    notes = [84, 79, 72]
    out = np.zeros(int(0.35 * SR))
    for i, note in enumerate(notes):
        add(out, i * 0.10, tone(midi(note), 0.12, "saw", 0.16))
    return out


def sfx_fire() -> np.ndarray:
    return mix(sweep(900, 240, 0.08, "square", 0.24), noise(0.08, 0.08, 38, True))


def sfx_brick() -> np.ndarray:
    return mix(noise(0.16, 0.26, 22), sweep(110, 55, 0.14, "triangle", 0.22))


def sfx_bump() -> np.ndarray:
    return tone(170, 0.10, "square", 0.28, release=0.08)


def sfx_checkpoint() -> np.ndarray:
    return mix(tone(midi(76), 0.12, "triangle", 0.24), np.concatenate([np.zeros(int(0.13 * SR)),
                                                                        tone(midi(83), 0.17, "triangle", 0.24)]))


def sfx_oneup() -> np.ndarray:
    out = np.zeros(int(0.35 * SR))
    for i, note in enumerate((84, 88, 91)):
        add(out, i * 0.09, tone(midi(note), 0.10, "square", 0.22))
    return out


def sfx_clear() -> np.ndarray:
    out = np.zeros(int(1.60 * SR))
    seq = [(72, 0.16), (76, 0.16), (79, 0.16), (84, 0.30), (86, 0.30), (91, 0.45)]
    t = 0.0
    for note, dur in seq:
        add(out, t, tone(midi(note), dur * 0.92, "square", 0.22))
        t += dur
    for note in (72, 76, 79):
        add(out, 0.98, tone(midi(note), 0.55, "triangle", 0.08, attack=0.05, release=0.35))
    return out


def sfx_death() -> np.ndarray:
    out = np.zeros(int(1.20 * SR))
    for i, note in enumerate((72, 76, 79, 84, 88)):
        add(out, i * 0.06, tone(midi(note), 0.09, "square", 0.20))
    t = 0.32
    for note, dur in ((83, 0.18), (79, 0.18), (74, 0.22), (67, 0.30)):
        add(out, t, tone(midi(note), dur * 0.9, "triangle", 0.22))
        t += dur
    return out


def sfx_menu() -> np.ndarray:
    return tone(1200, 0.05, "square", 0.25, release=0.02)


def sfx_pause() -> np.ndarray:
    return sweep(680, 460, 0.20, "square", 0.22)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bgms = {
        "bgm_grass": (28.0, 150.0, [48, 45, 41, 43],
                      [72, 76, 79, 76, 77, 81, 84, 81, 79, 76, 72, 74, 74, 72, 69, 67],
                      0.5, "square", True, "normal"),
        "bgm_cave": (26.0, 120.0, [45, 41, 43, 40],
                     [69, 72, 76, 72, 74, 72, 69, 67, 65, 69, 72, 69, 71, 69, 65, 64],
                     1.0, "triangle", True, "cave"),
        "bgm_sky": (30.0, 170.0, [50, 47, 43, 45],
                    [74, 78, 81, 78, 76, 79, 83, 79, 81, 78, 74, 76, 76, 74, 71, 69],
                    0.5, "triangle", True, "normal"),
        "bgm_castle": (24.0, 140.0, [40, 41, 43, 38],
                       [64, 67, 70, 67, 65, 68, 71, 68, 67, 70, 74, 70, 62, 65, 69, 65],
                       0.5, "square", False, "castle"),
    }
    for name, args in bgms.items():
        write_wav(name, build_bgm(*args), args[0])

    sfx = {
        "sfx_jump": (0.12, sfx_jump()),
        "sfx_coin": (0.10, sfx_coin()),
        "sfx_stomp": (0.08, sfx_stomp()),
        "sfx_bump": (0.10, sfx_bump()),
        "sfx_brick": (0.16, sfx_brick()),
        "sfx_powerup": (0.40, sfx_powerup()),
        "sfx_powerdown": (0.35, sfx_powerdown()),
        "sfx_fire": (0.08, sfx_fire()),
        "sfx_death": (1.20, sfx_death()),
        "sfx_clear": (1.60, sfx_clear()),
        "sfx_checkpoint": (0.30, sfx_checkpoint()),
        "sfx_oneup": (0.35, sfx_oneup()),
        "sfx_menu": (0.05, sfx_menu()),
        "sfx_pause": (0.20, sfx_pause()),
    }
    for name, (seconds, sig) in sfx.items():
        write_wav(name, sig, seconds)


if __name__ == "__main__":
    main()

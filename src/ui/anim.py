"""帧动画数据与取帧（docs/03 §9.2、docs/08 §2.3～§2.5）。

精灵表为线性帧序列：本模块只描述「某状态下从第几帧开始、共几帧、每秒几帧」，
真正的切图与绘制由 `renderer.py` 完成。
"""

from __future__ import annotations

from ..entities.base import AnimState


class Clip:
    """一段动画：起始线性帧索引、帧数、播放速度、是否循环。"""

    def __init__(self, start: int, count: int, fps: float, loop: bool = True):
        self.start = start
        self.count = count
        self.fps = fps
        self.loop = loop


def clip_frame(clip: Clip, elapsed: float) -> int:
    """按已播放秒数取当前线性帧索引；非循环动画停在最后一帧。"""
    if clip.count <= 1 or clip.fps <= 0:
        return clip.start
    idx = int(elapsed * clip.fps)
    if clip.loop:
        return clip.start + idx % clip.count
    return clip.start + min(idx, clip.count - 1)


# 玩家精灵表 6 列 × 4 行，行内帧顺序固定（docs/08 §2.3）：
# 行 0：站立 / 跑 1～4；行 1：起跳 / 下落 / 打滑 / 受伤 1～2；
# 行 2：变大 1～2 / 死亡 1～2；大体型行 3 第 0 帧为蹲下。
PLAYER_ANIMS: dict[str, dict[AnimState, Clip]] = {
    "small": {
        AnimState.IDLE: Clip(0, 1, 1.0, False),
        AnimState.RUN: Clip(1, 4, 10.0, True),
        AnimState.SKID: Clip(8, 1, 1.0, False),
        AnimState.JUMP: Clip(6, 1, 1.0, False),
        AnimState.FALL: Clip(7, 1, 1.0, False),
        AnimState.HURT: Clip(9, 2, 12.5, True),
        AnimState.GROW: Clip(12, 2, 10.0, False),
        AnimState.DEAD: Clip(14, 2, 6.25, False),
        AnimState.CROUCH: Clip(0, 1, 1.0, False),
        AnimState.SLIDE: Clip(1, 4, 10.0, True),
    },
    "big": {
        AnimState.IDLE: Clip(0, 1, 1.0, False),
        AnimState.RUN: Clip(1, 4, 9.1, True),
        AnimState.SKID: Clip(8, 1, 1.0, False),
        AnimState.JUMP: Clip(6, 1, 1.0, False),
        AnimState.FALL: Clip(7, 1, 1.0, False),
        AnimState.HURT: Clip(9, 2, 12.5, True),
        AnimState.GROW: Clip(12, 2, 10.0, False),
        AnimState.DEAD: Clip(14, 2, 6.25, False),
        AnimState.CROUCH: Clip(18, 1, 1.0, False),
        AnimState.SLIDE: Clip(1, 4, 9.1, True),
    },
}

# 敌人精灵表 4 列 × 5 行（docs/08 §2.4），行序：巡逻菇、甲壳虫行走、壳、飞行蝠、水管花。
ENEMY_ANIMS: dict[str, Clip] = {
    "patrol_shroom": Clip(0, 2, 5.56, True),
    "shellbug": Clip(4, 2, 6.25, True),
    "shell": Clip(8, 1, 1.0, False),
    "flitter": Clip(12, 2, 8.33, True),
    "pipe_bloom": Clip(16, 2, 5.0, True),
}

# 道具精灵表 4 列 × 3 行（docs/08 §2.5），行序：变大菇、火花、火球。
ITEM_ANIMS: dict[str, Clip] = {
    "mushroom": Clip(0, 1, 1.0, False),
    "fire_flower": Clip(4, 2, 4.0, True),
    "fireball": Clip(8, 4, 20.0, True),
}

# 地形帧动画：问号块两帧 0.4 s 一轮，金币四帧各 0.1 s（docs/08 §2.2）。
QUESTION_FRAME_SECONDS = 0.4
COIN_FRAME_SECONDS = 0.1


def player_clip(sheet: str, state: AnimState) -> Clip:
    """取玩家某状态的动画；未定义状态退回站立，保证绘制不崩。"""
    clips = PLAYER_ANIMS[sheet]
    return clips.get(state, clips[AnimState.IDLE])

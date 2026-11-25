"""实体基类与跨层数据类型（docs/03 §4.1）。

`InputIntent` 放在这里，是为了让 keymap 只依赖纯数据类型而不触碰实体业务逻辑。
"""

from __future__ import annotations

from enum import Enum, auto

from ..config import TILE
from ..physics import Body
from ..tilemap import TileMap


class PowerState(Enum):
    SMALL = auto()
    BIG = auto()
    FIRE = auto()


class AnimState(Enum):
    IDLE = auto()
    RUN = auto()
    SKID = auto()
    JUMP = auto()
    FALL = auto()
    HURT = auto()
    GROW = auto()
    DEAD = auto()
    SLIDE = auto()
    CROUCH = auto()


class EntityType(str, Enum):
    """与关卡 JSON 的 `entities[].type` 一一对应。"""

    PATROL_SHROOM = "patrol_shroom"
    SHELLBUG = "shellbug"
    FLITTER = "flitter"
    PIPE_BLOOM = "pipe_bloom"
    MOVING_PLATFORM = "moving_platform"
    CHECKPOINT = "checkpoint"
    GOAL = "goal"


class WorldView:
    """模型层向实体暴露的只读世界视图，避免实体持有 Game 引用。"""

    def __init__(self, tilemap: TileMap, camera_x: float,
                 player_x: float, width_px: int):
        self.tilemap = tilemap
        self.camera_x = camera_x
        self.player_x = player_x
        self.width_px = width_px


class InputIntent:
    """每帧采样一次的输入意图；jump_pressed / fire_pressed 只在按下的那一帧为 True。"""

    def __init__(self, left: bool = False, right: bool = False,
                 jump_held: bool = False, jump_pressed: bool = False,
                 sprint: bool = False, down: bool = False,
                 fire_pressed: bool = False):
        self.left = left
        self.right = right
        self.jump_held = jump_held
        self.jump_pressed = jump_pressed
        self.sprint = sprint
        self.down = down
        self.fire_pressed = fire_pressed


class Entity:
    kind = "entity"

    def __init__(self, x: float, y: float, w: float, h: float):
        self.body = Body(x, y, w, h)
        self.alive = True
        self.active = False          # 进入相机右侧 200 px 后置 True
        self.anim_state = AnimState.IDLE
        self.anim_frame = 0
        self.anim_timer = 0.0
        self.facing = 1

    @property
    def aabb(self) -> tuple[float, float, float, float]:
        return self.body.aabb

    def on_stomp(self) -> bool:
        """被踩：返回 True 表示可被踩死。默认不可踩。"""
        return False

    @staticmethod
    def on_fireball() -> bool:
        """被火球命中：返回 True 表示可被击杀。默认可被火球击杀。"""
        return True


def place_at(col: int, row: int, w: float, h: float,
             bottom_aligned: bool = True) -> tuple[float, float]:
    """把宽度 w、高度 h 的实体放在 (col,row) 格内；bottom_aligned 时脚底贴齐该格底面。"""
    x = col * TILE + (TILE - w) / 2
    y = (row + 1) * TILE - h if bottom_aligned else row * TILE
    return x, y

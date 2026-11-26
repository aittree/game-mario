# -*- coding: utf-8 -*-
"""全局常量与纯函数（docs/03 §1）。

本模块只允许依赖标准库，禁止依赖其他业务模块——见 docs/02 §2 分层依赖规则。
"""

APP_NAME = "超级树里奥"              # 中文名：窗口标题、界面文案
APP_NAME_EN = "Super Treeio"         # 英文名：徽章、英文标签、发布说明
APP_ID = "SuperTreeio"               # 存档目录 / 内部标识，无空格
VERSION = "1.0.0"

# —— 画布与瓦片 ——
CANVAS_W, CANVAS_H = 1280, 720
TILE = 40
VIEW_COLS = CANVAS_W // TILE          # 32
VIEW_ROWS = 18                        # 720 / 40，与关卡行数一致
HUD_H = 72
FPS = 60

# —— 物理步长 ——
PHYSICS_HZ = 120
PHYSICS_DT = 1.0 / PHYSICS_HZ         # 0.008333 s
MAX_SUBSTEPS = 6                      # 单帧最多物理步数，超出丢弃

# —— 玩家尺寸与手感 ——
PLY_W_SMALL, PLY_H_SMALL = 26, 36
PLY_W_BIG, PLY_H_BIG = 26, 56
GRAVITY = 1280.0         # 与 JUMP_VEL=640 配合，满按跳跃高度约 4 格（160 px）
MAX_FALL = 780.0
JUMP_VEL = 640.0
JUMP_CUT = 0.70          # 松开跳跃键后上升速度只剩 70%，轻按约跳 2 格
STOMP_BOUNCE = 420.0
GROUND_ACC = 2100.0      # 0 → 320 px/s 约 0.15 s
SPRINT_ACC = 3100.0      # 0 → 460 px/s 约 0.15 s
AIR_ACC = 1200.0
FRICTION = 1600.0        # 320 → 0 px/s 约 0.20 s
SKID_DEC = 3400.0
MAX_WALK = 320.0
MAX_SPRINT = 460.0
COYOTE_MS = 110
JUMP_BUFFER_MS = 130
INVINCIBLE_MS = 1200
TRANSFORM_MS = 300        # 变形期间免伤
FIRE_COOLDOWN_MS = 180
FIRE_MAX_ONSCREEN = 2
FIRE_SPEED = 520.0
FIRE_BOUNCES = 2          # 落地弹跳 2 次后消失；撞墙只反向，不计数
DEATH_MS = 1200
RESPAWN_INVINCIBLE_MS = 1500
CLEAR_SLIDE_MS = 600
CLEAR_HOLD_MS = 1000

# —— 敌人 ——
SHROOM_SPEED = 80.0
SHELLBUG_SPEED = 110.0
SHELL_SPEED = 420.0
SHELL_WALL_LIMIT = 3
FLITTER_SPEED = 120.0
FLITTER_AMP = 60.0
FLITTER_PERIOD = 2.4
BLOOM_CYCLE = 2.6
BLOOM_OUT_MS = 1400

# —— 规则 ——
TIME_START = 300
TIME_TICK_MS = 400
TIME_LOW = 100
LIVES_START = 3
COINS_PER_LIFE = 100
SCORE_COIN = 100
STOMP_CHAIN = (100, 200, 400, 800, 1000)
SCORE_FIREKILL = 200
SCORE_BRICK = 50
SCORE_BUMP = 50
SCORE_CLEAR_FIXED = 1000
SCORE_PER_TIME = 10
MAX_NAME_LEN = 8          # 留给 P2 的玩家名

# —— 相机 ——
CAM_DEAD_MIN, CAM_DEAD_MAX = 0.38, 0.55
CAM_LERP = 0.22           # 每帧插值系数，仅用于轻微缓动
PARALLAX_FAR, PARALLAX_NEAR = 0.35, 0.70

# —— 图块码 ——
EMPTY = "."
GROUND, BRICK, METAL, QUESTION, USED = "#", "B", "M", "?", "X"
PIPE, PLATFORM, SPIKE, COIN = "P", "=", "^", "c"
SOLID_TILES = frozenset({GROUND, BRICK, METAL, QUESTION, USED, PIPE})
SEMISOLID_TILES = frozenset({PLATFORM})
HAZARD_TILES = frozenset({SPIKE})
COIN_TILE = COIN

# —— 主题 ——
THEMES = {
    "grass":  {"name": "草原", "tiles": "tiles_grass.png",  "bg": "bg_grass",  "bgm": "grass",  "sky": ((92, 148, 252), (168, 216, 255))},
    "cave":   {"name": "地下", "tiles": "tiles_cave.png",   "bg": "bg_cave",   "bgm": "cave",   "sky": ((11, 10, 31), (26, 22, 52))},
    "sky":    {"name": "空中", "tiles": "tiles_sky.png",    "bg": "bg_sky",    "bgm": "sky",    "sky": ((127, 200, 255), (230, 246, 255))},
    "castle": {"name": "城堡", "tiles": "tiles_castle.png", "bg": "bg_castle", "bgm": "castle", "sky": ((42, 20, 38), (74, 32, 48))},
}

# —— 配色 ——
SKY_GRASS_TOP, SKY_GRASS_BOTTOM = (92, 148, 252), (168, 216, 255)
HUD_BG = (11, 15, 26)
HUD_TEXT = (255, 255, 255)
HUD_SUB = (185, 198, 218)
ACCENT = (255, 194, 31)
DANGER = (255, 77, 77)
GROUND_RGB = (192, 106, 46)
BRICK_RGB = (196, 84, 58)
METAL_RGB = (125, 143, 168)
QUESTION_RGB = (255, 194, 31)
USED_RGB = (154, 123, 79)
PIPE_RGB = (46, 196, 78)
SPIKE_RGB = (216, 222, 233)
COIN_RGB = (255, 215, 90)
PLY_RED = (230, 59, 46)
PLY_BLUE = (46, 91, 255)


def gravity(vy: float, dt: float) -> float:
    """每步重力积分，并钳制最大下落速度。"""
    return min(vy + GRAVITY * dt, MAX_FALL)


def time_to_score(units: int) -> int:
    return max(0, units) * SCORE_PER_TIME


def stomp_score(chain_index: int) -> int:
    return STOMP_CHAIN[min(chain_index, len(STOMP_CHAIN) - 1)]

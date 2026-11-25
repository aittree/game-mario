"""地形解析与查询（docs/03 §2）。

本模块只依赖 config，不引入 pygame / 实体 / UI。
"""

from __future__ import annotations

import json

from .config import (
    COIN_TILE,
    EMPTY,
    HAZARD_TILES,
    METAL,
    QUESTION,
    SEMISOLID_TILES,
    SOLID_TILES,
    THEMES,
    TILE,
    USED,
    VIEW_ROWS,
    BRICK,
    COIN,
    GROUND,
    PIPE,
    PLATFORM,
    SPIKE,
)


class LevelError(Exception):
    """关卡文件不可用。main 捕获后把该关标记为不可用。"""

    def __init__(self, message: str):
        super().__init__(message)


CODE_SET = set(EMPTY + GROUND + BRICK + METAL + QUESTION + USED + PIPE + PLATFORM + SPIKE + COIN)
ENTITY_TYPES = {"patrol_shroom", "shellbug", "flitter", "pipe_bloom",
                "moving_platform", "checkpoint", "goal"}


class TileMap:
    def __init__(self, rows: int, cols: int, grid: list[list[str]], theme: str):
        self.rows, self.cols, self.grid, self.theme = rows, cols, grid, theme

    # —— 构造 ——
    @classmethod
    def from_dict(cls, data: dict) -> "TileMap":
        rows, cols = int(data.get("rows", VIEW_ROWS)), int(data["cols"])
        if rows != VIEW_ROWS:
            raise LevelError(f"rows 必须为 {VIEW_ROWS}")
        lines = data["tiles"]
        if len(lines) != rows:
            raise LevelError("tiles 行数不符")
        grid = []
        for i, line in enumerate(lines):
            if len(line) != cols:
                raise LevelError(f"第 {i} 行长度 {len(line)} != {cols}")
            bad = set(line) - CODE_SET
            if bad:
                raise LevelError(f"第 {i} 行含未知图块码 {bad}")
            grid.append(list(line))
        theme = data["theme"]
        if theme not in THEMES:
            raise LevelError(f"未知主题 {theme}")
        return cls(rows, cols, grid, theme)

    @classmethod
    def from_file(cls, path: str) -> "TileMap":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            raise LevelError(str(exc)) from exc
        return cls.from_dict(data)

    # —— 尺寸 ——
    @property
    def width_px(self) -> int:
        return self.cols * TILE

    @property
    def height_px(self) -> int:
        return self.rows * TILE

    # —— 查询 ——
    def tile_at(self, col: int, row: int) -> str:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return EMPTY

    def solid(self, col: int, row: int) -> bool:
        """左右越界视为实心墙；上方越界为空；下方越界为空（掉出去即死）。"""
        if col < 0 or col >= self.cols:
            return True
        if row < 0 or row >= self.rows:
            return False
        return self.grid[row][col] in SOLID_TILES

    def semisolid(self, col: int, row: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols \
            and self.grid[row][col] in SEMISOLID_TILES

    def hazard(self, col: int, row: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols \
            and self.grid[row][col] in HAZARD_TILES

    def coin(self, col: int, row: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols \
            and self.grid[row][col] == COIN_TILE

    # —— 修改（仅模型层调用）——
    def take_coin(self, col: int, row: int) -> bool:
        if self.coin(col, row):
            self.grid[row][col] = EMPTY
            return True
        return False

    def remove(self, col: int, row: int) -> None:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.grid[row][col] = EMPTY

    def use_question(self, col: int, row: int) -> None:
        if self.tile_at(col, row) == QUESTION:
            self.grid[row][col] = USED

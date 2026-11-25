"""校验 assets/levels/*.json 的结构与内容约束。

校验项对应 docs/03 §2.2、docs/05 §2.7 与 docs/08 §4：
- 字段齐全、rows=18、每行长度 = cols、图块码合法；
- spawn 在界内，且该格与其上方一格为空；
- items 的键必须指向 `?` 问号块；
- entities 类型合法、坐标在界内，并校验各类型的额外字段；
- pipe_bloom 必须位于水管顶格；
- checkpoint / goal 下方必须有实心地面；
- 有且仅有一个 goal，且距右边界 ≤ 6 格；
- 出生点周围 3 格内无敌人；
- 顶部 2 行只允许 `.` 或 `M`；
- 单坑宽度 ≤ 5 格。

用法：
    python tools/format_level.py            # 校验全部关卡
    python tools/format_level.py --check    # 同上（兼容 04 文档中的写法）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVEL_DIR = ROOT / "assets" / "levels"

ROWS = 18
CODE_SET = set(".#BM?XP=^c")
SOLID = set("#BM?XP")
SEMISOLID = set("=")
THEMES = {"grass", "cave", "sky", "castle"}
ENTITY_TYPES = {"patrol_shroom", "shellbug", "flitter",
                "pipe_bloom", "moving_platform", "checkpoint", "goal"}
ITEM_VALUES = {"coin", "mushroom", "flower"}
MAX_PIT = 5
GOAL_EDGE = 6


class Report:
    def __init__(self, name: str):
        self.name = name
        self.errors: list[str] = []
        self.warns: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def _solid(grid: list[list[str]], col: int, row: int) -> bool:
    if 0 <= row < ROWS and 0 <= col < len(grid[row]):
        return grid[row][col] in SOLID
    return False


def _walkable(grid: list[list[str]], col: int, row: int) -> bool:
    if 0 <= row < ROWS and 0 <= col < len(grid[row]):
        return grid[row][col] in SOLID or grid[row][col] in SEMISOLID
    return False


def validate(path: Path) -> Report:
    rep = Report(path.name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        rep.error(f"无法读取/解析 JSON：{exc}")
        return rep

    # —— 基本字段 ——
    level_id = data.get("id")
    if level_id != path.stem[1:]:
        rep.error(f"id={level_id!r} 与文件名 {path.stem}.json 不一致（应为 {path.stem[1:]!r}）")
    if data.get("theme") not in THEMES:
        rep.error(f"未知主题 {data.get('theme')!r}")
    rows = data.get("rows")
    cols = data.get("cols")
    if rows != ROWS:
        rep.error(f"rows={rows}，必须为 {ROWS}")
    if not isinstance(cols, int) or not (160 <= cols <= 200):
        rep.error(f"cols={cols!r}，必须为 160～200 的整数")
        return rep
    if not isinstance(data.get("time"), int) or data["time"] <= 0:
        rep.error(f"time={data.get('time')!r} 必须为正整数")
    if not isinstance(data.get("name"), str) or not data["name"]:
        rep.error("name 必须为非空字符串")

    # —— 地形 ——
    lines = data.get("tiles")
    if not isinstance(lines, list) or len(lines) != ROWS:
        rep.error(f"tiles 行数 {len(lines) if isinstance(lines, list) else 'N/A'} != {ROWS}")
        return rep
    grid: list[list[str]] = []
    for i, line in enumerate(lines):
        if not isinstance(line, str):
            rep.error(f"第 {i} 行不是字符串")
            line = "." * cols
        if len(line) != cols:
            rep.error(f"第 {i} 行长度 {len(line)} != cols {cols}")
        bad = sorted(set(line) - CODE_SET)
        if bad:
            rep.error(f"第 {i} 行含未知图块码 {bad}")
        grid.append(list(line.ljust(cols, ".")[:cols]))

    # —— 顶部 2 行 ——
    for r in (0, 1):
        bad = {c for c in grid[r] if c not in (".", "M")}
        if bad:
            rep.error(f"顶部第 {r} 行出现非装饰图块 {sorted(bad)}")

    # —— 出生点 ——
    spawn = data.get("spawn")
    if (not isinstance(spawn, list) or len(spawn) != 2
            or not all(isinstance(v, int) for v in spawn)):
        rep.error("spawn 必须是 [col, row]")
    else:
        sx, sy = spawn
        if not (0 <= sx < cols and 0 <= sy < ROWS):
            rep.error(f"spawn {spawn} 越界")
        else:
            if grid[sy][sx] != ".":
                rep.error(f"spawn 所在格 ({sx},{sy}) 不是空图块，实为 {grid[sy][sx]!r}")
            if sy - 1 >= 0 and grid[sy - 1][sx] != ".":
                rep.error(f"spawn 上方格 ({sx},{sy - 1}) 不是空图块，实为 {grid[sy - 1][sx]!r}")
            if not _solid(grid, sx, sy + 1):
                rep.warn(f"spawn 下方 ({sx},{sy + 1}) 不是实心地面，玩家会直接下落")

    # —— items ——
    items = data.get("items", {})
    if not isinstance(items, dict):
        rep.error("items 必须是对象")
        items = {}
    for key, value in items.items():
        try:
            col_s, row_s = key.split(",")
            col, row = int(col_s), int(row_s)
        except (ValueError, AttributeError):
            rep.error(f"items 键 {key!r} 不是 'col,row' 格式")
            continue
        if not (0 <= col < cols and 0 <= row < ROWS):
            rep.error(f"items 键 {key} 越界")
            continue
        if grid[row][col] != "?":
            rep.error(f"items 键 {key} 指向的图块是 {grid[row][col]!r}，不是 '?'")
        if value not in ITEM_VALUES:
            rep.error(f"items[{key}]={value!r} 不是 {sorted(ITEM_VALUES)} 之一")

    # 统计未配置物品的问号块（运行时默认产出金币）
    question_cells = {(c, r) for r in range(ROWS) for c in range(cols) if grid[r][c] == "?"}
    missing = question_cells - {(int(k.split(",")[0]), int(k.split(",")[1]))
                                for k in items if k.count(",") == 1}
    if missing:
        rep.warn(f"{len(missing)} 个问号块未配置 items（运行时默认产出金币）：{sorted(missing)[:6]}")

    # —— 实体 ——
    entities = data.get("entities")
    if not isinstance(entities, list):
        rep.error("entities 必须是数组")
        entities = []
    goals: list[dict] = []
    enemy_cells: list[tuple[int, int]] = []
    for idx, ent in enumerate(entities):
        etype = ent.get("type")
        if etype not in ENTITY_TYPES:
            rep.error(f"实体 #{idx} 类型 {etype!r} 不合法")
            continue
        col, row = ent.get("col"), ent.get("row")
        if not (isinstance(col, int) and isinstance(row, int)
                and 0 <= col < cols and 0 <= row < ROWS):
            rep.error(f"实体 #{idx}({etype}) 坐标 ({col},{row}) 越界")
            continue
        if etype in ("checkpoint", "goal"):
            if not _solid(grid, col, row + 1):
                rep.error(f"{etype} ({col},{row}) 下方不是实心地面")
        if etype == "pipe_bloom":
            if not (row + 1 < ROWS and grid[row + 1][col] == "P"):
                rep.error(f"pipe_bloom ({col},{row}) 不在水管顶格（下方应为 'P'）")
        if etype == "moving_platform":
            path = ent.get("path")
            speed = ent.get("speed")
            if (not isinstance(path, list) or len(path) < 2
                    or not all(isinstance(p, list) and len(p) == 2 for p in path)):
                rep.error(f"moving_platform ({col},{row}) path 至少 2 个 [col,row] 格点")
            elif any(not (0 <= p[0] < cols and 0 <= p[1] < ROWS) for p in path):
                rep.error(f"moving_platform ({col},{row}) path 越界")
            if not isinstance(speed, (int, float)) or speed <= 0:
                rep.error(f"moving_platform ({col},{row}) speed 必须为正数")
        if etype == "flitter":
            if "amp" in ent and not isinstance(ent["amp"], (int, float)):
                rep.error(f"flitter ({col},{row}) amp 必须为数字")
            if "period" in ent and not (isinstance(ent["period"], (int, float)) and ent["period"] > 0):
                rep.error(f"flitter ({col},{row}) period 必须为正数")
        if etype == "goal":
            goals.append(ent)
        if etype not in ("checkpoint", "goal"):
            enemy_cells.append((col, row))

    if len(goals) != 1:
        rep.error(f"goal 数量为 {len(goals)}，必须恰好 1 个")
    else:
        gcol = goals[0]["col"]
        if cols - 1 - gcol > GOAL_EDGE:
            rep.error(f"goal.col={gcol} 距右边界 {cols - 1 - gcol} 格 > {GOAL_EDGE}")

    # —— 出生点周围 3 格无敌人（UT-L-06）——
    spawn_xy = data.get("spawn")
    if isinstance(spawn_xy, list) and len(spawn_xy) == 2:
        sx, sy = spawn_xy
        for (ec, er) in enemy_cells:
            if abs(ec - sx) <= 3 and abs(er - sy) <= 1:
                rep.error(f"出生点 ({sx},{sy}) 周围 3 格内有敌人 ({ec},{er})")

    # —— 单坑宽度 ——
    pit_run = 0
    max_run = 0
    for c in range(cols):
        empty_col = not _solid(grid, c, ROWS - 1) and not _walkable(grid, c, ROWS - 2)
        if empty_col:
            pit_run += 1
            max_run = max(max_run, pit_run)
        else:
            pit_run = 0
    if max_run > MAX_PIT:
        rep.error(f"存在宽度 {max_run} 格的坑，超过 {MAX_PIT} 格限制")

    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验关卡 JSON 的结构与内容约束")
    parser.add_argument("--check", action="store_true", help="兼容写法，行为与默认一致")
    parser.add_argument("paths", nargs="*", help="可选：指定关卡文件，默认校验 assets/levels/*.json")
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.paths] or sorted(LEVEL_DIR.glob("*.json"))
    if not paths:
        print(f"未找到关卡文件：{LEVEL_DIR}")
        return 1

    failed = 0
    for path in paths:
        rep = validate(path)
        status = "PASS" if rep.ok else "FAIL"
        print(f"[{status}] {rep.name}")
        for msg in rep.warns:
            print(f"    warn: {msg}")
        for msg in rep.errors:
            print(f"    error: {msg}")
        if not rep.ok:
            failed += 1

    print(f"\n共 {len(paths)} 个关卡，{len(paths) - failed} 个通过，{failed} 个失败。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

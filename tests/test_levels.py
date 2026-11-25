"""4 个正式关卡的校验与“无死路”检查（docs/05 §1 关卡校验）。

- 结构约束复用 tools/format_level.py，避免脚本与测试两套规则；
- 用粗粒度可达性搜索确认从出生点可以走到终点：允许 6 格横跨、3 格上跳，
  远低于实际冲刺跳（约 11 格横跨 / 4 格高），因此通过即说明没有几何死路。
"""

from collections import deque
from pathlib import Path

import pytest

from src.config import PHYSICS_DT, TILE
from src.entities.base import InputIntent
from src.game import LevelSession, SessionState
from src.storage import Profile
from tools import format_level

LEVEL_DIR = Path(__file__).resolve().parents[1] / "assets" / "levels"
LEVELS = sorted(LEVEL_DIR.glob("w*.json"))

JUMP_COLS = 6          # 保守的横跨距离（格）
MAX_RISE = 3 * TILE    # 保守的起跳提升高度


def _surfaces(tmap) -> dict[int, set[int]]:
    """每列可站立的脚底 y：图块实心/单向，且上方两格不实心。"""
    result: dict[int, set[int]] = {}
    for c in range(tmap.cols):
        for r in range(2, tmap.rows):
            if not (tmap.solid(c, r) or tmap.semisolid(c, r)):
                continue
            if tmap.solid(c, r - 1) or tmap.solid(c, r - 2):
                continue
            result.setdefault(c, set()).add(r * TILE)
    return result


def _goal_col(session: LevelSession) -> int:
    return next(e["col"] for e in session.raw["entities"] if e["type"] == "goal")


def test_all_level_files_exist():
    assert len(LEVELS) == 4, f"应有 4 个关卡，实际 {len(LEVELS)}"


@pytest.mark.parametrize("path", LEVELS, ids=[p.stem for p in LEVELS])
def test_level_passes_validator(path: Path):
    report = format_level.validate(path)
    assert report.ok, "\n".join(report.errors)


@pytest.mark.parametrize("path", LEVELS, ids=[p.stem for p in LEVELS])
def test_level_loads_and_spawn_is_stable(path: Path):
    session = LevelSession(str(path), Profile())
    assert session.goal is not None
    assert session.tilemap.cols == session.raw["cols"]
    spawn_col, spawn_row = session.raw["spawn"]
    assert session.tilemap.solid(spawn_col, spawn_row + 1)
    bottom = session.player.body.bottom
    for _ in range(120):
        session.step(InputIntent(), PHYSICS_DT)
    assert session.state is SessionState.RUNNING
    assert session.player.body.bottom == pytest.approx(bottom)


@pytest.mark.parametrize("path", LEVELS, ids=[p.stem for p in LEVELS])
def test_goal_reachable_without_dead_end(path: Path):
    session = LevelSession(str(path), Profile())
    tmap = session.tilemap
    surf = _surfaces(tmap)
    spawn_col, spawn_row = session.raw["spawn"]
    start = (spawn_col, (spawn_row + 1) * TILE)
    assert start[1] in surf.get(spawn_col, set()), "出生点脚下没有可站立地面"

    goal_col = _goal_col(session)
    seen = {start}
    queue = deque([start])
    while queue:
        col, feet = queue.popleft()
        if col >= goal_col - 1:
            break
        for dc in range(-JUMP_COLS, JUMP_COLS + 1):
            if dc == 0:
                continue
            for nfeet in surf.get(col + dc, ()):
                if feet - nfeet > MAX_RISE:      # 上跳超限
                    continue
                node = (col + dc, nfeet)
                if node not in seen:
                    seen.add(node)
                    queue.append(node)
    assert any(col >= goal_col - 1 for col, _ in seen), \
        f"{path.stem}: 保守可达性搜索到不了终点列 {goal_col}"

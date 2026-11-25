"""tilemap 单元测试（docs/05 §2.2 UT-T-01～UT-T-11）。

模型层不 import pygame，因此本文件可在无显示环境下直接运行。
"""

import json

import pytest

from src.config import TILE
from src.tilemap import LevelError, TileMap

ROWS, COLS = 18, 20
# 一行覆盖全部可查询图块码：土/砖/硬/问号/已用/水管/平台/尖刺/金币
SAMPLE_ROW = "#BM?XP=^c"


def make_data(**overrides) -> dict:
    tiles = ["." * COLS for _ in range(ROWS)]
    tiles[10] = SAMPLE_ROW + "." * (COLS - len(SAMPLE_ROW))
    data = {
        "id": "1-1",
        "name": "测试关",
        "theme": "grass",
        "cols": COLS,
        "rows": ROWS,
        "time": 300,
        "spawn": [2, 14],
        "tiles": tiles,
        "items": {},
        "entities": [],
    }
    data.update(overrides)
    return data


def test_parse_valid_map():
    """UT-T-01：合法 18×20 地图解析成功，尺寸换算正确。"""
    tmap = TileMap.from_dict(make_data())
    assert (tmap.rows, tmap.cols, tmap.theme) == (ROWS, COLS, "grass")
    assert tmap.width_px == COLS * TILE
    assert tmap.height_px == ROWS * TILE
    assert tmap.tile_at(0, 10) == "#"


def test_tiles_row_count_mismatch():
    """UT-T-02：tiles 只有 17 行应抛 LevelError。"""
    data = make_data()
    data["tiles"] = data["tiles"][:17]
    with pytest.raises(LevelError):
        TileMap.from_dict(data)


def test_row_length_mismatch_reports_line():
    """UT-T-03：某行长度 ≠ cols 时抛 LevelError，信息含行号。"""
    data = make_data()
    data["tiles"][2] = "." * (COLS - 1)
    with pytest.raises(LevelError, match="第 2 行"):
        TileMap.from_dict(data)


def test_unknown_tile_code():
    """UT-T-04：未知图块码应抛 LevelError。"""
    data = make_data()
    data["tiles"][5] = "Z" + "." * (COLS - 1)
    with pytest.raises(LevelError, match="未知图块码"):
        TileMap.from_dict(data)


def test_unknown_theme():
    """UT-T-05：未知主题应抛 LevelError。"""
    with pytest.raises(LevelError, match="未知主题"):
        TileMap.from_dict(make_data(theme="desert"))


def test_from_file_missing_raises_level_error(tmp_path):
    """UT-T-06：文件不存在抛 LevelError，而不是 FileNotFoundError。"""
    with pytest.raises(LevelError):
        TileMap.from_file(str(tmp_path / "missing.json"))


def test_from_file_bad_json_raises_level_error(tmp_path):
    """UT-T-06：JSON 语法错误抛 LevelError。"""
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(LevelError):
        TileMap.from_file(str(bad))


def test_from_file_valid(tmp_path):
    """补充：合法文件可从磁盘解析。"""
    path = tmp_path / "w1-1.json"
    path.write_text(json.dumps(make_data(), ensure_ascii=False), encoding="utf-8")
    assert TileMap.from_file(str(path)).cols == COLS


def test_solid_codes():
    """UT-T-07：实心码为 True，空/平台/尖刺/金币为 False。"""
    tmap = TileMap.from_dict(make_data())
    solid_true = "#BM?XP"
    for col, code in enumerate(SAMPLE_ROW):
        expected = code in solid_true
        assert tmap.solid(col, 10) is expected, code
    assert tmap.solid(len(SAMPLE_ROW), 10) is False   # 该列是 "."


def test_solid_horizontal_bounds_are_walls():
    """UT-T-08：左右越界视为实心墙。"""
    tmap = TileMap.from_dict(make_data())
    assert tmap.solid(-1, 10) is True
    assert tmap.solid(COLS, 10) is True


def test_solid_vertical_bounds_are_empty():
    """UT-T-09：上下越界视为空，掉出关卡由会话判定死亡。"""
    tmap = TileMap.from_dict(make_data())
    assert tmap.solid(0, -1) is False
    assert tmap.solid(0, ROWS) is False


def test_take_coin_once():
    """UT-T-10：金币只能收集一次，第二次返回 False。"""
    tmap = TileMap.from_dict(make_data())
    assert tmap.coin(8, 10) is True
    assert tmap.take_coin(8, 10) is True
    assert tmap.tile_at(8, 10) == "."
    assert tmap.take_coin(8, 10) is False


def test_use_question_once():
    """UT-T-11：问号块变已用块，再次顶不产出。"""
    tmap = TileMap.from_dict(make_data())
    assert tmap.tile_at(3, 10) == "?"
    tmap.use_question(3, 10)
    assert tmap.tile_at(3, 10) == "X"
    tmap.use_question(3, 10)                 # 再顶一次不应改变
    assert tmap.tile_at(3, 10) == "X"
    tmap.use_question(1, 10)                 # 对非问号块调用无副作用
    assert tmap.tile_at(1, 10) == "B"


def test_semisolid_hazard_and_remove():
    """补充：平台/尖刺查询与 remove 修改方法。"""
    tmap = TileMap.from_dict(make_data())
    assert tmap.semisolid(6, 10) is True
    assert tmap.semisolid(0, 10) is False
    assert tmap.hazard(7, 10) is True
    assert tmap.hazard(0, 10) is False

    tmap.remove(1, 10)
    assert tmap.tile_at(1, 10) == "."
    tmap.remove(-1, 10)                      # 越界删除安全忽略
    tmap.remove(0, ROWS)
    assert tmap.tile_at(0, 10) == "#"


def test_tile_at_out_of_bounds_is_empty():
    """补充：tile_at 越界返回空图块。"""
    tmap = TileMap.from_dict(make_data())
    assert tmap.tile_at(-1, 10) == "."
    assert tmap.tile_at(COLS, 10) == "."
    assert tmap.tile_at(0, -1) == "."
    assert tmap.tile_at(0, ROWS) == "."

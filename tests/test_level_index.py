"""关卡索引（docs/03 §10）：四个关卡均可加载且元信息一致。"""

from src.config import THEMES
from src.levels import load_level_index


def test_level_index_lists_four_available_levels():
    infos = load_level_index()
    assert len(infos) == 4
    assert all(info.available for info in infos)
    assert [info.id for info in infos] == ["1-1", "1-2", "1-3", "1-4"]


def test_each_level_has_distinct_theme_and_name():
    infos = load_level_index()
    assert len({info.theme for info in infos}) == 4
    assert all(info.theme in THEMES for info in infos)
    assert all(info.name and info.name != "暂不可用" for info in infos)
    assert all(info.cols > 0 for info in infos)

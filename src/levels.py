"""关卡索引（docs/03 §10）。

只扫描 `assets/levels/*.json` 读取展示所需的元信息；单个文件解析失败只把该关
标记为不可用，绝不阻断启动。
"""

from __future__ import annotations

import json
from pathlib import Path

from .resource import resource_path


class LevelInfo:
    """关卡索引项的只读元信息。"""

    def __init__(self, path: str, level_id: str, name: str, theme: str,
                 cols: int, available: bool = True):
        self.path = path
        self.id = level_id
        self.name = name
        self.theme = theme
        self.cols = cols
        self.available = available


def load_level_index() -> list[LevelInfo]:
    folder = Path(resource_path("assets", "levels"))
    infos: list[LevelInfo] = []
    for path in sorted(folder.glob("w*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            infos.append(LevelInfo(
                path=str(path),
                level_id=str(data["id"]),
                name=str(data["name"]),
                theme=str(data["theme"]),
                cols=int(data["cols"]),
                available=True,
            ))
        except (OSError, ValueError, KeyError, TypeError):
            infos.append(LevelInfo(path=str(path), level_id=path.stem,
                                   name="暂不可用", theme="grass",
                                   cols=0, available=False))
    return infos


def load_level_data(info: LevelInfo) -> dict:
    """读取关卡原始数据；文件不可用时抛出 OSError/ValueError 交由调用方兜底。"""
    return json.loads(Path(info.path).read_text(encoding="utf-8"))

"""资源路径（docs/03 §8.1）。

`assets/` 下所有文件必须经此函数拼接，禁止出现 "assets/..." 字面量。
"""

import os
import sys


def resource_path(*parts: str) -> str:
    """源码运行走工程根；PyInstaller onefile 运行走解包目录。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS")
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)

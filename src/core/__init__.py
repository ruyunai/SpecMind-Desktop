"""Core 层 - 配置/加密/模型路由/审计"""

import sys
import os
from pathlib import Path


def get_data_dir() -> Path:
    """获取数据目录（兼容 PyInstaller frozen 模式）。

    - 开发模式：项目根目录的 data/ 子目录
    - Frozen 模式（exe 运行）：%APPDATA%/SpecMindDesktop/data/
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "SpecMindDesktop" / "data"
    return Path(__file__).resolve().parent.parent.parent / "data"

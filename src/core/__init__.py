"""Core 层 - 配置/加密/模型路由/审计"""

import sys
import os
from pathlib import Path


def _get_exe_dir() -> Path:
    """获取 exe/脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # 开发模式：main.py 所在目录
    return Path(__file__).resolve().parent.parent.parent


def is_portable() -> bool:
    """检测是否为便携模式。

    规则：exe/脚本同级目录存在 portable.dat 标记文件时启用便携模式。
    便携模式下所有数据存储在 exe 所在目录的 data/ 子目录中。
    """
    return (_get_exe_dir() / "portable.dat").exists()


def get_app_root() -> Path:
    """获取应用根目录。

    - 便携模式：exe/脚本同级目录 (U 盘)
    - 非便携 / Frozen：%APPDATA%/SpecMindDesktop/
    - 开发模式：exe/脚本同级目录
    """
    if is_portable():
        return _get_exe_dir()
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "SpecMindDesktop"
    return _get_exe_dir()


def get_data_dir() -> Path:
    """获取数据目录（chroma/sqlite/logs）。

    - 便携模式：exe 同级 data/
    - 开发模式：项目根 data/
    - Frozen 模式（exe）：%APPDATA%/SpecMindDesktop/data/
    - 同时兼容旧路径（无 portable.dat 时行为不变）
    """
    if is_portable():
        return _get_exe_dir() / "data"
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "SpecMindDesktop" / "data"
    return Path(__file__).resolve().parent.parent.parent / "data"

"""全局日志配置 - 各 Agent 节点执行追踪。

输出：
  - 控制台（DEBUG 级别）
  - APPDATA/SpecMindDesktop/logs/specmind.log（RotatingFileHandler: 5MB × 3 备份）

阶段 8.6 S4：日志目录从相对路径 logs/ 迁移到 APPDATA，
兼容 PyInstaller frozen 模式，增加自动轮转防止日志文件无限膨胀。
"""
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

from core import get_data_dir


# 日志轮转参数
_MAX_BYTES = 5 * 1024 * 1024  # 5MB
_BACKUP_COUNT = 3             # 保留 3 个备份


def setup_logger(name: str = "specmind") -> logging.Logger:
    """配置全局 logger。

    单例模式：同一 name 只创建一次 handler。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 文件（APPDATA + 轮转）
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "specmind.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

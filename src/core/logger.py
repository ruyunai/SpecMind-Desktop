"""全局日志配置 - 各 Agent 节点执行追踪。

输出：
  - 控制台（DEBUG 级别，文本格式）
  - APPDATA/SpecMindDesktop/logs/specmind.log（RotatingFileHandler: 5MB × 3 备份）
  - APPDATA/SpecMindDesktop/logs/specmind.jsonl（JSON Lines，Frozen 模式自动启用）

阶段 8.6 S4：日志目录从相对路径 logs/ 迁移到 APPDATA，增加自动轮转。
阶段 8.4 O4：新增 StructuredFormatter（JSON Lines），Frozen 模式自动切换。
"""
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

from core import get_data_dir


# 日志轮转参数
_MAX_BYTES = 5 * 1024 * 1024  # 5MB
_BACKUP_COUNT = 3             # 保留 3 个备份


class _StructuredFormatter(logging.Formatter):
    """JSON Lines 格式器 — 每条日志一行 JSON。

    字段：ts, level, logger, message, run_id, node_name, elapsed_ms
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, self.datefmt or "%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 附加上下文（通过 extra 注入）
        for attr in ("run_id", "node_name", "elapsed_ms"):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)
        return json.dumps(log_entry, ensure_ascii=False)


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

    # Frozen 模式下自动启用 JSON Lines
    if getattr(sys, "frozen", False):
        _add_json_handler(logger, log_dir)

    return logger


def enable_json_logging(logger_name: str = "specmind") -> None:
    """手动启用 JSON Lines 日志（开发模式调试用）。"""
    logger = logging.getLogger(logger_name)
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _add_json_handler(logger, log_dir)


def _add_json_handler(logger: logging.Logger, log_dir: Path) -> None:
    """添加 JSON Lines 文件 handler。"""
    # 避免重复添加
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler) and str(h.baseFilename).endswith(".jsonl"):
            return
    json_handler = RotatingFileHandler(
        log_dir / "specmind.jsonl",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    json_handler.setLevel(logging.DEBUG)
    json_handler.setFormatter(_StructuredFormatter())
    logger.addHandler(json_handler)

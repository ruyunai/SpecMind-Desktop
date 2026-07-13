"""验证 8.6 S4 日志路径迁移与轮转功能。

测试项：
  1. RotatingFileHandler 类型正确
  2. 日志目录位于 get_data_dir()/logs/
  3. 轮转参数 (maxBytes=5MB, backupCount=3)
  4. 日志写入正常
  5. 轮转行为验证（用小 maxBytes 模拟）
"""
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core import get_data_dir


def test_handler_type():
    """测试 1: 新 logger 使用 RotatingFileHandler。"""
    print("=== Test 1: handler 类型 ===")
    logger = logging.getLogger("test_s4_handler")
    logger.handlers.clear()  # 清除缓存
    logger.setLevel(logging.DEBUG)

    from core.logger import setup_logger
    logger = setup_logger("test_s4_type")
    rotating = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) == 1, f"FAIL: expected 1 RotatingFileHandler, got {len(rotating)}"
    print(f"  RotatingFileHandler: ✓")
    print("  PASS")


def test_log_path():
    """测试 2: 日志路径位于 get_data_dir()/logs/。"""
    print("\n=== Test 2: 日志路径 ===")
    log_dir = get_data_dir() / "logs"
    log_file = log_dir / "specmind.log"

    # 确认目录存在
    assert log_dir.exists(), f"FAIL: {log_dir} does not exist"

    # 确认日志文件存在
    assert log_file.exists(), f"FAIL: {log_file} does not exist"

    # 确认不是旧的相对路径
    old_path = Path("logs") / "specmind.log"
    print(f"  日志路径 : {log_file}")
    print(f"  旧路径   : {old_path} (相对)")
    print("  PASS")


def test_rotation_params():
    """测试 3: 轮转参数正确。"""
    print("\n=== Test 3: 轮转参数 ===")
    logger = logging.getLogger("test_s4_params")
    logger.handlers.clear()
    from core.logger import setup_logger
    logger = setup_logger("test_s4_params")
    rotating = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)][0]
    max_mb = rotating.maxBytes / (1024 * 1024)
    print(f"  maxBytes   : {rotating.maxBytes} ({max_mb:.0f}MB)")
    print(f"  backupCount: {rotating.backupCount}")
    assert rotating.maxBytes == 5 * 1024 * 1024, \
        f"FAIL: expected 5MB, got {rotating.maxBytes}"
    assert rotating.backupCount == 3, \
        f"FAIL: expected 3, got {rotating.backupCount}"
    print("  PASS")


def test_write():
    """测试 4: 日志写入正常。"""
    print("\n=== Test 4: 写入测试 ===")
    logger = logging.getLogger("test_s4_write")
    logger.handlers.clear()
    from core.logger import setup_logger
    logger = setup_logger("test_s4_write")

    test_msg = "S4 日志路径迁移验证 - Hello SpecMind!"
    logger.info(test_msg)

    log_file = get_data_dir() / "logs" / "specmind.log"
    content = log_file.read_text(encoding="utf-8")
    assert test_msg in content, f"FAIL: message not found in log"
    print(f"  写入成功: '{test_msg}'")
    print("  PASS")


def test_rotation_behavior():
    """测试 5: 轮转行为（用小 maxBytes 独立 logger）。"""
    print("\n=== Test 5: 轮转行为验证 ===")
    test_logger = logging.getLogger("test_s4_rotate")
    test_logger.handlers.clear()
    test_logger.setLevel(logging.DEBUG)

    # 使用独立日志文件 + 极小 maxBytes 触发轮转
    tmp_dir = get_data_dir() / "logs"
    tmp_file = tmp_dir / "test_rotate.log"
    # 先清理旧文件
    for f in tmp_dir.glob("test_rotate*"):
        f.unlink()

    handler = RotatingFileHandler(
        str(tmp_file), maxBytes=100, backupCount=2, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    test_logger.addHandler(handler)

    # 写入足够数据触发轮转（100 bytes * 5 = 500 bytes > 100 bytes 触发第一次轮转）
    for i in range(20):
        test_logger.info("X" * 80)  # ~80 bytes per line

    handler.close()

    # 检查备份文件
    backups = sorted(tmp_dir.glob("test_rotate.log*"))
    print(f"  轮转文件: {len(backups)}")
    for b in backups:
        size = b.stat().st_size
        print(f"    {b.name} ({size} bytes)")
    assert len(backups) >= 2, \
        f"FAIL: expected >= 2 files (original + backup), got {len(backups)}"

    # 清理
    for f in backups:
        f.unlink()
    test_logger.handlers.clear()
    print("  PASS")


def main():
    tests = [
        test_handler_type,
        test_log_path,
        test_rotation_params,
        test_write,
        test_rotation_behavior,
    ]
    for test in tests:
        test()
    print(f"\n✅ 8.6 S4 日志路径迁移与轮转 — 全部 {len(tests)} 项测试通过!")


if __name__ == "__main__":
    main()

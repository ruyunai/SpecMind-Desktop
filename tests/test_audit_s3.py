"""测试 8.6 S3 审计日志过期清理。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.sqlite_store import SqliteStore


def main() -> None:
    tmp_db = str(Path(__file__).parent / "_test_audit_s3.db")

    # ---- 清理旧数据 ----
    Path(tmp_db).unlink(missing_ok=True)

    # 测试 1：retention_days=365 不删除
    print("=== Test 1: retention_days=365（不删除） ===")
    store = SqliteStore(db_path=tmp_db, retention_days=365)
    # 手动重置 _last_cleanup 避免机会性清理干扰
    store._last_cleanup = time.monotonic() + 99999
    store.add_audit_log("run-001", "node_a", "entry")
    store.add_audit_log("run-001", "node_a", "exit", elapsed_ms=100)
    deleted = store.cleanup_audit_logs()
    after = store.get_audit_logs()
    print(f"  删除: {deleted} 条, 剩余: {len(after)} 条")
    assert deleted == 0, f"FAIL: expected 0, got {deleted}"
    assert len(after) == 2, f"FAIL: expected 2, got {len(after)}"
    store.close()
    print("  PASS")

    # 测试 2：retention_days=0 全删
    print("\n=== Test 2: retention_days=0（全删） ===")
    # 先清理 DB，重新创建
    Path(tmp_db).unlink(missing_ok=True)
    store = SqliteStore(db_path=tmp_db, retention_days=0)
    # 阻止机会性清理
    store._last_cleanup = time.monotonic() + 99999
    store.add_audit_log("run-002", "node_a", "entry")
    store.add_audit_log("run-002", "node_a", "exit", elapsed_ms=100)
    store.add_audit_log("run-002", "node_b", "entry")
    assert len(store.get_audit_logs()) == 3, "FAIL: should have 3 records"
    deleted = store.cleanup_audit_logs(retention_days=0)
    after = store.get_audit_logs()
    print(f"  删除: {deleted} 条, 剩余: {len(after)} 条")
    assert deleted == 3, f"FAIL: expected 3, got {deleted}"
    assert len(after) == 0, f"FAIL: expected 0, got {len(after)}"
    store.close()
    print("  PASS")

    # 测试 3：覆盖率参数，retention 恢复
    print("\n=== Test 3: 手动覆盖 retention，restore 不受影响 ===")
    Path(tmp_db).unlink(missing_ok=True)
    store = SqliteStore(db_path=tmp_db, retention_days=90)
    store._last_cleanup = time.monotonic() + 99999
    store.add_audit_log("run-003", "node_a", "entry")
    deleted = store.cleanup_audit_logs(retention_days=365)
    print(f"  删除: {deleted} 条, retention={store.retention_days}")
    assert store.retention_days == 90, "FAIL: should restore to 90"
    store.close()
    print("  PASS")

    # 测试 4：节流生效
    print("\n=== Test 4: 节流（1 小时内不重复清理） ===")
    Path(tmp_db).unlink(missing_ok=True)
    store = SqliteStore(db_path=tmp_db, retention_days=90)
    initial = store._last_cleanup
    store.add_audit_log("run-004", "node_a", "entry")
    # 新 store 第一次写入触发清理（因为 _last_cleanup=0）
    assert store._last_cleanup > initial, "FAIL: should update on first write"
    second = store._last_cleanup
    store.add_audit_log("run-004", "node_a", "exit", elapsed_ms=10)
    # 1 秒后不应再触发
    assert store._last_cleanup == second, "FAIL: should throttle"
    store.close()
    print("  PASS")

    # 测试 5：机会性清理真实触发
    print("\n=== Test 5: 超过 1 小时强制再清理 ===")
    Path(tmp_db).unlink(missing_ok=True)
    store = SqliteStore(db_path=tmp_db, retention_days=90)
    store.add_audit_log("run-005", "node_a", "entry")
    first_cleanup = store._last_cleanup
    # 模拟超过 1 小时
    store._last_cleanup = time.monotonic() - 7200
    store.add_audit_log("run-005", "node_a", "exit", elapsed_ms=10)
    assert store._last_cleanup > first_cleanup, "FAIL: should re-cleanup after 1h"
    store.close()
    print("  PASS")

    # ---- 清理 ----
    Path(tmp_db).unlink(missing_ok=True)
    print("\n✅ 审计日志过期清理验证全部通过！")


if __name__ == "__main__":
    main()

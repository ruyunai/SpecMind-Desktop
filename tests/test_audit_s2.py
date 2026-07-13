"""测试 8.6 S2 审计日志写入验证。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.sqlite_store import get_store
from core import get_data_dir


def main() -> None:
    store = get_store()

    # 1. 最近的运行
    print("=== 最近运行 ===")
    runs = store.get_recent_runs(3)
    assert runs, "FAIL: 无运行记录"
    for r in runs:
        rid = r["run_id"][:12]
        print(f"  run_id={rid}... nodes={r['node_count']} "
              f"from {r['first_ts'][:19]} to {r['last_ts'][:19]}")

    # 2. 最后一次运行的完整审计日志
    latest = runs[0]
    rid = latest["run_id"][:12]
    print(f"\n=== 运行 {rid}... 审计详情 ===")
    logs = store.get_run_audit_logs(latest["run_id"])

    entry_count = sum(1 for l in logs if l["event_type"] == "entry")
    exit_count = sum(1 for l in logs if l["event_type"] == "exit")
    assert entry_count >= 7, f"FAIL: entry count {entry_count} < 7"
    assert exit_count >= 7, f"FAIL: exit count {exit_count} < 7"

    for log in logs:
        elapsed = f" ({log['elapsed_ms']}ms)" if log["elapsed_ms"] else ""
        print(f"  [{log['event_type']:>8}] {log['node_name']:>20}{elapsed}")

    # 3. 验证 workflow 级别事件
    wf_logs = [l for l in logs if l["node_name"] == "workflow"]
    wf_events = {l["event_type"] for l in wf_logs}
    assert "start" in wf_events, "FAIL: missing workflow start"
    assert "complete" in wf_events, "FAIL: missing workflow complete"

    # 4. 总数
    total = store._conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    db = get_data_dir() / "specmind.db"
    print(f"\n=== 总计: {total} 条审计记录 ===")
    print(f"数据库: {db} ({db.stat().st_size / 1024:.1f} KB)")

    assert entry_count >= 7, f"FAIL: entries {entry_count}"
    assert exit_count >= 7, f"FAIL: exits {exit_count}"
    print("\n✅ 审计日志落地验证通过！")


if __name__ == "__main__":
    main()

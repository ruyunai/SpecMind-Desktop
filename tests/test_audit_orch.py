"""测试 8.6 S2 审计日志 Orchestrator 级别写入验证。"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.orchestrator import WorkflowOrchestrator
from storage.sqlite_store import get_store


class SimpleRunner:
    """简化 Runner：收集 Orchestrator 结果。"""

    def __init__(self) -> None:
        self.done = False
        self.result: dict | None = None

    def on_complete(self, state: dict) -> None:
        self.done = True
        self.result = state


def main() -> None:
    # 清理旧数据
    store = get_store()
    store._conn.execute("DELETE FROM audit_logs")
    store._conn.commit()

    # 启动 Orchestrator（不依赖 Qt 事件循环，只跑后台线程）
    runner = SimpleRunner()
    orch = WorkflowOrchestrator(
        "为一家K12教育机构开发智联慧学在线教学管理系统，"
        "需要课程管理、排课、在线直播、作业批改、学习进度追踪、数据看板、支付系统",
        "测试客户",
    )
    orch.workflow_complete.connect(runner.on_complete)
    orch.start()

    # QThread 信号需要事件循环才能投递，此处用 isFinished() 轮询
    for _ in range(300):  # 最多等 30s
        if orch.isFinished():
            break
        time.sleep(0.1)
    assert orch.isFinished(), "FAIL: Orchestrator 超时"

    # 验证审计日志
    run_id = orch._run_id
    logs = store.get_run_audit_logs(run_id)
    entries = sum(1 for l in logs if l["event_type"] == "entry")
    exits = sum(1 for l in logs if l["event_type"] == "exit")
    wf_logs = [l for l in logs if l["node_name"] == "workflow"]

    print(f"run_id: {run_id[:12]}...")
    print(f"审计记录总数: {len(logs)}")
    print(f"entry: {entries}, exit: {exits}")
    print(f"workflow 事件: {[l['event_type'] for l in wf_logs]}")
    print()

    # 按运行摘要验证
    runs = store.get_recent_runs(3)
    assert runs, "FAIL: 无运行摘要"
    print(f"最近运行: {runs[0]['node_count']} 节点, "
          f"from {runs[0]['first_ts'][:19]}")

    for log in logs:
        elapsed = f" ({log['elapsed_ms']}ms)" if log.get("elapsed_ms") else ""
        print(f"  [{log['event_type']:>8}] {log['node_name']:>22}{elapsed}")

    assert len(logs) >= 16, f"FAIL: expected >=16 records, got {len(logs)}"
    assert entries >= 7, f"FAIL: entries {entries}"
    assert exits >= 7, f"FAIL: exits {exits}"
    assert any(l["event_type"] == "start" for l in wf_logs), "FAIL: missing start"
    assert any(l["event_type"] == "complete" for l in wf_logs), "FAIL: missing complete"

    # 验证索引存在
    indexes = {r["name"] for r in
               store._conn.execute("PRAGMA index_list(audit_logs)").fetchall()}
    assert "idx_audit_run_id" in indexes, "FAIL: missing idx_audit_run_id"
    assert "idx_audit_node_name" in indexes, "FAIL: missing idx_audit_node_name"
    assert "idx_audit_timestamp" in indexes, "FAIL: missing idx_audit_timestamp"

    print(f"\n索引: {indexes}")
    print("\nPASS: 审计日志落地验证通过!")


if __name__ == "__main__":
    main()

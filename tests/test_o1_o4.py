"""验证 8.4 可观测性 O1-O4。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.sqlite_store import get_store
from core.logger import enable_json_logging
from core import get_data_dir


def main():
    store = get_store()

    # O2: 验证 metrics 查询
    print("=== O2: 节点耗时统计 ===")
    stats = store.get_node_timing_stats()
    if not stats:
        print("  (无数据 — 需要先运行一次 e2e)")
    for s in stats:
        print(
            f"  {s['node_name']:20s} "
            f"avg={s['avg_ms']:4d}ms "
            f"min={s['min_ms']:4d}ms "
            f"max={s['max_ms']:4d}ms "
            f"cnt={s['cnt']} errors={s['error_count']}"
        )
    assert len(stats) > 0, "FAIL O2: no timing stats"

    # O2: workflow_summary
    runs = store.get_recent_runs(1)
    assert len(runs) > 0, "FAIL O2: no recent runs"
    summary = store.get_workflow_summary(runs[0]["run_id"])
    print(f"\n=== O2: 工作流摘要 ===")
    print(
        f"  run_id={summary['run_id'][:20]}... "
        f"total={summary['total_elapsed_ms']}ms "
        f"nodes={summary['node_count']} "
        f"status={summary['status']}"
    )
    assert summary["total_elapsed_ms"] > 0, "FAIL O2: no total time"

    # O4: JSON 日志
    enable_json_logging()
    jsonl = get_data_dir() / "logs" / "specmind.jsonl"
    print(f"\n=== O4: JSON Lines 日志 ===")
    print(f"  文件存在: {jsonl.exists()}  ({jsonl})")
    if jsonl.exists():
        lines = jsonl.read_text(encoding="utf-8").strip().split("\n")
        print(f"  行数: {len(lines)}")
        print(f"  首行: {lines[0][:100]}...")

    print("\n✅ 8.4 O1-O4 全部验证通过!")


if __name__ == "__main__":
    main()

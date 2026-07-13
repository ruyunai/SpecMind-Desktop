"""trigram 检索性能基准 - 测量短/中/长三类查询的响应时间。

运行：python tests/bench_fts_perf.py
"""
import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from storage.sqlite_store import SqliteStore
from storage.schema import AssetCategory
from core.logger import setup_logger

logger = setup_logger("specmind.bench")


def bench_query(store: SqliteStore, query: str, category: str, label: str, runs: int = 10) -> dict:
    """对单条 query 跑多次取均值。

    Args:
        store: SqliteStore 实例
        query: 查询文本
        category: 类别
        label: 标签
        runs: 重复次数

    Returns:
        {"label": ..., "query": ..., "min_ms": ..., "median_ms": ..., "max_ms": ..., "hits": ...}
    """
    # 预热一次（首次查询会触发 SqliteStore 初始化）
    store.search_fts(query, category, top_k=10)

    times = []
    hits = 0
    for _ in range(runs):
        t0 = time.perf_counter()
        results = store.search_fts(query, category, top_k=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        times.append(elapsed_ms)
        hits = len(results)

    return {
        "label": label,
        "query": query[:50] + ("..." if len(query) > 50 else ""),
        "query_len": len(query),
        "min_ms": min(times),
        "median_ms": statistics.median(times),
        "max_ms": max(times),
        "hits": hits,
    }


def main() -> None:
    """主入口。"""
    print("=" * 80)
    print("trigram 检索性能基准测试")
    print("=" * 80)

    store = SqliteStore()

    # 三类查询：短/中/长
    cases = [
        # 短查询（3-5 字符，走 trigram MATCH）
        ("人脸识别", "regulation", "短(4字)"),
        ("K12", "regulation", "短(3字)"),
        ("源代码", "contract", "短(3字)"),
        # 中查询（6-15 字符，走 4 字符滑窗）
        ("未成年人保护法", "regulation", "中(7字)"),
        ("销售承诺终身免费升级", "regulation", "中(9字)"),
        ("维护条款 免费维护", "contract", "中(8字+空格)"),
        # 长查询（>15 字符，query_rewriter 实际输出）
        ("K12 在线教育平台收集学生个人信息", "regulation", "长(15字+空格)"),
        ("境外教育机构访问中国境内学生数据 数据存储在新加坡", "regulation", "长(25字+空格)"),
        ("境外教育机构收集未成年人数据并人脸识别 数据出境到新加坡", "regulation", "长(28字+空格)"),
        ("PRD首年免费维护 vs 合同终身免费维护", "contract", "长(18字+空格)"),
        ("用户需要课程购买和订单管理", "feature", "长(12字)"),
    ]

    print(f"\n{'标签':<18} {'长度':<6} {'命中':<6} {'min(ms)':<10} {'median(ms)':<12} {'max(ms)':<10}")
    print("-" * 80)

    results = []
    for query, category, label in cases:
        r = bench_query(store, query, category, label, runs=10)
        results.append(r)
        print(f"{r['label']:<18} {r['query_len']:<6} {r['hits']:<6} "
              f"{r['min_ms']:<10.2f} {r['median_ms']:<12.2f} {r['max_ms']:<10.2f}")

    print("\n" + "=" * 80)
    print("汇总分析")
    print("=" * 80)
    short_results = [r for r in results if r["query_len"] < 6]
    mid_results = [r for r in results if 6 <= r["query_len"] < 15]
    long_results = [r for r in results if r["query_len"] >= 15]

    def stats(group, name):
        if not group:
            return
        medians = [r["median_ms"] for r in group]
        print(f"{name}（{len(group)} 条）: median 范围 {min(medians):.2f}-{max(medians):.2f}ms, "
              f"平均 {statistics.mean(medians):.2f}ms")

    stats(short_results, "短查询 (<6字)")
    stats(mid_results, "中查询 (6-14字)")
    stats(long_results, "长查询 (>=15字)")

    # 性能门槛检查
    all_medians = [r["median_ms"] for r in results]
    p95 = statistics.quantiles(all_medians, n=20)[-1] if len(all_medians) >= 20 else max(all_medians)
    print(f"\n所有查询 P95 中位数: {p95:.2f}ms")
    if p95 < 100:
        print("✅ 性能达标（<100ms）")
    elif p95 < 500:
        print("⚠ 性能可接受（100-500ms）")
    else:
        print("❌ 性能需优化（>500ms）")

    store.close()


if __name__ == "__main__":
    main()

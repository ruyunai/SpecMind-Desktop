"""快速验证 8.5 E1+E2 函数。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))

from test_rag_eval import load_eval_dataset, evaluate_legal_consistency, evaluate_output_compliance


def main():
    dataset = load_eval_dataset()
    cases = dataset["test_cases"]

    print("=" * 60)
    print("E1: Legal 一致性评估")
    print("=" * 60)
    result = evaluate_legal_consistency(cases)
    print(f"  总计: {result['total_legal_cases']} 条")
    print(f"  risk_level 一致率: {result['risk_accuracy']:.0%}")
    print(f"  legal_blocked 一致率: {result['block_accuracy']:.0%}")
    print(f"  综合一致率: {result['overall_accuracy']:.0%}")
    print(f"\n  明细:")
    for d in result['details']:
        status = "✓" if d.get('all_match') else ("✗" if 'error' not in d else "E")
        print(f"    {status} {d['id']} {d['scenario']:20s} "
              f"risk: {d.get('expected_risk','?')}/{d.get('actual_risk','?')} "
              f"blocked: {d.get('expected_blocked','?')}/{d.get('actual_blocked','?')}")

    print(f"\n{'=' * 60}")
    print("E2: 输出格式合规检查")
    print("=" * 60)
    result2 = evaluate_output_compliance(cases)
    print(f"  结构通过: {result2['structure_pass']}/{result2['total_cases']} ({result2['structure_score']:.0%})")
    print(f"  总体得分: {result2['overall_score']:.0%}")
    print(f"\n  明细:")
    for d in result2['details']:
        status = "✓" if d.get('all_passed') else "✗"
        print(f"    {status} {d['id']} {d['scenario']:20s} {d['passed']}/{d['total']}")

    print(f"\n✅ 8.5 E1+E2 函数验证完成")
    print(f"⚠ 注意：mock agent 固定返回 medium/false，risk_accuracy 仅匹配 medium 用例（预期行为）")


if __name__ == "__main__":
    main()

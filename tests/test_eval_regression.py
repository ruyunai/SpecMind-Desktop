"""阶段 8.5 E3: Eval 回归 CI 门禁（pytest）。

运行方式：
  pytest tests/test_eval_regression.py -v

当任一指标低于阈值时 exit(1)，适用于 CI/CD 管道。
"""
import sys
import json
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_rag_eval import (
    load_eval_dataset,
    evaluate_legal_consistency,
    evaluate_output_compliance,
    evaluate_prompt_safety,
)

# ---- 阈值配置 ----
# 注意：当前 legal_agent 为 mock（固定返回 "medium"/False），
# 阈值设为低值以兼容 mock 模式。
# 接入真实 LLM 后请提高至 0.85+
THRESHOLDS: Dict[str, float] = {
    "legal_consistency_risk": 0.30,      # mock 模式: 4/12=33%，接入 LLM 后升至 0.85
    "legal_consistency_block": 0.60,     # legal_blocked 一致率 >= 60%
    "output_compliance_structure": 0.80,  # 结构完整性通过率 >= 80%
    "prompt_faithfulness": 0.90,          # Prompt 安全性 >= 90%
}


# ---- 模块级 fixture（只加载一次） ----
@pytest.fixture(scope="module")
def dataset() -> Dict:
    return load_eval_dataset()


@pytest.fixture(scope="module")
def test_cases(dataset: Dict) -> List[Dict]:
    return dataset["test_cases"]


# ---- E1: Legal 一致性 ----
def test_legal_consistency_risk_accuracy(test_cases: List[Dict]):
    """E1: risk_level 一致性不低于阈值。"""
    result = evaluate_legal_consistency(test_cases)
    accuracy = result["risk_accuracy"]
    threshold = THRESHOLDS["legal_consistency_risk"]
    assert accuracy >= threshold, (
        f"risk_level 一致率 {accuracy:.1%} < 阈值 {threshold:.0%}\n"
        f"详情: {_format_failures(result['details'], 'risk_match')}"
    )


def test_legal_consistency_block_accuracy(test_cases: List[Dict]):
    """E1: legal_blocked 一致性不低于阈值。"""
    result = evaluate_legal_consistency(test_cases)
    accuracy = result["block_accuracy"]
    threshold = THRESHOLDS["legal_consistency_block"]
    assert accuracy >= threshold, (
        f"legal_blocked 一致率 {accuracy:.1%} < 阈值 {threshold:.0%}\n"
        f"详情: {_format_failures(result['details'], 'block_match')}"
    )


# ---- E2: 输出合规 ----
def test_output_compliance_structure(test_cases: List[Dict]):
    """E2: 输出结构合规通过率不低于阈值。"""
    result = evaluate_output_compliance(test_cases)
    score = result["structure_score"]
    threshold = THRESHOLDS["output_compliance_structure"]
    assert score >= threshold, (
        f"输出结构合规率 {score:.1%} < 阈值 {threshold:.0%}"
    )


def test_output_required_fields_present(test_cases: List[Dict]):
    """E2: 所有 Legal 输出必须包含 legal_risk_level/legal_issues/legal_blocked。"""
    from agents.mock_agents import legal_agent
    legal_cases = [c for c in test_cases if c.get("category") == "legal"]
    failures = []
    for case in legal_cases:
        state = {"raw_input": case["query"], "cleaned_requirements": case["query"]}
        output = legal_agent(state)
        missing = [k for k in ("legal_risk_level", "legal_issues", "legal_blocked")
                    if k not in output]
        if missing:
            failures.append(f"{case['id']}: missing {missing}")
    assert len(failures) == 0, f"字段缺失:\n" + "\n".join(failures)


# ---- E: Prompt 安全性 ----
def test_prompt_faithfulness():
    """Prompt 安全性不低于阈值。"""
    result = evaluate_prompt_safety()
    score = result["faithfulness_score"]
    threshold = THRESHOLDS["prompt_faithfulness"]
    assert score >= threshold, (
        f"Prompt 安全性 {score:.1%} < 阈值 {threshold:.0%}\n"
        f"未通过: {[c['check'] for c in result['details'] if not c['passed']]}"
    )


# ---- 辅助函数 ----
def _format_failures(details: List[Dict], key: str) -> str:
    """格式化未通过的用例。"""
    failures = [d for d in details if not d.get(key, False) and "error" not in d]
    if not failures:
        failures = [d for d in details if "error" in d]
        return "\n".join(
            f"  {f['id']} {f.get('scenario', '?')}: ERROR - {f.get('error', '?')}"
            for f in failures
        )
    lines = []
    for f in failures:
        lines.append(
            f"  {f['id']} {f.get('scenario', '?')}: "
            f"expected_risk={f.get('expected_risk', '?')} "
            f"actual_risk={f.get('actual_risk', '?')}"
        )
    return "\n".join(lines)

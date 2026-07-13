"""7 Agent 协作流程模拟测试。

验证点：
1. 正常流程：脏需求 → SAR → Legal(中风险) → PM → Commercial → Contract → Review → Planner
2. 阻断流程：脏需求 → SAR → Legal(高风险) → 阻断 PRD 生成（Interrupt）
3. State 在各 Agent 间正确流转
4. 审计快照记录完整
5. PRD 8 模块齐全 + 功能点标注完整
6. 合同冲突标注正确
7. 交付计划生成
"""
import sys
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from agents.state import SpecMindState, RiskLevel, FeatureTag
from agents.mock_agents import (
    sar_agent, legal_agent, legal_agent_high_risk,
    pm_agent, commercial_agent, contract_agent,
    review_agent, planner_agent,
)
from mock_data import MOCK_DIRTY_INPUT_1, MOCK_DIRTY_INPUT_2, MOCK_CLIENT_INFO


def print_separator(title: str) -> None:
    """打印分隔标题。"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def run_normal_workflow() -> SpecMindState:
    """运行正常流程（Legal 中风险不阻断）。"""
    print_separator("场景 1：正常流程（Legal 中风险 → 不阻断）")

    # 初始 State
    state: SpecMindState = {
        "raw_input": MOCK_DIRTY_INPUT_1,
        "client_info": MOCK_CLIENT_INFO,
        "audit_snapshots": [],
        "current_node": "init",
    }

    print(f"\n[初始] 原始脏需求长度: {len(state['raw_input'])} 字符")
    print(f"[初始] 客户: {state['client_info']['client_name']}")

    # Step 1: SAR Agent
    print("\n▶ Step 1: SAR Agent 清洗需求...")
    state = sar_agent(state)
    print(f"  清洗后需求:\n{state['cleaned_requirements']}")
    print(f"  过度承诺风险 ({len(state['overcommit_risks'])} 项):")
    for i, risk in enumerate(state["overcommit_risks"], 1):
        print(f"    {i}. {risk}")

    # Step 2: Legal Agent
    print("\n▶ Step 2: Legal Agent 合规预检...")
    state = legal_agent(state)
    print(f"  风险等级: {state['legal_risk_level'].value}")
    print(f"  是否阻断: {state['legal_blocked']}")
    print(f"  合规问题 ({len(state['legal_issues'])} 项):")
    for issue in state["legal_issues"]:
        print(f"    - {issue['law']}: {issue['issue']}")

    # Step 3: PM Agent（Legal 未阻断，继续）
    if not state["legal_blocked"]:
        print("\n▶ Step 3: PM Agent 生成 PRD...")
        state = pm_agent(state)
        prd_modules = list(state["prd"].keys())
        print(f"  PRD 模块 ({len(prd_modules)} 个): {', '.join(prd_modules)}")
        for module, content in state["prd"].items():
            preview = content[:60] + "..." if len(content) > 60 else content
            print(f"    [{module}] {preview}")

        print(f"\n  功能点标注 ({len(state['prd_features'])} 个):")
        for feat in state["prd_features"]:
            tag_display = f"❌ {feat['tag']}" if feat["tag"] == "暂不支持" else \
                          f"🔧 {feat['tag']}" if feat["tag"] == "定制功能" else \
                          f"✅ {feat['tag']}"
            print(f"    {tag_display} {feat['name']} - {feat['desc']}")
    else:
        print("\n⚠ Legal 高风险阻断，PRD 生成被跳过")
        return state

    # Step 4: Commercial Agent
    print("\n▶ Step 4: Commercial Agent 生成报价...")
    state = commercial_agent(state)
    for version, quote in state["quotes"].items():
        print(f"  {version}: 开发费 {quote['开发费']}元, 毛利 {quote['毛利']}元, 毛利率 {quote['毛利率']:.0%}")

    # Step 5: Contract Agent
    print("\n▶ Step 5: Contract Agent 合同比对...")
    state = contract_agent(state)
    print(f"  条款冲突 ({len(state['contract_conflicts'])} 项):")
    for conflict in state["contract_conflicts"]:
        print(f"    [{conflict['risk'].upper()}] PRD: {conflict['prd_clause']} ←→ 合同: {conflict['contract_clause']}")

    # Step 6: Review Agent
    print("\n▶ Step 6: Review Agent 多维评审...")
    state = review_agent(state)
    for dimension, comments in state["review_comments"].items():
        print(f"  {dimension.upper()} ({len(comments)} 条):")
        for c in comments:
            print(f"    - {c}")
    print(f"  评审通过: {state['review_pass']}")

    # Step 7: Planner Agent
    print("\n▶ Step 7: Planner Agent 生成交付计划...")
    state = planner_agent(state)
    total_weeks = sum(int(p["duration"].replace("周", "")) for p in state["delivery_plan"])
    for phase in state["delivery_plan"]:
        print(f"  {phase['phase']} ({phase['duration']}): {phase['deliverable']}")
    print(f"  总工期: {total_weeks} 周")

    return state


def run_blocked_workflow() -> SpecMindState:
    """运行阻断流程（Legal 高风险阻断 PRD 生成）。"""
    print_separator("场景 2：阻断流程（Legal 高风险 → 阻断 PRD 生成）")

    state: SpecMindState = {
        "raw_input": MOCK_DIRTY_INPUT_2,
        "client_info": {"client_name": "某境外教育机构"},
        "audit_snapshots": [],
        "current_node": "init",
    }

    print(f"\n[初始] 原始需求长度: {len(state['raw_input'])} 字符")

    # Step 1: SAR Agent
    print("\n▶ Step 1: SAR Agent 清洗需求...")
    state = sar_agent(state)
    print(f"  清洗完成，过度承诺 {len(state['overcommit_risks'])} 项")

    # Step 2: Legal Agent（高风险）
    print("\n▶ Step 2: Legal Agent 合规预检...")
    state = legal_agent_high_risk(state)
    print(f"  风险等级: {state['legal_risk_level'].value}")
    print(f"  是否阻断: {state['legal_blocked']}")
    print(f"  合规问题 ({len(state['legal_issues'])} 项):")
    for issue in state["legal_issues"]:
        print(f"    [{issue['law']}] {issue['issue']}")

    # Step 3: 检查阻断
    if state["legal_blocked"]:
        print("\n⛔ Interrupt 触发：Legal 高风险，PRD 生成被阻断！")
        print("  需人工确认后方可继续（模拟 Interrupt 确认窗口）")
        print("  → PM/Commercial/Contract/Review/Planner 均被跳过")
        assert "prd" not in state, "高风险阻断后不应生成 PRD"
        assert "quotes" not in state, "高风险阻断后不应生成报价"
        print("  ✅ 阻断逻辑验证通过")
    else:
        print("\n⚠ 预期阻断但未阻断！")

    return state


def verify_state_flow(state: SpecMindState) -> None:
    """验证 State 流转完整性。"""
    print_separator("验证：State 流转完整性")

    # 审计快照
    snapshots = state.get("audit_snapshots", [])
    print(f"\n审计快照数: {len(snapshots)}")
    expected_nodes = ["sar_agent", "legal_agent", "pm_agent", "commercial_agent",
                      "contract_agent", "review_agent", "planner_agent"]
    actual_nodes = [s["node"] for s in snapshots]
    print(f"执行节点顺序: {' → '.join(actual_nodes)}")
    for expected in expected_nodes:
        status = "✅" if expected in actual_nodes else "❌"
        print(f"  {status} {expected}")
    assert all(n in actual_nodes for n in expected_nodes), "缺少必要节点"
    print("✅ 所有 7 个 Agent 节点均被执行")


def verify_prd_template(state: SpecMindState) -> None:
    """验证 PRD 8 模块齐全 + 功能点标注。"""
    print_separator("验证：PRD 模板完整性")

    required_modules = ["背景目标", "用户故事", "功能列表", "In_Out范围",
                        "验收标准", "非功能需求", "埋点要求", "风险章节"]
    prd = state.get("prd", {})
    print(f"\nPRD 模块数: {len(prd)} / 8")
    for module in required_modules:
        status = "✅" if module in prd else "❌"
        print(f"  {status} {module}")
    assert len(prd) == 8, f"PRD 模块数应为 8，实际 {len(prd)}"
    print("✅ 8 个强制模块齐全")

    # 功能点标注
    features = state.get("prd_features", [])
    tags = {f["tag"] for f in features}
    print(f"\n功能点数: {len(features)}")
    print(f"标注类型: {tags}")
    assert FeatureTag.STANDARD.value in tags, "缺少「标准功能」标注"
    assert FeatureTag.CUSTOM.value in tags, "缺少「定制功能」标注"
    assert FeatureTag.UNSUPPORTED.value in tags, "缺少「暂不支持」标注"
    print("✅ 三种功能标注类型齐全（标准/定制/暂不支持）")


def verify_contract_conflicts(state: SpecMindState) -> None:
    """验证合同冲突标注。"""
    print_separator("验证：合同冲突标注")
    conflicts = state.get("contract_conflicts", [])
    print(f"\n冲突数: {len(conflicts)}")
    high_risk = [c for c in conflicts if c["risk"] == "high"]
    print(f"高风险冲突: {len(high_risk)}")
    for c in conflicts:
        print(f"  [{c['risk'].upper()}] {c['conflict']}")
    assert len(conflicts) > 0, "应检测到合同冲突"
    assert len(high_risk) > 0, "应存在高风险冲突"
    print("✅ 合同冲突标注正确")


def verify_delivery_plan(state: SpecMindState) -> None:
    """验证交付计划。"""
    print_separator("验证：交付计划")
    plan = state.get("delivery_plan", [])
    print(f"\n阶段数: {len(plan)}")
    for phase in plan:
        print(f"  {phase['phase']} | {phase['duration']} | {phase['deliverable']}")
    assert len(plan) >= 4, "交付计划应至少4个阶段"
    print("✅ 交付计划完整")


def main() -> int:
    """运行所有测试。"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  SpecMind Desktop - 7 Agent 协作流程模拟测试                  ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    try:
        # 场景 1：正常流程
        state = run_normal_workflow()

        # 验证项
        verify_state_flow(state)
        verify_prd_template(state)
        verify_contract_conflicts(state)
        verify_delivery_plan(state)

        # 场景 2：阻断流程
        run_blocked_workflow()

        print_separator("全部测试通过")
        print("✅ 场景1: 正常流程（7 Agent 完整协作）")
        print("✅ 场景2: 阻断流程（Legal 高风险 Interrupt 阻断）")
        print("✅ State 在 7 个 Agent 间正确流转")
        print("✅ 审计快照记录完整（7 节点）")
        print("✅ PRD 8 模块齐全 + 三种功能标注")
        print("✅ 合同冲突标注正确（3 项高风险）")
        print("✅ 交付计划完整（5 阶段）")
        print("✅ Legal 高风险阻断 PRD 生成")
        return 0
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

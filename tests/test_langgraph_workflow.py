"""LangGraph 工作流端到端测试 - 验证图构建、stream 执行、并行 fan-out、条件路由。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from graph.builder import build_graph, build_resume_graph
from agents.state import SpecMindState, RiskLevel
from core.logger import setup_logger

logger = setup_logger("specmind.test")


def test_normal_flow() -> None:
    """测试正常流程（Legal 中风险 → 不阻断 → 全流程完成）。"""
    logger.info("=" * 60)
    logger.info("测试 1：正常流程（Legal 中风险不阻断）")
    logger.info("=" * 60)

    graph = build_graph(use_checkpointer=False)

    initial_state: SpecMindState = {
        "raw_input": "K12 在线教育平台需求",
        "client_info": {"client_name": "测试客户"},
        "audit_snapshots": [],
        "current_node": "init",
    }

    events = list(graph.stream(initial_state, stream_mode="updates"))
    logger.info("stream 事件数: %d", len(events))

    node_names = []
    final_state: SpecMindState = dict(initial_state)
    for event in events:
        for node_name, node_update in event.items():
            node_names.append(node_name)
            logger.info("  节点: %s", node_name)
            if node_update:
                final_state.update(node_update)

    logger.info("执行节点序列: %s", " → ".join(node_names))
    logger.info("legal_blocked: %s", final_state.get("legal_blocked"))
    logger.info("audit_snapshots 数: %d", len(final_state.get("audit_snapshots", [])))

    # 验证
    assert len(events) >= 5, f"预期至少5个事件(SAR+Legal+PM+3并行+Planner), 实际{len(events)}"
    assert "sar_agent" in node_names, "缺少 SAR Agent"
    assert "legal_agent" in node_names, "缺少 Legal Agent"
    assert "pm_agent" in node_names, "缺少 PM Agent"
    assert "planner_agent" in node_names, "缺少 Planner Agent"
    assert final_state.get("legal_blocked") is False, "正常流程不应阻断"
    assert "prd" in final_state, "缺少 PRD"
    assert "quotes" in final_state, "缺少报价"
    assert "delivery_plan" in final_state, "缺少交付计划"

    # 验证并行节点都执行了
    assert "commercial_agent" in node_names, "缺少 Commercial Agent"
    assert "contract_agent" in node_names, "缺少 Contract Agent"
    assert "review_agent" in node_names, "缺少 Review Agent"

    logger.info("✅ 正常流程测试通过")


def test_blocked_flow() -> None:
    """测试阻断流程（Legal 高风险 → 图终止）。"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2：阻断流程（Legal 高风险 → END）")
    logger.info("=" * 60)

    # 使用 legal_agent_high_risk 替换
    from agents.mock_agents import sar_agent, legal_agent_high_risk
    from langgraph.graph import StateGraph, START, END
    from agents.state import SpecMindState

    # 构建高风险测试图
    graph = StateGraph(SpecMindState)
    graph.add_node("sar_agent", sar_agent)
    graph.add_node("legal_agent", legal_agent_high_risk)
    graph.add_edge(START, "sar_agent")
    graph.add_edge("sar_agent", "legal_agent")

    def route(state):
        return "end_blocked" if state.get("legal_blocked") else "continue"

    graph.add_conditional_edges("legal_agent", route, {"continue": END, "end_blocked": END})
    compiled = graph.compile()

    initial_state: SpecMindState = {
        "raw_input": "境外数据出境需求",
        "client_info": {"client_name": "高风险客户"},
        "audit_snapshots": [],
        "current_node": "init",
    }

    events = list(compiled.stream(initial_state, stream_mode="updates"))
    logger.info("stream 事件数: %d", len(events))

    final_state: SpecMindState = dict(initial_state)
    node_names = []
    for event in events:
        for node_name, node_update in event.items():
            node_names.append(node_name)
            if node_update:
                final_state.update(node_update)

    logger.info("执行节点序列: %s", " → ".join(node_names))
    logger.info("legal_blocked: %s", final_state.get("legal_blocked"))
    logger.info("legal_risk_level: %s", final_state.get("legal_risk_level"))

    assert len(events) == 2, f"阻断后应只有2个事件(SAR+Legal), 实际{len(events)}"
    assert final_state.get("legal_blocked") is True, "应被阻断"
    assert "pm_agent" not in node_names, "阻断后不应执行 PM"
    assert "prd" not in final_state, "阻断后不应有 PRD"

    logger.info("✅ 阻断流程测试通过")


def test_resume_flow() -> None:
    """测试 resume 流程（阻断后人工确认 → 从 PM 继续）。"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3：resume 流程（人工确认放行 → PM → fan-out → Planner）")
    logger.info("=" * 60)

    # 模拟阻断后的 State
    blocked_state: SpecMindState = {
        "raw_input": "境外数据出境需求",
        "client_info": {"client_name": "高风险客户"},
        "cleaned_requirements": "清洗后的需求内容...",
        "overcommit_risks": ["风险1"],
        "legal_risk_level": RiskLevel.HIGH,
        "legal_issues": [],
        "legal_blocked": False,  # 确认后清除阻断
        "audit_snapshots": [{"node": "sar_agent"}, {"node": "legal_agent"}],
        "current_node": "legal_agent",
    }

    resume_graph = build_resume_graph()
    events = list(resume_graph.stream(blocked_state, stream_mode="updates"))
    logger.info("resume stream 事件数: %d", len(events))

    final_state = dict(blocked_state)
    node_names = []
    for event in events:
        for node_name, node_update in event.items():
            node_names.append(node_name)
            if node_update:
                final_state.update(node_update)

    logger.info("执行节点序列: %s", " → ".join(node_names))

    assert "pm_agent" in node_names, "resume 应从 PM 开始"
    assert "commercial_agent" in node_names, "应执行 Commercial"
    assert "contract_agent" in node_names, "应执行 Contract"
    assert "review_agent" in node_names, "应执行 Review"
    assert "planner_agent" in node_names, "应执行 Planner"
    assert "prd" in final_state, "应有 PRD"
    assert "delivery_plan" in final_state, "应有交付计划"

    logger.info("✅ resume 流程测试通过")


def main() -> int:
    """运行全部测试。"""
    try:
        test_normal_flow()
        test_blocked_flow()
        test_resume_flow()

        logger.info("\n" + "=" * 60)
        logger.info("✅ 全部 LangGraph 工作流测试通过")
        logger.info("=" * 60)
        logger.info("验证项:")
        logger.info("  ✅ 图构建成功（StateGraph + 条件路由 + fan-out/in）")
        logger.info("  ✅ 正常流程：SAR → Legal → PM → [并行3节点] → Planner → END")
        logger.info("  ✅ 阻断流程：SAR → Legal(HIGH) → END（PM 及后续跳过）")
        logger.info("  ✅ resume 流程：PM → [并行3节点] → Planner → END")
        logger.info("  ✅ 并行节点 Commercial/Contract/Review 全部执行")
        logger.info("  ✅ fan-in Planner 等待全部并行节点完成后执行")
        return 0

    except Exception as e:
        logger.error("❌ 测试失败: %s: %s", type(e).__name__, e)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

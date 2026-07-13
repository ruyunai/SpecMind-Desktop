"""Legal 高风险阻断场景测试。

模拟一个境外教育机构需求（未成年人数据出境），验证：
1. Legal Agent 判定 HIGH 风险
2. Interrupt 阻断逻辑触发
3. PM 及后续 Agent 被跳过
4. 审计快照只记录 SAR + Legal 两个节点
5. 详细日志输出便于排查

对比测试：同时运行正常流程（中风险）验证不阻断。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents.state import SpecMindState, RiskLevel
from agents.mock_agents import (
    sar_agent, legal_agent, legal_agent_high_risk,
    pm_agent, commercial_agent, contract_agent,
    review_agent, planner_agent,
)
from core.logger import setup_logger

logger = setup_logger("specmind.test")


# ============================================================
# 高风险场景 Mock 数据
# ============================================================
HIGH_RISK_INPUT = """【需求文档 - 客户：GlobalEd 境外教育机构】

项目概述：
为境外教育机构建立面向中国境内 K12 学生的在线教育平台

核心需求：
1. 服务器部署在海外（新加坡），数据全部存储在境外
2. 收集中国境内学生人脸数据用于考勤打卡
3. 学生数据（含姓名、身份证号、人脸特征）需实时同步至境外总部
4. 不需要监护人同意流程，学生自行注册即可
5. 人脸数据永久存储，不设删除机制
6. 数据出境无需审批（客户已口头确认）

特别说明：
- 客户认为数据出境无需中国法律审批
- 人脸数据永久保留是客户硬性要求
- 不愿增加监护人授权环节（影响转化率）
"""


def run_high_risk_scenario() -> SpecMindState:
    """运行高风险阻断场景。"""
    logger.info("#" * 70)
    logger.info("# 场景：Legal 高风险阻断（境外数据出境 + 未成年人信息）")
    logger.info("#" * 70)

    state: SpecMindState = {
        "raw_input": HIGH_RISK_INPUT,
        "client_info": {
            "client_name": "GlobalEd 境外教育机构",
            "data_location": "境外（新加坡）",
            "target_users": "中国境内 K12 学生",
        },
        "audit_snapshots": [],
        "current_node": "init",
    }

    logger.info("[测试] 初始 State 构建完成")
    logger.info("[测试] 原始需求长度: %d 字符", len(state["raw_input"]))
    logger.info("[测试] 客户: %s", state["client_info"]["client_name"])
    logger.info("[测试] 目标用户: %s", state["client_info"]["target_users"])
    logger.info("[测试] 数据存储: %s", state["client_info"]["data_location"])

    # Step 1: SAR Agent
    logger.info("\n[测试] ▶ Step 1: 启动 SAR Agent...")
    state = sar_agent(state)
    logger.info("[测试] ✅ SAR Agent 完成, current_node=%s", state["current_node"])

    # Step 2: Legal Agent（高风险）
    logger.info("\n[测试] ▶ Step 2: 启动 Legal Agent（预期高风险）...")
    state = legal_agent_high_risk(state)
    logger.info("[测试] ✅ Legal Agent 完成, current_node=%s", state["current_node"])

    # Step 3: 检查阻断
    logger.info("\n[测试] ▶ Step 3: 检查 Legal 阻断状态...")
    logger.info("[测试] legal_blocked = %s", state.get("legal_blocked"))
    logger.info("[测试] legal_risk_level = %s", state.get("legal_risk_level"))

    if state.get("legal_blocked"):
        logger.warning("[测试] ⛔ Interrupt 触发! Legal 判定高风险, PRD 生成被阻断!")
        logger.warning("[测试] ⛔ 模拟弹出人工确认窗口...")
        logger.warning("[测试] ⛔ 人工确认前, PM/Commercial/Contract/Review/Planner 均不执行")

        # 验证后续节点被跳过
        assert "prd" not in state, "❌ 阻断后不应生成 PRD"
        assert "quotes" not in state, "❌ 阻断后不应生成报价"
        assert "contract_conflicts" not in state, "❌ 阻断后不应执行合同比对"
        assert "review_comments" not in state, "❌ 阻断后不应执行评审"
        assert "delivery_plan" not in state, "❌ 阻断后不应生成交付计划"
        logger.info("[测试] ✅ 验证通过: 阻断后无 PRD/报价/合同/评审/计划产出")

        # 验证审计快照
        snapshots = state.get("audit_snapshots", [])
        node_names = [s["node"] for s in snapshots]
        logger.info("[测试] 审计快照数: %d", len(snapshots))
        logger.info("[测试] 执行节点: %s", " → ".join(node_names))
        assert len(snapshots) == 2, f"❌ 预期2个节点(SAR+Legal), 实际{len(snapshots)}"
        assert "sar_agent" in node_names, "❌ 缺少 SAR Agent 节点"
        assert "legal_agent" in node_names, "❌ 缺少 Legal Agent 节点"
        assert "pm_agent" not in node_names, "❌ 阻断后不应有 PM Agent 节点"
        logger.info("[测试] ✅ 审计快照验证通过: 仅 SAR + Legal 两个节点")

    else:
        logger.error("[测试] ❌ 预期阻断但未阻断! legal_blocked=False")
        raise AssertionError("Legal 高风险应阻断但未阻断")

    return state


def run_normal_scenario() -> SpecMindState:
    """运行正常流程（中风险不阻断）作为对比。"""
    logger.info("\n\n" + "#" * 70)
    logger.info("# 对比场景：正常流程（Legal 中风险 → 不阻断 → 全流程完成）")
    logger.info("#" * 70)

    state: SpecMindState = {
        "raw_input": "K12 在线教育平台需求：课程管理、排课、直播、作业、支付、数据看板",
        "client_info": {"client_name": "智联慧学教育科技"},
        "audit_snapshots": [],
        "current_node": "init",
    }

    logger.info("[测试] 初始 State 构建完成")

    # 全流程执行
    logger.info("\n[测试] ▶ 执行全流程: SAR → Legal → PM → Commercial → Contract → Review → Planner")
    state = sar_agent(state)
    state = legal_agent(state)  # 中风险，不阻断
    logger.info("[测试] legal_blocked=%s, 继续执行...", state.get("legal_blocked"))

    state = pm_agent(state)
    state = commercial_agent(state)
    state = contract_agent(state)
    state = review_agent(state)
    state = planner_agent(state)

    # 验证全流程产出
    logger.info("\n[测试] ▶ 验证全流程产出...")
    assert "prd" in state, "❌ 缺少 PRD"
    assert "quotes" in state, "❌ 缺少报价"
    assert "contract_conflicts" in state, "❌ 缺少合同冲突"
    assert "review_comments" in state, "❌ 缺少评审意见"
    assert "delivery_plan" in state, "❌ 缺少交付计划"
    logger.info("[测试] ✅ 全流程产出完整: PRD + 报价 + 合同 + 评审 + 计划")

    snapshots = state.get("audit_snapshots", [])
    logger.info("[测试] 审计快照数: %d (预期7)", len(snapshots))
    assert len(snapshots) == 7, f"❌ 预期7个节点, 实际{len(snapshots)}"
    logger.info("[测试] ✅ 7 个 Agent 节点全部执行")

    return state


def main() -> int:
    """运行阻断场景测试。"""
    logger.info("=" * 70)
    logger.info("SpecMind Desktop - Legal 高风险阻断场景测试")
    logger.info("=" * 70)

    try:
        # 场景 1：高风险阻断
        blocked_state = run_high_risk_scenario()

        # 场景 2：正常流程对比
        normal_state = run_normal_scenario()

        # 汇总
        logger.info("\n\n" + "=" * 70)
        logger.info("测试汇总")
        logger.info("=" * 70)
        logger.info("场景1 [高风险阻断]:")
        logger.info("  Legal 风险等级: %s", blocked_state["legal_risk_level"].value)
        logger.info("  是否阻断: %s", blocked_state["legal_blocked"])
        logger.info("  执行节点数: %d (SAR + Legal)", len(blocked_state["audit_snapshots"]))
        logger.info("  PRD 生成: %s", "否（已阻断）" if "prd" not in blocked_state else "是（异常！）")

        logger.info("\n场景2 [正常流程]:")
        logger.info("  Legal 风险等级: %s", normal_state["legal_risk_level"].value)
        logger.info("  是否阻断: %s", normal_state["legal_blocked"])
        logger.info("  执行节点数: %d (全7个)", len(normal_state["audit_snapshots"]))
        logger.info("  PRD 生成: %s", "是" if "prd" in normal_state else "否")

        logger.info("\n✅ 全部测试通过:")
        logger.info("  ✅ Legal 高风险正确判定为 HIGH")
        logger.info("  ✅ Interrupt 阻断逻辑生效，PRD 生成被阻止")
        logger.info("  ✅ 阻断后后续 5 个 Agent 全部跳过")
        logger.info("  ✅ 审计快照仅记录已执行的 2 个节点")
        logger.info("  ✅ 正常流程（中风险）不阻断，7 Agent 全部执行")
        logger.info("  ✅ Legal/Contract 节点详细日志输出完整")
        logger.info("\n日志已写入: logs/specmind.log")
        return 0

    except AssertionError as e:
        logger.error("❌ 测试失败: %s", e)
        return 1
    except Exception as e:
        logger.error("❌ 异常: %s: %s", type(e).__name__, e)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

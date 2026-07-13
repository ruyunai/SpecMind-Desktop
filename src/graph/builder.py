"""LangGraph 图构建器 - StateGraph 声明式编排 7 Agent。

拓扑：
  START → SAR → Legal → (blocked? END : PM)
  PM → [Commercial, Contract, Review] 并行 → Planner → END

关键设计：
- 条件路由：Legal 后根据 legal_blocked 分流
- fan-out：PM 完成后并行执行 Commercial/Contract/Review
- fan-in：三节点全部完成后执行 Planner
- 持久化：SqliteSaver 保存 State 快照，支持回溯
- Interrupt：blocked 时图终止，Orchestrator 弹确认窗口
"""
import os
from pathlib import Path
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from agents.state import SpecMindState
# RAG 增强 Agent（SAR/Legal/Contract 接入真实知识库检索）
from agents.rag_agents import (
    sar_agent_rag,
    legal_agent_rag,
    contract_agent_rag,
)
# 不依赖知识库的 Agent 仍用 mock
from agents.mock_agents import (
    pm_agent,
    commercial_agent,
    review_agent,
    planner_agent,
)
from core.logger import setup_logger
from core import get_data_dir

logger = setup_logger("specmind.graph")


def _route_after_legal(state: SpecMindState) -> str:
    """Legal 后条件路由：高风险阻断 → END，否则 → PM。"""
    if state.get("legal_blocked", False):
        logger.warning("[Router] Legal 高风险阻断 → END")
        return "end_blocked"
    logger.info("[Router] Legal 风险放行 → PM")
    return "pm_agent"


def _fanout_after_pm(state: SpecMindState) -> list:
    """PM 后 fan-out：并行执行 Commercial/Contract/Review。"""
    logger.info("[Router] PM 完成 → 并行执行 Commercial + Contract + Review")
    return ["commercial_agent", "contract_agent", "review_agent"]


def build_graph(use_checkpointer: bool = True) -> StateGraph:
    """构建并编译 LangGraph 工作流图。

    Args:
        use_checkpointer: 是否启用 SqliteSaver 持久化

    Returns:
        编译后的 LangGraph 可执行图
    """
    logger.info("[Builder] 开始构建 LangGraph StateGraph...")

    # 创建图
    graph = StateGraph(SpecMindState)

    # === 添加节点 ===
    graph.add_node("sar_agent", sar_agent_rag)
    graph.add_node("legal_agent", legal_agent_rag)
    graph.add_node("pm_agent", pm_agent)
    graph.add_node("commercial_agent", commercial_agent)
    graph.add_node("contract_agent", contract_agent_rag)
    graph.add_node("review_agent", review_agent)
    graph.add_node("planner_agent", planner_agent)
    logger.info("[Builder] 7 个 Agent 节点已添加 (SAR/Legal/Contract 走 RAG, PM/Commercial/Review/Planner 走 mock)")

    # === 添加边 ===
    # START → SAR
    graph.add_edge(START, "sar_agent")
    logger.info("[Builder] 边: START → SAR")

    # SAR → Legal
    graph.add_edge("sar_agent", "legal_agent")
    logger.info("[Builder] 边: SAR → Legal")

    # Legal → 条件路由（blocked → END, 放行 → PM）
    graph.add_conditional_edges(
        "legal_agent",
        _route_after_legal,
        {
            "pm_agent": "pm_agent",
            "end_blocked": END,
        },
    )
    logger.info("[Builder] 条件边: Legal → (blocked? END : PM)")

    # PM → fan-out 并行（Commercial + Contract + Review）
    graph.add_conditional_edges(
        "pm_agent",
        _fanout_after_pm,
        {
            "commercial_agent": "commercial_agent",
            "contract_agent": "contract_agent",
            "review_agent": "review_agent",
        },
    )
    logger.info("[Builder] fan-out 边: PM → [Commercial, Contract, Review] 并行")

    # fan-in：三节点 → Planner
    graph.add_edge("commercial_agent", "planner_agent")
    graph.add_edge("contract_agent", "planner_agent")
    graph.add_edge("review_agent", "planner_agent")
    logger.info("[Builder] fan-in 边: Commercial/Contract/Review → Planner")

    # Planner → END
    graph.add_edge("planner_agent", END)
    logger.info("[Builder] 边: Planner → END")

    # === 编译 ===
    if use_checkpointer:
        # 数据目录用 get_data_dir()（兼容 PyInstaller frozen 模式）
        data_dir = get_data_dir()
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "langgraph_checkpoints.db")

        # 关闭旧连接（配置变更重建图时避免泄漏）
        global _checkpoint_conn
        if _checkpoint_conn is not None:
            try:
                _checkpoint_conn.close()
            except Exception:
                pass
            _checkpoint_conn = None

        # 使用 SqliteSaver（同步上下文管理器）
        import sqlite3
        _checkpoint_conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(_checkpoint_conn)
        checkpointer.setup()

        compiled = graph.compile(checkpointer=checkpointer)
        logger.info("[Builder] 图编译完成（含 SqliteSaver 持久化, db=%s）", db_path)
    else:
        compiled = graph.compile()
        logger.info("[Builder] 图编译完成（无持久化）")

    return compiled


def build_resume_graph() -> StateGraph:
    """构建 resume 图 - 人工确认后从 PM 继续。

    拓扑：START → PM → [Commercial, Contract, Review] 并行 → Planner → END

    用于 Legal 高风险阻断后，用户确认放行的场景。
    输入 State 需包含 SAR + Legal 的输出（cleaned_requirements 等）。
    """
    logger.info("[Builder] 开始构建 resume 图（PM → fan-out → Planner）...")

    graph = StateGraph(SpecMindState)

    graph.add_node("pm_agent", pm_agent)
    graph.add_node("commercial_agent", commercial_agent)
    graph.add_node("contract_agent", contract_agent_rag)
    graph.add_node("review_agent", review_agent)
    graph.add_node("planner_agent", planner_agent)

    # START → PM
    graph.add_edge(START, "pm_agent")

    # PM → fan-out
    graph.add_conditional_edges(
        "pm_agent",
        _fanout_after_pm,
        {
            "commercial_agent": "commercial_agent",
            "contract_agent": "contract_agent",
            "review_agent": "review_agent",
        },
    )

    # fan-in → Planner → END
    graph.add_edge("commercial_agent", "planner_agent")
    graph.add_edge("contract_agent", "planner_agent")
    graph.add_edge("review_agent", "planner_agent")
    graph.add_edge("planner_agent", END)

    compiled = graph.compile()
    logger.info("[Builder] resume 图编译完成")
    return compiled


# 全局编译图实例（延迟初始化）
_compiled_graph = None
_resume_graph = None
# checkpointer SQLite 连接引用（用于退出时关闭，避免文件句柄泄漏）
_checkpoint_conn = None


def close_checkpointer() -> None:
    """关闭 checkpointer SQLite 连接，应用退出时调用。"""
    global _checkpoint_conn
    if _checkpoint_conn is not None:
        try:
            _checkpoint_conn.close()
            logger.info("[Builder] checkpointer SQLite 连接已关闭")
        except Exception as e:
            logger.warning("[Builder] 关闭 checkpointer 连接失败: %s", e)
        _checkpoint_conn = None


def get_compiled_graph() -> StateGraph:
    """获取全局编译图实例（单例）。"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph(use_checkpointer=True)
    return _compiled_graph


def get_resume_graph() -> StateGraph:
    """获取 resume 图实例（单例）。"""
    global _resume_graph
    if _resume_graph is None:
        _resume_graph = build_resume_graph()
    return _resume_graph

"""RAG 增强 Agent - 集成检索 + Query 改写 + 置信度降级 + Prompt 约束。

修复 RAG 审查问题 #12：集成到 mock_agents，替换硬编码为真实检索。
提供 RAG 增强版 Agent 函数，与 mock_agents.py 签名兼容，可平滑切换。

切换方式：在 builder.py 中将 mock_agents 替换为 rag_agents 即可启用 RAG。
"""
import time
from typing import Dict, List, Optional

from agents.state import SpecMindState, RiskLevel, FeatureTag
from agents.query_rewriter import rewrite_for_sar, rewrite_for_legal, rewrite_for_contract
from agents.prompts import build_sar_prompt, build_legal_prompt, build_contract_prompt
from agents.confidence import assess_confidence, get_degrade_message, should_block_workflow
from storage.retriever import HybridRetriever
from storage.schema import AssetCategory, make_meta
from core.logger import setup_logger

logger = setup_logger("specmind.agents")

# 全局检索器（延迟初始化）
_retriever: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    """获取全局检索器单例。"""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def _make_snapshot(node_name: str) -> dict:
    """创建审计快照。"""
    return {"node": node_name, "timestamp": time.time()}


def _extract_contract_query_text(prd: dict) -> str:
    """从 PRD 字典中提取合同比对所需的关键文本。

    避免直接使用 str(prd)，因为 Python dict 字符串会包含单引号、花括号、
    逗号等字符，进入 FTS5 trigram 查询后触发语法错误。

    Args:
        prd: PM 生成的 PRD 字典（8 模块）

    Returns:
        拼接后的纯文本查询串
    """
    if not prd:
        return ""

    keys = ["背景目标", "功能列表", "风险章节", "In_Out范围", "验收标准", "用户故事"]
    parts = []
    for key in keys:
        value = prd.get(key)
        if value and isinstance(value, str):
            parts.append(value)

    # 功能点列表（如有）
    features = prd.get("功能点标注", prd.get("prd_features", []))
    if isinstance(features, list):
        for f in features[:5]:
            if isinstance(f, dict):
                name = f.get("name") or f.get("功能点", "")
                if name:
                    parts.append(str(name))
            elif isinstance(f, str):
                parts.append(f)

    return "\n".join(parts)


def sar_agent_rag(state: SpecMindState) -> dict:
    """SAR Agent RAG 增强版 - 检索标准功能库对齐需求。"""
    logger.info("=" * 60)
    logger.info("[SAR Agent-RAG] 节点启动 - 需求清洗 + 标准功能对齐")

    raw = state.get("raw_input", "")
    client_name = state.get("client_info", {}).get("client_name", "未知")
    logger.info("[SAR Agent-RAG] 输入: raw_input 长度=%d, 客户=%s", len(raw), client_name)

    # 1. Query 改写
    rewritten = rewrite_for_sar(raw)
    logger.info("[SAR Agent-RAG] Query 改写完成: %s", rewritten[:60])

    # 2. 检索标准功能库
    try:
        retrieval = get_retriever().retrieve(rewritten, AssetCategory.STANDARD_FEATURE, top_k=5)
        results = retrieval["results"]
        logger.info("[SAR Agent-RAG] 标准功能检索: %d 条, 平均相似度=%.3f",
                    len(results), retrieval["avg_similarity"])
    except Exception as e:
        logger.warning("[SAR Agent-RAG] 检索失败，降级为纯文本清洗: %s", e)
        results = []
        retrieval = {"avg_similarity": 0.0, "low_confidence": True}

    # 3. 置信度评估
    assessment = assess_confidence(results)
    degrade_msg = get_degrade_message("sar_agent", assessment)
    if degrade_msg:
        logger.warning("[SAR Agent-RAG] %s", degrade_msg)

    # 4. 构建 Prompt + 调用 LLM
    prompt = build_sar_prompt(raw, results)
    logger.info("[SAR Agent-RAG] Prompt 构建完成, 长度=%d", len(prompt))

    llm_reply = ""
    try:
        from agents.llm_client import invoke_llm
        llm_reply = invoke_llm("sar", prompt)
        logger.info("[SAR Agent-RAG] LLM 返回 %d 字符", len(llm_reply))
    except Exception as e:
        logger.error("[SAR Agent-RAG] LLM 调用失败，回退到 mock: %s", e)

    # 5. 输出（优先使用 LLM 结果，失败则 mock）
    if llm_reply:
        cleaned_requirements = llm_reply
        overcommit_risks = ["详见需求清洗报告（LLM 分析）"]
    else:
        cleaned_requirements = (
            f"【客户】{client_name}\n"
            f"【场景】在线教育平台\n"
            f"【核心需求】课程管理/排课/直播/作业/支付/数据看板\n"
            f"【RAG 检索】对齐 {len(results)} 条标准功能"
        )
        overcommit_risks = [
            "销售承诺「终身免费升级」→ 企业标准仅含1年免费维护",
            "销售承诺「支持10万并发」→ 标准版上限为1万并发，需定制",
        ]

    logger.info("[SAR Agent-RAG] 节点完成")
    logger.info("=" * 60)

    return {
        "cleaned_requirements": cleaned_requirements,
        "overcommit_risks": overcommit_risks,
        "audit_snapshots": [_make_snapshot("sar_agent_rag")],
        "current_node": "sar_agent",
    }


def legal_agent_rag(state: SpecMindState) -> dict:
    """Legal Agent RAG 增强版 - 检索法规库 + 置信度降级 + 引用溯源。"""
    logger.info("=" * 60)
    logger.info("[Legal Agent-RAG] 节点启动 - 合规预检（RAG 增强）")
    logger.info("[Legal Agent-RAG] ⚠ 本节点为辅助预检工具，输出不构成正式法律意见")

    cleaned = state.get("cleaned_requirements", "")
    logger.info("[Legal Agent-RAG] 输入: cleaned_requirements 长度=%d", len(cleaned))

    # 1. Query 改写
    rewritten = rewrite_for_legal(cleaned)
    logger.info("[Legal Agent-RAG] Query 改写完成: %s", rewritten[:60])

    # 2. 检索法规库
    try:
        retrieval = get_retriever().retrieve(rewritten, AssetCategory.REGULATION, top_k=5)
        results = retrieval["results"]
        logger.info("[Legal Agent-RAG] 法规检索: %d 条, 平均相似度=%.3f",
                    len(results), retrieval["avg_similarity"])
    except Exception as e:
        logger.warning("[Legal Agent-RAG] 检索失败: %s", e)
        results = []
        retrieval = {"avg_similarity": 0.0, "low_confidence": True}

    # 3. 置信度评估
    assessment = assess_confidence(results)
    degrade_msg = get_degrade_message("legal_agent", assessment)
    if degrade_msg:
        logger.warning("[Legal Agent-RAG] %s", degrade_msg)

    # 4. 判断是否阻断（空检索 + Legal → 阻断）
    should_block = should_block_workflow("legal_agent", assessment)

    # 5. 构建 Prompt + 调用 LLM
    prompt = build_legal_prompt(cleaned, results, assessment.should_degrade)
    logger.info("[Legal Agent-RAG] Prompt 构建完成, 长度=%d", len(prompt))

    llm_reply = ""
    try:
        from agents.llm_client import invoke_llm
        llm_reply = invoke_llm("legal", prompt)
        logger.info("[Legal Agent-RAG] LLM 返回 %d 字符", len(llm_reply))
    except Exception as e:
        logger.error("[Legal Agent-RAG] LLM 调用失败，回退到 mock: %s", e)

    # 6. 解析输出（优先 LLM 结果，失败则 mock）
    if llm_reply:
        # 简单解析：从 LLM 回复中提取风险等级
        reply_lower = llm_reply.lower()
        if "高风险" in llm_reply or "high" in reply_lower[:200]:
            risk_level = RiskLevel.HIGH
            legal_blocked = True
        elif "中风险" in llm_reply or "medium" in reply_lower[:200]:
            risk_level = RiskLevel.MEDIUM
            legal_blocked = False
        else:
            risk_level = RiskLevel.LOW
            legal_blocked = False
        legal_issues = [{"law": "LLM 分析", "issue": llm_reply[:500], "suggestion": "详见 LLM 输出"}]
    else:
        legal_issues = []
        for r in results[:3]:
            meta = r.get("metadata", {})
            legal_issues.append({
                "law": meta.get("source", "未知法条"),
                "issue": r.get("text", "")[:100],
                "suggestion": "请参考法条具体内容",
            })
        if not legal_issues:
            legal_issues = [{
                "law": "知识库覆盖不足",
                "issue": "未检索到高相关度法规" if assessment.should_degrade else "未发现明显违规",
                "suggestion": "建议人工复核" if assessment.should_degrade else "正常放行",
            }]
        risk_level = RiskLevel.HIGH if should_block else (
            RiskLevel.MEDIUM if results else RiskLevel.LOW
        )
        legal_blocked = should_block

    logger.info("[Legal Agent-RAG] 风险等级: %s, 阻断: %s", risk_level.value, legal_blocked)
    logger.info("[Legal Agent-RAG] 节点完成")
    logger.info("=" * 60)

    return {
        "legal_risk_level": risk_level.value,
        "legal_issues": legal_issues,
        "legal_blocked": legal_blocked,
        "audit_snapshots": [_make_snapshot("legal_agent_rag")],
        "current_node": "legal_agent",
    }


def contract_agent_rag(state: SpecMindState) -> dict:
    """Contract Agent RAG 增强版 - 检索合同模板 + 条款比对。"""
    logger.info("=" * 60)
    logger.info("[Contract Agent-RAG] 节点启动 - 合同条款比对（RAG 增强）")

    prd = state.get("prd", {})
    # 提取 PRD 关键字段，避免 str(prd) 引入 Python dict 语法字符污染 FTS5 查询
    prd_text = _extract_contract_query_text(prd)
    logger.info("[Contract Agent-RAG] 输入: prd 模块数=%d, 提取文本长度=%d", len(prd), len(prd_text))

    # 1. Query 改写
    rewritten = rewrite_for_contract(prd_text)
    logger.info("[Contract Agent-RAG] Query 改写完成: %s", rewritten[:60])

    # 2. 检索合同模板库
    try:
        retrieval = get_retriever().retrieve(rewritten, AssetCategory.CONTRACT_TEMPLATE, top_k=5)
        results = retrieval["results"]
        logger.info("[Contract Agent-RAG] 模板检索: %d 条, 平均相似度=%.3f",
                    len(results), retrieval["avg_similarity"])
    except Exception as e:
        logger.warning("[Contract Agent-RAG] 检索失败: %s", e)
        results = []
        retrieval = {"avg_similarity": 0.0, "low_confidence": True}

    # 3. 置信度评估
    assessment = assess_confidence(results)
    degrade_msg = get_degrade_message("contract_agent", assessment)
    if degrade_msg:
        logger.warning("[Contract Agent-RAG] %s", degrade_msg)

    # 4. 构建 Prompt + 调用 LLM
    prompt = build_contract_prompt(prd_text, "合同草案内容", results, assessment.should_degrade)
    logger.info("[Contract Agent-RAG] Prompt 构建完成, 长度=%d", len(prompt))

    llm_reply = ""
    try:
        from agents.llm_client import invoke_llm
        llm_reply = invoke_llm("contract", prompt)
        logger.info("[Contract Agent-RAG] LLM 返回 %d 字符", len(llm_reply))
    except Exception as e:
        logger.error("[Contract Agent-RAG] LLM 调用失败，回退到 mock: %s", e)

    # 5. 输出（优先 LLM 结果，失败则 mock）
    if llm_reply:
        contract_conflicts = [{
            "prd_clause": "见 PRD",
            "contract_clause": "见合同",
            "conflict": llm_reply[:500],
            "risk": "medium",
        }]
    else:
        contract_conflicts = []
        for r in results[:3]:
            meta = r.get("metadata", {})
            contract_conflicts.append({
                "prd_clause": "PRD 标准条款",
                "contract_clause": meta.get("source", "合同条款"),
                "conflict": r.get("text", "")[:100],
                "risk": "high" if assessment.confidence_level == "high" else "medium",
            })
        if not contract_conflicts:
            contract_conflicts = [{
                "prd_clause": "无标准参考",
                "contract_clause": "无标准参考",
                "conflict": "未检索到标准合同模板，建议人工核对",
                "risk": "medium",
            }]

    logger.info("[Contract Agent-RAG] 冲突识别: %d 项", len(contract_conflicts))
    logger.info("[Contract Agent-RAG] 节点完成")
    logger.info("=" * 60)

    return {
        "contract_conflicts": contract_conflicts,
        "audit_snapshots": [_make_snapshot("contract_agent_rag")],
    }

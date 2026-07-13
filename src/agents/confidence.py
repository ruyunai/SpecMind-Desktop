"""置信度评估 + 降级策略。

修复 RAG 审查问题 #5：无置信度评估，低质量检索结果无降级策略。
检索后评估平均相似度，低于阈值时触发降级：
- Legal Agent：输出「知识库覆盖不足，建议人工复核」
- Contract Agent：输出「未检索到标准模板，比对结果仅供参考」
- 不强行给结论，避免幻觉
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from core.logger import setup_logger

logger = setup_logger("specmind.agents")


@dataclass
class ConfidenceAssessment:
    """置信度评估结果。"""
    avg_similarity: float          # 平均相似度
    max_similarity: float          # 最大相似度
    result_count: int              # 结果数
    confidence_level: str          # high/medium/low/empty
    should_degrade: bool           # 是否触发降级
    degrade_reason: str            # 降级原因（空字符串表示不降级）


# 置信度阈值
THRESHOLD_HIGH = 0.75      # ≥0.75 高置信度
THRESHOLD_MEDIUM = 0.6     # 0.6-0.75 中置信度
THRESHOLD_LOW = 0.4        # 0.4-0.6 低置信度（触发降级）
# <0.4 或无结果 → 空置信度（强降级）


def assess_confidence(retrieved_results: List[Dict]) -> ConfidenceAssessment:
    """评估检索结果置信度。

    根据平均相似度和最大相似度判断：
    - high：avg≥0.75，正常使用
    - medium：0.6≤avg<0.75，正常使用但提示
    - low：0.4≤avg<0.6，触发降级（提示人工复核）
    - empty：avg<0.4 或无结果，强降级（不输出结论）

    Args:
        retrieved_results: 检索结果列表

    Returns:
        ConfidenceAssessment 置信度评估结果
    """
    if not retrieved_results:
        logger.warning("检索结果为空，触发强降级")
        return ConfidenceAssessment(
            avg_similarity=0.0,
            max_similarity=0.0,
            result_count=0,
            confidence_level="empty",
            should_degrade=True,
            degrade_reason="未检索到任何相关结果",
        )

    sims = [r.get("similarity", 0.0) for r in retrieved_results if r.get("similarity") is not None]
    if not sims:
        return ConfidenceAssessment(
            avg_similarity=0.0,
            max_similarity=0.0,
            result_count=len(retrieved_results),
            confidence_level="empty",
            should_degrade=True,
            degrade_reason="检索结果无相似度信息",
        )

    avg_sim = sum(sims) / len(sims)
    max_sim = max(sims)

    if avg_sim >= THRESHOLD_HIGH:
        level = "high"
        degrade = False
        reason = ""
    elif avg_sim >= THRESHOLD_MEDIUM:
        level = "medium"
        degrade = False
        reason = ""
    elif avg_sim >= THRESHOLD_LOW:
        level = "low"
        degrade = True
        reason = f"平均相似度 {avg_sim:.2f} 低于阈值 {THRESHOLD_MEDIUM}，知识库覆盖不足"
    else:
        level = "empty"
        degrade = True
        reason = f"平均相似度 {avg_sim:.2f} 极低，检索结果不可靠"

    logger.info(
        "置信度评估: avg=%.3f, max=%.3f, level=%s, degrade=%s",
        avg_sim, max_sim, level, degrade,
    )

    return ConfidenceAssessment(
        avg_similarity=avg_sim,
        max_similarity=max_sim,
        result_count=len(retrieved_results),
        confidence_level=level,
        should_degrade=degrade,
        degrade_reason=reason,
    )


def get_degrade_message(agent_name: str, assessment: ConfidenceAssessment) -> str:
    """获取降级提示消息。

    Args:
        agent_name: Agent 名称
        assessment: 置信度评估

    Returns:
        降级提示消息（空字符串表示不降级）
    """
    if not assessment.should_degrade:
        return ""

    messages = {
        "legal_agent": (
            f"⚠ 知识库覆盖不足（{assessment.degrade_reason}），"
            "Legal 输出仅供参考，建议人工复核合规风险。"
            "⚠ 本节点为辅助预检工具，输出不构成正式法律意见。"
        ),
        "contract_agent": (
            f"⚠ 合同模板库覆盖不足（{assessment.degrade_reason}），"
            "比对结果仅供参考，建议人工核对条款。"
        ),
        "sar_agent": (
            f"⚠ 标准能力库覆盖不足（{assessment.degrade_reason}），"
            "需求清洗仅做文本处理，未对齐企业标准。"
        ),
    }

    return messages.get(agent_name, f"⚠ 检索置信度低：{assessment.degrade_reason}")


def should_block_workflow(agent_name: str, assessment: ConfidenceAssessment) -> bool:
    """判断是否应阻断工作流（强降级场景）。

    仅 Legal Agent 在 empty 级别时阻断（合规风险不可忽视）。
    其他 Agent 降级但继续执行。

    Args:
        agent_name: Agent 名称
        assessment: 置信度评估

    Returns:
        True 表示应阻断
    """
    if agent_name == "legal_agent" and assessment.confidence_level == "empty":
        logger.warning("Legal Agent 检索结果为空，建议阻断工作流")
        return True
    return False

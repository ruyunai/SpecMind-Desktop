"""Prompt 共用辅助函数 - 知识库与 LLM 知识融合策略。

融合原则（工程化核心）：
1. 知识库命中明确内容（高/中置信度）-> 以知识库为基准，LLM 知识补充验证
2. 知识库命中但低置信度 -> LLM 知识为主，知识库作参考，标注降级提示
3. 知识库未命中 -> LLM 纯用自身知识，明确标注未经知识库验证

目标：让大模型知识与企业知识库完美融合，而非此消彼长。
"""
from typing import List, Dict


def format_retrieved_context(results: List[Dict]) -> str:
    """格式化检索结果为 Prompt 上下文（含来源标注）。

    Args:
        results: 检索结果列表

    Returns:
        格式化的上下文文本
    """
    if not results:
        return "（无检索结果）"

    lines = []
    for i, r in enumerate(results, 1):
        text = r.get("text", "")[:500]
        meta = r.get("metadata", {})
        source = meta.get("source", "未知来源")
        article = meta.get("article_no", meta.get("clause_no", meta.get("module", "")))
        source_tag = f"【来源：{source}】" if source != "未知来源" else ""
        article_tag = f"【{article}】" if article else ""
        lines.append(f"[{i}]{source_tag}{article_tag}\n{text}")

    return "\n\n".join(lines)


def build_kb_fusion_hint(
    retrieved_results: List[Dict],
    low_confidence: bool,
    kb_name: str,
) -> str:
    """构建知识库与 LLM 知识的融合提示。

    三档融合策略：
    - 高/中置信度：知识库为基准，LLM 补充
    - 低置信度：LLM 为主，知识库参考，降级提示
    - 空结果：LLM 纯用自身知识

    Args:
        retrieved_results: 检索结果
        low_confidence: 是否低置信度
        kb_name: 知识库名称（如「企业法规库」）

    Returns:
        融合提示文本
    """
    context = format_retrieved_context(retrieved_results)

    if not retrieved_results:
        return (
            f"【{kb_name}状态】\n"
            f"{kb_name}未检索到相关内容。请你以自身的专业知识为基准完成分析，"
            f"不要因检索结果为空而降低分析质量。\n"
            f"引用溯源要求：输出中标注「来源：LLM 知识（未经企业知识库验证）」。"
        )

    if low_confidence:
        return (
            f"【{kb_name}检索结果 - 低置信度】\n"
            f"{kb_name}检索到以下内容，但相关度较低，可信度有限：\n"
            f"{context}\n\n"
            f"融合策略（低置信度 — 仍以知识库为基准）：\n"
            f"1. 仍以知识库检索结果为主要依据（优先级高于你的自身知识）\n"
            f"2. 结合你的专业知识补充验证知识库内容的完整性与准确性\n"
            f"3. 知识库未覆盖的维度，用你的知识补充\n"
            f"4. 引用知识库时标注「来源：{kb_name}（低置信度）」，\n"
            f"   用你的知识补充时标注「来源：LLM 知识」\n"
            f"5. 输出末尾标注：⚠ 低置信度检索，建议人工复核"
        )

    return (
        f"【{kb_name}检索结果 - 命中明确内容】\n"
        f"{kb_name}检索到以下高相关度内容，以此为基准：\n"
        f"{context}\n\n"
        f"融合策略（知识库为基准）：\n"
        f"1. 以知识库检索结果为基准（事实依据）\n"
        f"2. 你的专业知识用于补充分析、识别风险、给出建议\n"
        f"3. 引用知识库时标注「来源：{kb_name}」\n"
        f"4. 知识库未覆盖的维度，用你的知识补充并标注「来源：LLM 知识」"
    )

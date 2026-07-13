"""结构化分块器 - 按文档类型智能分块，保留语义完整性。

修复 RAG 审查问题 #1：分块方式匹配文档类型。
- 法规：按法条分块（第X条为单位，保留编号+全文）
- 合同：按条款分块（条款编号+上下文段落）
- PRD：按模块分块（8 模块各为一块）
- 通用文本：递归分块（800 字 + 15% overlap）
"""
import re
from typing import List, Optional
from dataclasses import dataclass

from core.logger import setup_logger

logger = setup_logger("specmind.parsers")


@dataclass
class Chunk:
    """分块结果。"""
    text: str                    # 块文本
    chunk_type: str              # 块类型（regulation_article/contract_clause/prd_module/generic）
    metadata: dict               # 块元数据（法条编号/条款编号/模块名等）


def chunk_document(text: str, doc_type: str = "generic") -> List[Chunk]:
    """按文档类型智能分块。

    Args:
        text: 文档纯文本
        doc_type: 文档类型（regulation/contract/prd/generic）

    Returns:
        分块列表
    """
    if not text or not text.strip():
        return []

    logger.info("分块开始: 类型=%s, 文本长度=%d 字符", doc_type, len(text))

    if doc_type == "regulation":
        chunks = _chunk_regulation(text)
    elif doc_type == "contract":
        chunks = _chunk_contract(text)
    elif doc_type == "prd":
        chunks = _chunk_prd(text)
    else:
        chunks = _chunk_generic(text)

    logger.info("分块完成: %d 块", len(chunks))
    return chunks


def _chunk_regulation(text: str) -> List[Chunk]:
    """法规分块：按法条（第X条）为单位分块。

    保留法条编号 + 全文，避免条文被截断。
    """
    # 匹配「第X条」「第X章」等结构
    pattern = re.compile(r"第[一二三四五六七八九十百千零0-9]+条")
    splits = pattern.split(text)

    chunks: List[Chunk] = []
    # 第一个 split 通常是标题/总则，单独成块
    if splits[0].strip():
        chunks.append(Chunk(
            text=splits[0].strip(),
            chunk_type="regulation_preamble",
            metadata={"section": "总则"},
        ))

    # 后续 splits 对应各法条
    matches = pattern.findall(text)
    for i, match in enumerate(matches):
        content = splits[i + 1].strip() if i + 1 < len(splits) else ""
        if content:
            chunks.append(Chunk(
                text=f"{match} {content}",
                chunk_type="regulation_article",
                metadata={"article_no": match},
            ))

    return chunks if chunks else _chunk_generic(text)


def _chunk_contract(text: str) -> List[Chunk]:
    """合同分块：按条款编号分块。

    匹配「第X条」「X.」「（X）」等条款格式。
    """
    # 匹配多种条款格式
    pattern = re.compile(r"(?:第[一二三四五六七八九十0-9]+条|^\d+[\.\、]|^[（\(]\d+[）\)])", re.MULTILINE)
    splits = pattern.split(text)

    chunks: List[Chunk] = []
    if splits[0].strip():
        chunks.append(Chunk(
            text=splits[0].strip(),
            chunk_type="contract_header",
            metadata={"section": "合同头部"},
        ))

    matches = pattern.findall(text)
    for i, match in enumerate(matches):
        content = splits[i + 1].strip() if i + 1 < len(splits) else ""
        if content:
            chunks.append(Chunk(
                text=f"{match} {content}",
                chunk_type="contract_clause",
                metadata={"clause_no": match.strip()},
            ))

    return chunks if chunks else _chunk_generic(text)


def _chunk_prd(text: str) -> List[Chunk]:
    """PRD 分块：按 8 模块分块。

    匹配模块标题（背景目标/用户故事/功能列表等）。
    """
    module_names = [
        "背景目标", "用户故事", "功能列表", "In_Out范围", "In/Out范围",
        "验收标准", "非功能需求", "埋点要求", "风险章节",
    ]
    chunks: List[Chunk] = []
    remaining = text

    for module in module_names:
        # 查找模块标题位置
        idx = remaining.find(module)
        if idx >= 0:
            # 查找下一个模块标题
            next_idx = -1
            for next_module in module_names:
                if next_module == module:
                    continue
                ni = remaining.find(next_module, idx + len(module))
                if ni > 0 and (next_idx < 0 or ni < next_idx):
                    next_idx = ni

            content = remaining[idx:next_idx] if next_idx > 0 else remaining[idx:]
            content = content.strip()
            if content:
                chunks.append(Chunk(
                    text=content,
                    chunk_type="prd_module",
                    metadata={"module": module},
                ))

    return chunks if chunks else _chunk_generic(text)


def _chunk_generic(text: str, chunk_size: int = 800, overlap: int = 120) -> List[Chunk]:
    """通用递归分块：固定长度 + overlap。

    适用于无结构文本，chunk_size=800（中文通用），overlap=15%。

    Args:
        text: 文本
        chunk_size: 块大小（默认 800 字符）
        overlap: 重叠区域（默认 120 字符，约 15%）
    """
    chunks: List[Chunk] = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(Chunk(
                text=chunk_text,
                chunk_type="generic",
                metadata={"chunk_idx": chunk_idx, "start": start, "end": end},
            ))
            chunk_idx += 1
        start = end - overlap if end - overlap > start else end

    return chunks

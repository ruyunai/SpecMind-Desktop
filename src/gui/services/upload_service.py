"""知识库上传管线 — 解析 → 分块 → 嵌入 → 入库。

企业用户上传自有文档（.docx/.pdf/.txt/.json），自动解析为纯文本，
按文档类型智能分块，向量化为 ChromaDB 索引，供 Agent RAG 检索使用。

用法：
  from gui.services.upload_service import ingest_document
  result = ingest_document(file_path, category, doc_name)

返回 IngestResult(doc_name, total_chunks, added, skipped, errors)。
"""
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
from typing import Optional

from parsers.doc_parser import parse_document
from parsers.chunker import chunk_document, Chunk
from storage.chroma_store import ChromaStore
from storage.schema import AssetMeta, AssetCategory, make_meta
from core.logger import setup_logger

logger = setup_logger("specmind.upload")


# ---- 分类映射 ----
# 用户选的 GUI 分类 → chunk 分块策略 + AssetCategory
CATEGORY_MAP = {
    "regulation":  {"chunk_type": "regulation", "category": AssetCategory.REGULATION},
    "contract":    {"chunk_type": "contract",    "category": AssetCategory.CONTRACT_TEMPLATE},
    "prd":         {"chunk_type": "prd",         "category": AssetCategory.PRD_HISTORY},
    "feature":     {"chunk_type": "generic",     "category": AssetCategory.STANDARD_FEATURE},
    "generic":     {"chunk_type": "generic",     "category": AssetCategory.STANDARD_FEATURE},
}


@dataclass
class IngestResult:
    """上传结果。"""
    doc_name: str = ""
    total_chunks: int = 0          # 分块总数
    added: int = 0                 # 成功入库数
    skipped: int = 0               # 重复跳过数
    errors: list = field(default_factory=list)


def ingest_document(
    file_path: str,
    category: str,
    doc_name: Optional[str] = None,
) -> IngestResult:
    """上传文档到知识库。

    Args:
        file_path: 文档绝对路径
        category:  用户选择的分类（regulation/contract/prd/feature/generic）
        doc_name:  文档名称（用于元数据 source 字段），默认取文件名

    Returns:
        IngestResult 上传结果摘要
    """
    mapper = CATEGORY_MAP.get(category, CATEGORY_MAP["generic"])
    chunk_type = mapper["chunk_type"]
    asset_category = mapper["category"]

    if doc_name is None:
        doc_name = Path(file_path).name

    logger.info("=" * 60)
    logger.info("[Upload] 开始: %s → %s (分类=%s)", doc_name, category, asset_category.value)

    try:
        # 1. 解析
        text = parse_document(file_path)
        if not text or not text.strip():
            raise ValueError(f"文档解析后为空: {file_path}")
        logger.info("[Upload] 解析完成: %d 字符", len(text))

        # 2. 分块
        chunks = chunk_document(text, chunk_type)
        logger.info("[Upload] 分块完成: %d 块", len(chunks))

        # 3. 构建 AssetMeta
        texts = []
        metas = []
        for chunk in chunks:
            texts.append(chunk.text)
            meta = _build_meta(doc_name, chunk, category, asset_category)
            metas.append(meta)

        # 4. 入库（hash 去重）
        store = ChromaStore()
        added = store.add_documents(texts, metas, asset_category)
        skipped = len(texts) - added

        logger.info("[Upload] 入库完成: 新增=%d, 跳过=%d (重复)", added, skipped)
        logger.info("=" * 60)

        return IngestResult(
            doc_name=doc_name,
            total_chunks=len(texts),
            added=added,
            skipped=skipped,
        )

    except Exception as e:
        logger.error("[Upload] 失败: %s", e)
        return IngestResult(
            doc_name=doc_name or Path(file_path).name,
            total_chunks=0,
            added=0,
            skipped=0,
            errors=[str(e)],
        )


def _build_meta(doc_name: str, chunk: Chunk, category: str, asset_category: AssetCategory) -> AssetMeta:
    """从 chunk 元数据构建 AssetMeta。

    补全 source/version/effective_date/category 等必填字段，
    避免 ChromaDB metadata 缺失报错。
    """
    meta = make_meta(source=doc_name, category=asset_category)

    # 补充分类信息
    meta["category"] = category

    # 传递分块器产出的结构化元数据
    if chunk.metadata:
        for key, value in chunk.metadata.items():
            if key not in meta:
                meta[key] = value

    # 默认日期/版本（如果分块器没提供）
    if not meta.get("version"):
        meta["version"] = date.today().isoformat()
    if not meta.get("effective_date"):
        meta["effective_date"] = date.today().isoformat()

    return meta


def delete_documents_by_source(source: str, category: str) -> int:
    """按来源名称删除文档（用于资产管理）。

    Args:
        source: 文档 name/source 字段
        category: 分类

    Returns:
        删除的文档数量
    """
    mapper = CATEGORY_MAP.get(category, CATEGORY_MAP["generic"])
    asset_category = mapper["category"]
    store = ChromaStore()
    return store.delete_by_source(source, asset_category)

"""文档解析器 - 统一 Word/PDF/文本/JSON 解析接口。

修复 RAG 审查问题 #1 前置依赖：统一文档解析为纯文本，
供分块器使用。支持 .docx/.pdf/.txt/.json 四种格式。
"""
import json
from pathlib import Path
from typing import Optional

from core.logger import setup_logger

logger = setup_logger("specmind.parsers")


def parse_document(file_path: str) -> str:
    """解析文档为纯文本。

    根据扩展名自动选择解析器：
    - .docx → python-docx 提取段落
    - .pdf → PyPDF2 提取页面文本
    - .txt → 直接读取
    - .json → 格式化为可读文本

    Args:
        file_path: 文档绝对路径

    Returns:
        解析后的纯文本内容

    Raises:
        ValueError: 不支持的文件格式
        FileNotFoundError: 文件不存在
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()
    logger.info("解析文档: %s (格式: %s)", path.name, suffix)

    if suffix == ".docx":
        return _parse_docx(path)
    elif suffix == ".pdf":
        return _parse_pdf(path)
    elif suffix == ".txt":
        return _parse_txt(path)
    elif suffix == ".json":
        return _parse_json(path)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}（仅支持 .docx/.pdf/.txt/.json）")


def _parse_docx(path: Path) -> str:
    """解析 Word 文档，提取所有段落文本。"""
    from docx import Document
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    logger.info("Word 解析完成: %d 段落, %d 字符", len(paragraphs), len(text))
    return text


def _parse_pdf(path: Path) -> str:
    """解析 PDF 文档，提取所有页面文本。"""
    from PyPDF2 import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    text = "\n\n".join(pages)
    logger.info("PDF 解析完成: %d 页, %d 字符", len(reader.pages), len(text))
    return text


def _parse_txt(path: Path) -> str:
    """解析纯文本文件。"""
    text = path.read_text(encoding="utf-8")
    logger.info("TXT 解析完成: %d 字符", len(text))
    return text


def _parse_json(path: Path) -> str:
    """解析 JSON 文件，格式化为可读文本。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, ensure_ascii=False, indent=2)
    logger.info("JSON 解析完成: %d 字符", len(text))
    return text


def parse_raw_input(raw: str) -> str:
    """解析用户输入的原始需求文本。

    用户输入可能是纯文本或 JSON 字符串，统一处理。

    Args:
        raw: 原始输入字符串

    Returns:
        解析后的纯文本
    """
    raw = raw.strip()
    if not raw:
        return ""
    # 尝试 JSON 解析
    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    return raw

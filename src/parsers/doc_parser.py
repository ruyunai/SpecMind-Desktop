"""文档解析器 - 统一 Word/PDF/文本/JSON 解析接口。

支持 .docx/.pdf/.txt/.json 四种格式。
- .docx → python-docx 按顺序提取段落 + 表格（表格转 Markdown）
- .pdf  → pdfplumber 提取文本 + 表格（表格转 Markdown）
- .txt  → 直接读取
- .json → 格式化为可读文本
"""
import json
from pathlib import Path
from typing import Optional

from core.logger import setup_logger

logger = setup_logger("specmind.parsers")


def parse_document(file_path: str) -> str:
    """解析文档为纯文本。

    Args:
        file_path: 文档绝对路径

    Returns:
        解析后的纯文本内容（表格转为 Markdown 格式）

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


def _table_rows_to_markdown(rows: list) -> str:
    """将表格行列表转为 Markdown 表格文本。

    Args:
        rows: 二维列表，每个子列表是一行的单元格文本

    Returns:
        Markdown 格式表格字符串，空表格返回空字符串
    """
    if not rows:
        return ""
    lines = []
    for i, row in enumerate(rows):
        cells = [str(c).strip().replace("\n", " ") if c else "" for c in row]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(lines)


def _parse_docx(path: Path) -> str:
    """解析 Word 文档，按文档顺序提取段落和表格。

    使用 lxml 遍历 body 子元素，保持段落和表格的原始顺序。
    表格转为 Markdown 格式，避免内容丢失。
    """
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(str(path))
    parts = []
    table_count = 0

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            text = p.text.strip()
            if text:
                parts.append(text)
        elif child.tag == qn("w:tbl"):
            tbl = Table(child, doc)
            rows = [[cell.text for cell in row.cells] for row in tbl.rows]
            md = _table_rows_to_markdown(rows)
            if md:
                parts.append(md)
                table_count += 1

    text = "\n\n".join(parts)
    logger.info("Word 解析完成: %d 段落, %d 表格, %d 字符",
                len(parts) - table_count, table_count, len(text))
    return text


def _parse_pdf(path: Path) -> str:
    """解析 PDF 文档，提取每页文本和表格。

    使用 pdfplumber 提取文本 + 表格，表格转 Markdown 格式。
    比 PyPDF2 更准确地还原表格和复杂布局。
    """
    import pdfplumber

    parts = []
    table_count = 0
    page_count = 0

    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            # 提取页面文本
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
            # 提取页面表格
            tables = page.extract_tables() or []
            for table in tables:
                md = _table_rows_to_markdown(table)
                if md:
                    parts.append(md)
                    table_count += 1

    text = "\n\n".join(parts)
    logger.info("PDF 解析完成: %d 页, %d 表格, %d 字符",
                page_count, table_count, len(text))
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
    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    return raw

"""资产元数据 schema - 统一资产库元数据标注规范。

修复 RAG 审查问题 #6：资产库无元数据标注规范。
每条资产标注 source/version/effective_date/category/expired，
支持过期检查与版本管理。
"""
from typing import TypedDict, Optional
from datetime import date
from enum import Enum


class AssetCategory(str, Enum):
    """资产类别。"""
    REGULATION = "regulation"      # 法规库
    CONTRACT_TEMPLATE = "contract"  # 合同模板
    PRD_HISTORY = "prd"            # 历史 PRD
    COST_MODEL = "cost"            # 成本模型
    STANDARD_FEATURE = "feature"   # 标准功能清单


class AssetMeta(TypedDict, total=False):
    """资产元数据 schema（强制标注）。

    每条入库资产必须包含以下字段，支持过期检查与版本管理。
    """
    source: str                    # 来源（如「个人信息保护法」「合同模板v2」）
    version: str                   # 版本号（如「2024修订版」「v2.1」）
    effective_date: str            # 生效日期 ISO 格式（如「2024-01-01」）
    expired: bool                  # 是否已过期（默认 False）
    category: str                  # 资产类别（AssetCategory 枚举值）
    doc_hash: str                  # 内容 hash（用于去重，避免重复 embedding）
    extra: dict                    # 扩展字段（法条编号/条款编号/模块名等）


def is_expired(meta: AssetMeta, today: Optional[date] = None) -> bool:
    """检查资产是否已过期。

    Args:
        meta: 资产元数据
        today: 当前日期，默认取系统日期

    Returns:
        True 表示已过期需更新
    """
    if meta.get("expired", False):
        return True
    today = today or date.today()
    eff_str = meta.get("effective_date", "")
    if not eff_str:
        return False
    try:
        eff_date = date.fromisoformat(eff_str)
        # 超过 2 年视为可能过期（法规/合同通常需要定期复核）
        days_old = (today - eff_date).days
        return days_old > 730
    except ValueError:
        return False


def make_meta(
    source: str,
    category: AssetCategory,
    version: str = "1.0",
    effective_date: str = "",
    doc_hash: str = "",
    extra: Optional[dict] = None,
) -> AssetMeta:
    """便捷构造元数据。"""
    return AssetMeta(
        source=source,
        version=version,
        effective_date=effective_date or date.today().isoformat(),
        expired=False,
        category=category.value,
        doc_hash=doc_hash,
        extra=extra or {},
    )

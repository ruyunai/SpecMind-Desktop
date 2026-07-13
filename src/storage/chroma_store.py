"""ChromaDB 封装 - 向量资产库，含 hash 去重避免重复 embedding。

修复 RAG 审查问题 #8：无 Embedding 缓存，相同文本重复向量化。
通过 doc_hash 索引，新增文档时检查 hash 是否已存在，跳过重复 embedding。
"""
import hashlib
from typing import List, Dict, Optional
from pathlib import Path

from storage.schema import AssetMeta, AssetCategory, make_meta
from core.logger import setup_logger

logger = setup_logger("specmind.storage")


class ChromaStore:
    """ChromaDB 向量存储封装。

    按资产类别分集合（collection），支持：
    - 向量检索（语义相似）
    - hash 去重（避免重复 embedding）
    - 元数据过滤（category/source/version）
    """

    # 数据目录（兼容 PyInstaller frozen 模式 → %APPDATA%/SpecMindDesktop/data/）
    from core import get_data_dir
    _DEFAULT_PERSIST = str(get_data_dir() / "chroma")

    def __init__(self, persist_path: str = "") -> None:
        """初始化 ChromaDB 客户端。

        Args:
            persist_path: 持久化目录路径（默认使用项目根 data/chroma）
        """
        import chromadb
        if not persist_path:
            persist_path = self._DEFAULT_PERSIST
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collections: Dict[str, object] = {}
        logger.info("ChromaDB 初始化: persist=%s", persist_path)

    def _get_collection(self, category) -> object:
        """获取或创建指定类别的集合。

        Args:
            category: AssetCategory 枚举或字符串（如 "regulation"）
        """
        # 兼容字符串输入
        if isinstance(category, str):
            category = AssetCategory(category)
        name = f"specmind_{category.value}"
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("集合就绪: %s", name)
        return self._collections[name]

    @staticmethod
    def _compute_hash(text: str) -> str:
        """计算文本内容的 hash（用于去重）。"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _flatten_meta(meta: dict) -> dict:
        """平铺元数据以适配 ChromaDB 限制。

        ChromaDB metadata 仅接受 str/int/float/bool/list/None，
        嵌套 dict 与 list[dict] 不被支持。本方法将 extra 字段提到顶层，
        并将复杂值（如嵌套 dict）序列化为字符串。

        Args:
            meta: 原始元数据（可能含 extra 嵌套 dict）

        Returns:
            平铺后的元数据 dict
        """
        import json
        flat: dict = {}
        for k, v in meta.items():
            if k == "extra":
                # extra 里的字段提到顶层
                if isinstance(v, dict):
                    for ek, ev in v.items():
                        flat[ek] = ChromaStore._coerce_value(ev)
                continue
            flat[k] = ChromaStore._coerce_value(v)
        return flat

    @staticmethod
    def _coerce_value(v) -> object:
        """将复杂类型转换为 ChromaDB 兼容类型。"""
        if v is None or isinstance(v, (str, int, float, bool)):
            return v
        if isinstance(v, list):
            # 列表元素为基本类型时保留，否则序列化
            if all(isinstance(x, (str, int, float, bool)) for x in v):
                return v
            return json.dumps(v, ensure_ascii=False)
        # dict 或其他复杂类型 → JSON 字符串
        return json.dumps(v, ensure_ascii=False)

    def add_documents(
        self,
        texts: List[str],
        metas: List[AssetMeta],
        category: AssetCategory,
    ) -> int:
        """批量添加文档到向量库（含 hash 去重）。

        Args:
            texts: 文档文本列表
            metas: 元数据列表（与 texts 一一对应）
            category: 资产类别

        Returns:
            实际新增的文档数（跳过已存在的）
        """
        # 兼容字符串输入（调用方可传 "regulation" 或 AssetCategory.REGULATION）
        if isinstance(category, str):
            category = AssetCategory(category)
        collection = self._get_collection(category)
        added = 0

        for text, meta in zip(texts, metas):
            doc_hash = self._compute_hash(text)
            # 检查是否已存在（hash 去重）
            existing = collection.get(where={"doc_hash": doc_hash})
            if existing["ids"]:
                logger.debug("跳过重复文档: hash=%s", doc_hash)
                continue

            # 补全元数据（make_meta 默认 doc_hash=""，需用真实 hash 覆盖）
            if not meta.get("doc_hash"):
                meta["doc_hash"] = doc_hash
            if "category" not in meta:
                meta["category"] = category.value

            # ChromaDB 仅接受 str/int/float/bool/list/None，平铺 extra 字段
            flat_meta = self._flatten_meta(meta)
            doc_id = f"{category.value}_{doc_hash}"
            collection.add(
                ids=[doc_id],
                documents=[text],
                metadatas=[flat_meta],
            )
            added += 1
            logger.debug("新增文档: id=%s", doc_id)

        logger.info("批量添加完成: 类别=%s, 新增=%d, 跳过=%d",
                    category.value, added, len(texts) - added)
        return added

    def query(
        self,
        query_text: str,
        category: AssetCategory,
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索。

        Args:
            query_text: 查询文本
            category: 资产类别（AssetCategory 或字符串）
            top_k: 返回结果数
            where: 元数据过滤条件

        Returns:
            检索结果列表，每项含 text/metadata/distance
        """
        if isinstance(category, str):
            category = AssetCategory(category)
        collection = self._get_collection(category)
        if collection.count() == 0:
            # category 可能仍是字符串，兼容处理
            cat_name = category.value if isinstance(category, AssetCategory) else category
            logger.warning("集合为空: %s", cat_name)
            return []

        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k, collection.count()),
            where=where,
        )

        docs = []
        for i, doc in enumerate(results["documents"][0]):
            docs.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1 - results["distances"][0][i],  # cosine 距离转相似度
            })

        logger.info("向量检索: 类别=%s, 查询=%s..., 命中=%d",
                    category.value, query_text[:20], len(docs))
        return docs

    def count(self, category: AssetCategory) -> int:
        """获取集合文档数。"""
        return self._get_collection(category).count()

    def list_assets(self, category: AssetCategory, limit: int = 100) -> List[Dict]:
        """列出指定类别的全部资产（供 GUI 资产库展示）。

        Args:
            category: 资产类别
            limit: 最大返回数

        Returns:
            [{"text": ..., "metadata": {...}}, ...]
        """
        collection = self._get_collection(category)
        result = collection.get(limit=limit)
        items = []
        for doc, meta in zip(result.get("documents", []), result.get("metadatas", [])):
            items.append({
                "text": doc,
                "metadata": meta or {},
                "source": (meta or {}).get("source", "未知"),
                "version": (meta or {}).get("version", ""),
            })
        return items

    def list_expired(self, category: AssetCategory) -> List[Dict]:
        """列出已过期资产（用于提示更新）。"""
        from storage.schema import is_expired
        collection = self._get_collection(category)
        all_docs = collection.get()
        expired = []
        for meta in all_docs["metadatas"]:
            if is_expired(meta):
                expired.append(meta)
        return expired

    def delete_by_source(self, source: str, category: AssetCategory) -> int:
        """按来源名称删除文档。

        Args:
            source: 文档 source 字段值
            category: 资产类别

        Returns:
            删除的文档数量
        """
        if isinstance(category, str):
            category = AssetCategory(category)
        collection = self._get_collection(category)
        result = collection.get(where={"source": source})
        ids = result.get("ids", [])
        if ids:
            collection.delete(ids=ids)
            logger.info("删除文档: source=%s, category=%s, 删除=%d 条", source, category.value, len(ids))
        return len(ids)

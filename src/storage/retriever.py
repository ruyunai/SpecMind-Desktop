"""混合检索器 - 向量检索 + BM25 关键词检索 + Rerank 重排。

修复 RAG 审查问题 #2：纯向量检索漏关键词，无 Rerank 导致相关结果被截断。
流程：向量召回（Top 10）+ BM25 召回（Top 10）→ 合并去重 → 简易 Rerank → Top K
"""
from typing import List, Dict, Optional
from collections import defaultdict

from storage.chroma_store import ChromaStore
from storage.sqlite_store import SqliteStore
from storage.schema import AssetCategory
from core.logger import setup_logger

logger = setup_logger("specmind.storage")


class HybridRetriever:
    """混合检索器。

    融合向量检索（语义相似）+ BM25 检索（关键词匹配），
    通过 RRF（Reciprocal Rank Fusion）重排，取最终 Top-K。
    """

    # 相似度阈值（低于此值视为低质量结果）
    SIMILARITY_THRESHOLD = 0.6

    def __init__(
        self,
        chroma_store: Optional[ChromaStore] = None,
        sqlite_store: Optional[SqliteStore] = None,
    ) -> None:
        """初始化混合检索器。

        Args:
            chroma_store: ChromaDB 存储（None 时延迟初始化）
            sqlite_store: SQLite 存储（None 时延迟初始化）
        """
        self._chroma = chroma_store
        self._sqlite = sqlite_store

    def _ensure_stores(self) -> None:
        """延迟初始化存储（避免启动时加载 ChromaDB）。"""
        if self._chroma is None:
            self._chroma = ChromaStore()
        if self._sqlite is None:
            self._sqlite = SqliteStore()

    def retrieve(
        self,
        query: str,
        category: AssetCategory,
        top_k: int = 5,
        vector_top_k: int = 10,
        bm25_top_k: int = 10,
    ) -> Dict:
        """混合检索：向量 + BM25 + RRF 重排。

        Args:
            query: 查询文本
            category: 资产类别
            top_k: 最终返回结果数
            vector_top_k: 向量召回数
            bm25_top_k: BM25 召回数

        Returns:
            {
                "results": [...],          # 重排后的结果
                "avg_similarity": float,   # 平均相似度（用于置信度评估）
                "low_confidence": bool,    # 是否低置信度
            }
        """
        self._ensure_stores()

        # 1. 向量检索
        vector_results = self._chroma.query(
            query_text=query,
            category=category,
            top_k=vector_top_k,
        )
        logger.info("向量召回: %d 条", len(vector_results))

        # 2. BM25 检索
        bm25_results = self._sqlite.search_fts(
            query=query,
            category=category.value,
            top_k=bm25_top_k,
        )
        logger.info("BM25 召回: %d 条", len(bm25_results))

        # 3. RRF 融合重排
        fused = self._rrf_fuse(vector_results, bm25_results, top_k=top_k)
        logger.info("RRF 融合后: %d 条", len(fused))

        # 4. 置信度评估
        avg_sim = self._calc_avg_similarity(fused)
        low_conf = avg_sim < self.SIMILARITY_THRESHOLD if fused else True

        return {
            "results": fused,
            "avg_similarity": avg_sim,
            "low_confidence": low_conf,
        }

    def _rrf_fuse(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        top_k: int,
        k: int = 60,
    ) -> List[Dict]:
        """Reciprocal Rank Fusion 融合重排。

        RRF 公式：score = sum(1 / (k + rank_i))
        k=60 是业界常用值，平衡头部与尾部结果权重。

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果
            top_k: 返回数
            k: RRF 常数

        Returns:
            融合重排后的结果列表
        """
        scores: Dict[str, float] = defaultdict(float)
        docs: Dict[str, Dict] = {}

        # 向量结果按 similarity 降序排
        for rank, doc in enumerate(sorted(
            vector_results, key=lambda x: x.get("similarity", 0), reverse=True
        )):
            doc_hash = doc.get("metadata", {}).get("doc_hash", doc.get("text", "")[:32])
            scores[doc_hash] += 1.0 / (k + rank + 1)
            docs[doc_hash] = doc

        # BM25 结果按 bm25_score 降序排
        for rank, doc in enumerate(sorted(
            bm25_results, key=lambda x: x.get("bm25_score", 0), reverse=True
        )):
            doc_hash = doc.get("doc_hash", doc.get("text", "")[:32])
            scores[doc_hash] += 1.0 / (k + rank + 1)
            # BM25 结果可能没有向量相似度，补 0
            if doc_hash not in docs:
                docs[doc_hash] = {**doc, "similarity": 0.0}

        # 按 RRF 分数降序取 Top-K
        sorted_hashes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        fused = []
        for doc_hash, rrf_score in sorted_hashes[:top_k]:
            doc = docs[doc_hash]
            doc["rrf_score"] = rrf_score
            fused.append(doc)

        return fused

    @staticmethod
    def _calc_avg_similarity(results: List[Dict]) -> float:
        """计算平均相似度（用于置信度评估）。"""
        if not results:
            return 0.0
        sims = [r.get("similarity", 0.0) for r in results if r.get("similarity") is not None]
        return sum(sims) / len(sims) if sims else 0.0

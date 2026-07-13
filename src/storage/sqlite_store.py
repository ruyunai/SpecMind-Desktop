"""SQLite 封装 - 审计日志 + 结构化资产 + FTS5 全文检索。

修复 RAG 审查问题 #2：提供 BM25 关键词检索，与向量检索混合。
FTS5 虚拟表支持中文全文检索，配合 ChromaDB 向量检索实现混合召回。
"""
import sqlite3
import json
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

from core.logger import setup_logger

logger = setup_logger("specmind.storage")


class SqliteStore:
    """SQLite 存储封装。

    三张表：
    - audit_logs: 审计快照（LangGraph 节点 entry/exit）
    - assets: 结构化资产（成本模型/标准功能清单）
    - assets_fts: FTS5 全文检索虚拟表（BM25 关键词检索）
    """

    # 数据目录（兼容 PyInstaller frozen 模式 → %APPDATA%/SpecMindDesktop/data/）
    from core import get_data_dir
    _DEFAULT_DB = str(get_data_dir() / "specmind.db")

    def __init__(self, db_path: str = "", retention_days: int = 90) -> None:
        """初始化 SQLite 数据库。

        Args:
            db_path: 数据库文件路径（默认使用项目根 data/specmind.db）
            retention_days: 审计日志保留天数（默认 90 天，到期自动清理）
        """
        if not db_path:
            db_path = self._DEFAULT_DB
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.retention_days = retention_days
        self._last_cleanup = 0.0  # time.monotonic 时间戳，节流清理
        self._init_tables()
        logger.info("SQLite 初始化: db=%s", db_path)

    def _init_tables(self) -> None:
        """初始化表结构。

        FTS5 tokenizer 选 trigram：把任意文本按 3 字符滑窗切分，
        相比 unicode61（汉字按单字切，短语匹配失效）召回显著提升。
        迁移兼容：检测旧表若为 unicode61，自动 DROP + 重建 + 从 assets 表回填。
        """
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL DEFAULT '',
                node_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                state_snapshot TEXT,
                elapsed_ms INTEGER,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                source TEXT,
                content TEXT NOT NULL,
                metadata TEXT,
                doc_hash TEXT UNIQUE,
                created_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

        # 审计日志表迁移：补 run_id / elapsed_ms 列
        self._migrate_audit_logs()
        # 审计日志索引
        self._conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_audit_run_id ON audit_logs(run_id);
            CREATE INDEX IF NOT EXISTS idx_audit_node_name ON audit_logs(node_name);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
        """)
        self._conn.commit()

        # FTS5 虚拟表（trigram tokenizer）- 含旧表自动迁移
        self._migrate_fts_to_trigram()

    def _migrate_audit_logs(self) -> None:
        """审计日志表迁移：为旧表补 run_id 和 elapsed_ms 列。"""
        cols = {row["name"] for row in
                self._conn.execute("PRAGMA table_info(audit_logs)").fetchall()}
        if "run_id" not in cols:
            self._conn.execute("ALTER TABLE audit_logs ADD COLUMN run_id TEXT NOT NULL DEFAULT ''")
        if "elapsed_ms" not in cols:
            self._conn.execute("ALTER TABLE audit_logs ADD COLUMN elapsed_ms INTEGER")

    def _migrate_fts_to_trigram(self) -> None:
        """检测并迁移 FTS5 表到 trigram tokenizer。

        迁移条件：assets_fts 表存在且 tokenize != 'trigram'。
        迁移步骤：DROP 旧表 -> CREATE 新表 -> 从 assets 表回填所有数据。
        幂等：已是 trigram 则跳过。
        """
        row = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='assets_fts'"
        ).fetchone()

        if row is None:
            # 表不存在，首次创建
            self._create_trigram_fts()
            self._repopulate_fts_from_assets()
            logger.info("FTS5 首次创建: tokenize=trigram")
            return

        sql_text = row["sql"] or ""
        if "trigram" in sql_text:
            # 已是 trigram，无需迁移
            return

        # 检测到旧 unicode61 表，执行迁移
        logger.warning("检测到旧 FTS5 表 (unicode61)，开始迁移到 trigram...")
        self._conn.execute("DROP TABLE IF EXISTS assets_fts")
        self._conn.commit()
        self._create_trigram_fts()
        self._repopulate_fts_from_assets()
        logger.info("FTS5 迁移完成: unicode61 -> trigram, 已回填索引")

    def _create_trigram_fts(self) -> None:
        """创建 trigram tokenizer 的 FTS5 虚拟表。"""
        self._conn.execute(
            "CREATE VIRTUAL TABLE assets_fts USING fts5("
            "content, category, doc_hash UNINDEXED, tokenize='trigram'"
            ")"
        )
        self._conn.commit()

    def _repopulate_fts_from_assets(self) -> None:
        """从 assets 表回填所有数据到 FTS5 索引。

        回填时把 metadata.keywords 拼接到 content 后，
        确保关键词查询可命中（与 add_asset 行为一致）。
        """
        rows = self._conn.execute(
            "SELECT content, category, doc_hash, metadata FROM assets"
        ).fetchall()
        for r in rows:
            fts_content = r["content"]
            try:
                meta = json.loads(r["metadata"] or "{}")
                keywords = meta.get("keywords") if isinstance(meta, dict) else None
                if keywords:
                    fts_content = fts_content + " 关键词：" + " ".join(keywords)
            except (json.JSONDecodeError, TypeError):
                pass
            self._conn.execute(
                "INSERT INTO assets_fts (content, category, doc_hash) VALUES (?, ?, ?)",
                (fts_content, r["category"], r["doc_hash"] or ""),
            )
        self._conn.commit()
        logger.info("FTS5 索引回填: %d 条", len(rows))

    def add_asset(
        self,
        content: str,
        category: str,
        source: str = "",
        metadata: Optional[dict] = None,
        doc_hash: str = "",
    ) -> bool:
        """添加结构化资产（同时写入 FTS5 索引）。

        Args:
            content: 资产内容
            category: 类别
            source: 来源
            metadata: 元数据 dict
            doc_hash: 内容 hash（去重）

        Returns:
            True 表示新增成功，False 表示已存在
        """
        # hash 去重
        if doc_hash:
            existing = self._conn.execute(
                "SELECT id FROM assets WHERE doc_hash = ?", (doc_hash,)
            ).fetchone()
            if existing:
                logger.debug("跳过重复资产: hash=%s", doc_hash)
                return False

        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        now = datetime.now().isoformat()

        self._conn.execute(
            "INSERT INTO assets (category, source, content, metadata, doc_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (category, source, content, meta_str, doc_hash, now),
        )
        # FTS5 索引内容：原 content + keywords 拼接，确保关键词查询可命中
        fts_content = content
        keywords = (metadata or {}).get("keywords") if isinstance(metadata, dict) else None
        if keywords:
            fts_content = fts_content + " 关键词：" + " ".join(keywords)
        self._conn.execute(
            "INSERT INTO assets_fts (content, category, doc_hash) VALUES (?, ?, ?)",
            (fts_content, category, doc_hash),
        )
        self._conn.commit()
        logger.debug("新增资产: category=%s, hash=%s", category, doc_hash)
        return True

    def search_fts(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """FTS5 全文检索（trigram tokenizer，BM25 关键词匹配）。

        trigram tokenizer 把文本按 3 字符滑窗切分，对中文短语匹配友好。
        长查询处理：按空格切分成 tokens，每个 token 单独 MATCH 后合并去重，
        避免 trigram AND 全部 3-gram 导致 0 召回。
        短 token (<3 字符) 走 LIKE 回退。

        Args:
            query: 关键词查询（可含空格分词）
            category: 类别过滤（None 表示全部）
            top_k: 返回结果数

        Returns:
            检索结果列表，每项含 content/metadata/bm25_score
        """
        t_start = time.perf_counter()
        # 按空格切分成 tokens（trigram 对长字符串 AND 匹配几乎全失败）
        tokens = [t for t in query.split() if t.strip()]
        if not tokens:
            return []

        # 单 token 直接 MATCH
        if len(tokens) == 1:
            results = self._match_single_token(tokens[0], category, top_k)
        else:
            # 多 token：各自 MATCH 后合并去重，按累计 bm25_score 排序
            merged: Dict[str, Dict] = {}
            for token in tokens:
                hits = self._match_single_token(token, category, top_k)
                for h in hits:
                    dh = h["doc_hash"]
                    if dh in merged:
                        merged[dh]["bm25_score"] += h["bm25_score"]
                    else:
                        merged[dh] = h
            results = sorted(
                merged.values(),
                key=lambda x: x.get("bm25_score", 0),
                reverse=True,
            )[:top_k]

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        logger.info("FTS5 检索: query=%s..., tokens=%d, 命中=%d, 耗时=%.1fms",
                    query[:20], len(tokens), len(results), elapsed_ms)
        return results

    def _match_single_token(
        self,
        token: str,
        category: Optional[str],
        top_k: int,
    ) -> List[Dict]:
        """单 token 的 FTS5 MATCH 查询。

        分流策略（按 token 长度）：
        - <3 字符：trigram 不支持，走 LIKE
        - 3-5 字符：trigram MATCH（切成 1-3 个 3-gram AND，命中率高）
        - >=6 字符：按 4 字符滑窗切成多个子串，每个子串 trigram MATCH，
          OR 合并结果。避免长 token 切成过多 3-gram AND 导致 0 命中。

        Args:
            token: 单个查询 token
            category: 类别过滤
            top_k: 返回结果数

        Returns:
            检索结果列表
        """
        # 短 token 走 LIKE
        if len(token) < 3:
            return self._search_like_fallback(token, category, top_k)

        # 长 token 按 4 字符滑窗切分，每段 trigram MATCH，OR 合并
        if len(token) >= 6:
            return self._match_long_token_sliding(token, category, top_k)

        # 3-5 字符 token 走 trigram MATCH
        return self._match_trigram(token, category, top_k)

    def _match_trigram(
        self,
        token: str,
        category: Optional[str],
        top_k: int,
    ) -> List[Dict]:
        """3-5 字符 token 的 trigram MATCH 查询。"""
        try:
            sql = """
                SELECT a.content, a.metadata, a.doc_hash, a.category,
                       bm25(assets_fts) AS score
                FROM assets_fts
                JOIN assets a ON assets_fts.doc_hash = a.doc_hash
                WHERE assets_fts MATCH ?
            """
            params: list = [token]
            if category:
                sql += " AND a.category = ?"
                params.append(category)
            sql += " ORDER BY score ASC LIMIT ?"
            params.append(top_k)
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning("FTS5 MATCH 失败，回退 LIKE: token=%s, err=%s", token, e)
            return self._search_like_fallback(token, category, top_k)

        return [{
            "text": r["content"],
            "metadata": json.loads(r["metadata"] or "{}"),
            "doc_hash": r["doc_hash"],
            "category": r["category"],
            "bm25_score": -r["score"],
        } for r in rows]

    def _match_long_token_sliding(
        self,
        token: str,
        category: Optional[str],
        top_k: int,
    ) -> List[Dict]:
        """长 token 按 4 字符滑窗切分，每段 trigram MATCH，结果合并去重。

        例：「在线教育平台收集学生个人信息」(13 字) 切成：
        ['在线教育', '线教育平', '教育平台', '育平台收', '平台收集',
         '台收集学', '收集学生', '集学生个', '学生个人', '生个人信', '个人信息']
        每段 4 字符 trigram 切成 2 个 3-gram AND，命中率高。

        Args:
            token: 长查询 token（>=6 字符）
            category: 类别过滤
            top_k: 返回结果数

        Returns:
            合并去重后的检索结果，按累计 bm25_score 排序
        """
        t_start = time.perf_counter()
        window = 4
        substrings = [token[i:i + window] for i in range(len(token) - window + 1)]
        # 去重保持顺序
        seen = set()
        substrings = [s for s in substrings if not (s in seen or seen.add(s))]

        merged: Dict[str, Dict] = {}
        for sub in substrings:
            hits = self._match_trigram(sub, category, top_k)
            for h in hits:
                dh = h["doc_hash"]
                if dh in merged:
                    merged[dh]["bm25_score"] += h["bm25_score"]
                else:
                    merged[dh] = h

        results = sorted(
            merged.values(),
            key=lambda x: x.get("bm25_score", 0),
            reverse=True,
        )[:top_k]
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        logger.debug("长 token 滑窗: token_len=%d, 子串=%d, 命中=%d, 耗时=%.1fms",
                     len(token), len(substrings), len(results), elapsed_ms)
        return results

    def _search_like_fallback(
        self,
        query: str,
        category: Optional[str],
        top_k: int,
    ) -> List[Dict]:
        """短查询回退 LIKE 模糊匹配（trigram 对 <3 字符不工作）。

        Args:
            query: 短查询文本
            category: 类别过滤
            top_k: 返回结果数

        Returns:
            检索结果列表，bm25_score 固定为 0.5（无 BM25 排序信号）
        """
        sql = """
            SELECT content, metadata, doc_hash, category
            FROM assets WHERE content LIKE ?
        """
        params: list = [f"%{query}%"]

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " LIMIT ?"
        params.append(top_k)

        rows = self._conn.execute(sql, params).fetchall()
        results = [{
            "text": r["content"],
            "metadata": json.loads(r["metadata"] or "{}"),
            "doc_hash": r["doc_hash"],
            "category": r["category"],
            "bm25_score": 0.5,  # 无排序信号，固定分
        } for r in rows]

        logger.info("LIKE 回退检索: query=%s, 命中=%d", query, len(results))
        return results

    def add_audit_log(
        self,
        run_id: str,
        node_name: str,
        event_type: str,
        state_snapshot: Optional[dict] = None,
        elapsed_ms: Optional[int] = None,
    ) -> None:
        """添加审计日志。

        Args:
            run_id: 工作流运行 ID（每次执行唯一）
            node_name: 节点名
            event_type: 事件类型（entry/exit）
            state_snapshot: State 快照
            elapsed_ms: 节点耗时（ms），仅 exit 时记录
        """
        snapshot_str = json.dumps(state_snapshot or {}, ensure_ascii=False)
        self._conn.execute(
            "INSERT INTO audit_logs (run_id, node_name, event_type, "
            "state_snapshot, elapsed_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, node_name, event_type, snapshot_str, elapsed_ms,
             datetime.now().isoformat()),
        )
        self._conn.commit()

        # 机会性清理：最多每小时扫描一次过期日志
        now = time.monotonic()
        if now - self._last_cleanup > 3600:
            self._cleanup_expired_logs()
            self._last_cleanup = now

    def _cleanup_expired_logs(self) -> int:
        """清理超过 retention_days 天的过期审计日志。

        Returns:
            删除的记录数
        """
        cutoff = (datetime.now() - timedelta(days=self.retention_days)).isoformat()

        cursor = self._conn.execute(
            "DELETE FROM audit_logs WHERE timestamp < ?", (cutoff,)
        )
        self._conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("审计日志清理: 删除 %d 条超过 %d 天的记录 (cutoff=%s)",
                        deleted, self.retention_days, cutoff[:10])
        return deleted

    def cleanup_audit_logs(self, retention_days: int | None = None) -> int:
        """手动触发审计日志清理。

        Args:
            retention_days: 覆盖默认保留天数（None 则用构造函数的值）
        Returns:
            删除的记录数
        """
        if retention_days is not None:
            original = self.retention_days
            self.retention_days = retention_days
            try:
                return self._cleanup_expired_logs()
            finally:
                self.retention_days = original
        return self._cleanup_expired_logs()

    def get_audit_logs(self, node_name: Optional[str] = None) -> List[Dict]:
        """查询审计日志。"""
        if node_name:
            rows = self._conn.execute(
                "SELECT * FROM audit_logs WHERE node_name = ? ORDER BY id",
                (node_name,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM audit_logs ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run_audit_logs(self, run_id: str) -> List[Dict]:
        """按 run_id 查询单次运行的完整审计日志。"""
        rows = self._conn.execute(
            "SELECT * FROM audit_logs WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_runs(self, limit: int = 10) -> List[Dict]:
        """获取最近的 N 次运行摘要。

        Returns:
            [{run_id, node_count, first_ts, last_ts}]
        """
        rows = self._conn.execute(
            "SELECT run_id, COUNT(*) AS node_count, "
            "MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts "
            "FROM audit_logs WHERE run_id != '' "
            "GROUP BY run_id ORDER BY first_ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """关闭连接。"""
        self._conn.close()


# ---- 全局单例 ----

_store: Optional[SqliteStore] = None


def get_store() -> SqliteStore:
    """获取全局 SQLite 存储单例。"""
    global _store
    if _store is None:
        _store = SqliteStore()
    return _store

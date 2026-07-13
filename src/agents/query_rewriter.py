"""Query Rewriter - 各 Agent 专属查询改写。

修复 RAG 审查问题 #3：原始需求口语化，直接检索召回率低。
每个 Agent 调用 LLM 前先做 Query Rewriting：
- SAR：提取关键功能词
- Legal：提取合规风险词
- Contract：提取条款关键词
"""
import re
from typing import List, Optional

from core.logger import setup_logger

logger = setup_logger("specmind.agents")


# 各 Agent 专属关键词扩展词典
KEYWORD_DICTS = {
    "sar_agent": {
        "排课": ["课程管理", "排课系统", "课表"],
        "直播": ["在线直播", "视频教学", "实时课堂"],
        "作业": ["作业批改", "作业提交", "在线作业"],
        "支付": ["课程购买", "订单管理", "在线支付"],
        "数据": ["数据看板", "数据分析", "BI"],
    },
    "legal_agent": {
        "未成年人": ["K12", "学生", "儿童", "青少年"],
        "数据出境": ["境外", "海外", "跨境"],
        "人脸识别": ["生物特征", "人脸", "面部"],
        "终身免费": ["绝对化用语", "广告法"],
        "个人信息": ["用户数据", "学生信息", "隐私"],
    },
    "contract_agent": {
        "源代码": ["源码", "代码交付", "知识产权"],
        "免费维护": ["维护期", "保修", "售后服务"],
        "并发": ["并发数", "并发能力", "性能"],
        "定制": ["定制开发", "个性化", "定制功能"],
    },
}


def rewrite_query(
    raw_query: str,
    agent_name: str,
    cleaned_requirements: Optional[str] = None,
) -> str:
    """改写查询，适配 Agent 专属检索需求。

    策略：
    1. 提取关键词（去停用词）
    2. 用 Agent 专属词典扩展同义词
    3. 拼接为检索友好的查询串

    Args:
        raw_query: 原始查询文本
        agent_name: Agent 名称（sar_agent/legal_agent/contract_agent）
        cleaned_requirements: SAR 清洗后的需求（可选，用于上下文）

    Returns:
        改写后的查询字符串
    """
    if not raw_query or not raw_query.strip():
        return ""

    logger.info("[%s] Query 改写开始: %s...", agent_name, raw_query[:30])

    # 1. 提取关键词（简单分词 + 去停用词）
    keywords = _extract_keywords(raw_query)
    logger.info("[%s] 提取关键词: %s", agent_name, keywords)

    # 2. 词典扩展
    dict_ = KEYWORD_DICTS.get(agent_name, {})
    expanded: List[str] = list(keywords)
    for kw in keywords:
        if kw in dict_:
            expanded.extend(dict_[kw])

    # 3. 合并清洗后的需求（如有）
    if cleaned_requirements:
        req_keywords = _extract_keywords(cleaned_requirements)
        expanded.extend(req_keywords[:5])  # 只取前 5 个避免过长

    # 去重保序
    seen = set()
    unique = []
    for w in expanded:
        if w and w not in seen:
            seen.add(w)
            unique.append(w)

    rewritten = " ".join(unique)
    logger.info("[%s] Query 改写完成: %s", agent_name, rewritten[:60])
    return rewritten


def _extract_keywords(text: str) -> List[str]:
    """简单中文关键词提取。

    策略：
    - 按标点和空白分词
    - 过滤停用词和短词（<2 字符）
    - 保留中文/英文/数字混合词

    Args:
        text: 输入文本

    Returns:
        关键词列表
    """
    if not text:
        return []

    # 停用词
    stop_words = {
        "的", "了", "和", "是", "在", "我", "有", "要", "这", "那",
        "一个", "可以", "需要", "进行", "通过", "使用", "以及", "并且",
        "或者", "如果", "因为", "所以", "但是", "不过", "然后", "已经",
    }

    # 清洗文本：去除 Python dict/json 语法字符、引号、花括号、斜杠等可能污染 FTS5 查询的符号
    text = re.sub(r"[{\}\[\]'\"()<>/\\\r\n]+", " ", text)
    # 按标点和空白分词
    tokens = re.split(r"[，。、；：？！\s,;:?\!\.\n]+", text)

    keywords = []
    for token in tokens:
        token = token.strip()
        if not token or token in stop_words:
            continue
        if len(token) < 2:
            continue
        # 过滤纯数字
        if token.isdigit():
            continue
        keywords.append(token)

    return keywords


def rewrite_for_sar(raw_input: str) -> str:
    """SAR Agent 专属查询改写 - 提取功能关键词。"""
    return rewrite_query(raw_input, "sar_agent")


def rewrite_for_legal(cleaned_requirements: str) -> str:
    """Legal Agent 专属查询改写 - 提取合规风险词。"""
    return rewrite_query(cleaned_requirements, "legal_agent")


def rewrite_for_contract(prd_text: str) -> str:
    """Contract Agent 专属查询改写 - 提取条款关键词。"""
    return rewrite_query(prd_text, "contract_agent")

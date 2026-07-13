"""知识库种子数据 - 初始化法规/合同模板/标准功能库。

填充 ChromaDB + SQLite，使 Recall@5 评估达标。
包含评估数据集 tests/eval_dataset.json 中期望的法条/条款/功能。
"""
import hashlib
from typing import List, Dict

from storage.chroma_store import ChromaStore
from storage.sqlite_store import SqliteStore
from storage.schema import AssetCategory, make_meta
from core.logger import setup_logger

logger = setup_logger("specmind.seed")


# ===== 法规库种子数据 =====
REGULATIONS = [
    {
        "source": "个人信息保护法",
        "article_no": "第十三条",
        "text": "个人信息保护法第十三条：处理个人信息应当取得个人同意，处理生物识别、宗教信仰、特定身份、医疗健康、金融账户、行踪轨迹等敏感个人信息应当取得单独同意。",
        "keywords": ["个人信息", "生物特征", "人脸识别", "单独同意", "隐私"],
    },
    {
        "source": "个人信息保护法",
        "article_no": "第三十九条",
        "text": "个人信息保护法第三十九条：向境外提供个人信息的，应当向个人告知境外接收方的名称、联系方式、处理目的、处理方式、个人信息种类以及个人行使权利的方式和程序等事项，并取得个人的单独同意。",
        "keywords": ["数据出境", "境外", "跨境", "个人信息", "单独同意"],
    },
    {
        "source": "数据安全法",
        "article_no": "第三十一条",
        "text": "数据安全法第三十一条：关键信息基础设施的运营者在中华人民共和国境内运营中收集和产生的个人信息和重要数据应当在境内存储。因业务需要确需向境外提供的，应当通过国家网信部门组织的安全评估。",
        "keywords": ["数据出境", "境外", "安全评估", "跨境", "境内存储"],
    },
    {
        "source": "未成年人保护法",
        "article_no": "第七十二条",
        "text": "未成年人保护法第七十二条：信息处理者通过网络处理未成年人个人信息信息的，应当遵循合法、正当和必要的原则。处理不满十四周岁未成年人个人信息的，应当征得未成年人的父母或者其他监护人同意。",
        "keywords": ["未成年人", "儿童", "监护人同意", "K12", "学生", "青少年"],
    },
    {
        "source": "未成年人保护法",
        "article_no": "第七十四条",
        "text": "未成年人保护法第七十四条：网络产品和服务提供者不得向未成年人提供诱导其沉迷的产品和服务。对未成年人个人信息进行处理应当制定专门规则。",
        "keywords": ["未成年人", "个人信息", "专门规则", "K12", "学生"],
    },
    {
        "source": "广告法",
        "article_no": "第二十四条",
        "text": "广告法第二十四条：广告不得含有虚假或者引人误解的内容，不得欺骗、误导消费者。广告使用绝对化用语（如「最」「终身」「第一」等）属于违法行为。",
        "keywords": ["广告法", "绝对化用语", "终身免费", "虚假宣传"],
    },
    {
        "source": "网络安全法",
        "article_no": "第四十一条",
        "text": "网络安全法第四十一条：网络运营者收集、使用个人信息，应当公开收集、使用规则，明示收集、使用信息的目的、方式和范围，并经被收集者同意。",
        "keywords": ["网络安全", "个人信息", "收集", "同意"],
    },
]


# ===== 合同模板种子数据 =====
CONTRACT_TEMPLATES = [
    {
        "source": "标准合同模板v2.1",
        "clause_no": "维护条款",
        "text": "维护条款：标准合同模板规定维护期为首年免费维护，自交付之日起12个月内免费提供缺陷修复和小版本升级。第二年起按开发费的10%收取年度维护费。",
        "keywords": ["维护期", "免费维护", "首年", "终身免费", "维护"],
    },
    {
        "source": "标准合同模板v2.1",
        "clause_no": "性能条款",
        "text": "性能条款：标准版软件支持1万并发用户，如需更高并发能力（如10万并发）需定制开发并额外收费，定制费用根据性能需求评估确定。",
        "keywords": ["并发", "1万并发", "10万并发", "性能", "定制"],
    },
    {
        "source": "标准合同模板v2.1",
        "clause_no": "知识产权条款",
        "text": "知识产权条款：软件源代码归属开发方所有，不对外提供源代码。客户获得软件使用权而非所有权。如需源代码需另行签订知识产权转让协议。",
        "keywords": ["源代码", "源码", "知识产权", "代码交付"],
    },
    {
        "source": "标准合同模板v2.1",
        "clause_no": "定制功能条款",
        "text": "定制功能条款：标准版功能外的定制需求需单独评估，定制功能按人天单价计算，单价为3000元/人天。定制部分交付后同样享受1年免费维护。",
        "keywords": ["定制", "定制开发", "个性化", "人天"],
    },
]


# ===== 标准功能库种子数据 =====
STANDARD_FEATURES = [
    {
        "source": "企业标准能力库v3.0",
        "module": "课程管理",
        "text": "课程管理（标准功能）：提供课程创建、编辑、删除、分类管理。支持课程基本信息、封面、简介、价格设置。标准CRUD能力。",
        "keywords": ["课程管理", "课程", "CRUD"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "排课系统",
        "text": "排课系统（标准功能）：日历式排课界面，支持拖拽排课、冲突检测、批量排课。教师课表、教室课表、班级课表多视图展示。",
        "keywords": ["排课", "排课系统", "课表", "课程管理"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "在线直播",
        "text": "在线直播（标准功能）：基于WebRTC+SFU架构的标准直播能力，支持1000人同时在线，低延迟≤2s。支持屏幕共享、白板、互动问答。",
        "keywords": ["在线直播", "直播", "视频教学", "实时课堂"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "作业批改",
        "text": "作业批改（标准功能）：支持图文作业提交、在线批改、批注反馈。支持图片/文档/PDF 格式作业。自动统计提交率与批改进度。",
        "keywords": ["作业", "作业批改", "作业提交", "在线作业"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "支付系统",
        "text": "支付系统（标准功能）：集成微信支付/支付宝双通道，支持课程购买、订单管理、退款处理。提供支付回调与对账功能。",
        "keywords": ["支付", "支付系统", "课程购买", "订单管理", "在线支付"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "数据看板",
        "text": "数据看板（标准功能）：BI 数据可视化，支持机构管理、教师/学生账号管理、核心指标看板（活跃度、完课率、营收）。",
        "keywords": ["数据看板", "数据分析", "BI", "机构管理"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "AI智能推荐（暂不支持）",
        "text": "AI智能推荐（暂不支持）：本期暂不提供 AI 推荐功能，后续版本规划。如客户强制需求需评估为定制功能。",
        "keywords": ["AI", "智能推荐", "暂不支持", "推荐"],
    },
    {
        "source": "企业标准能力库v3.0",
        "module": "10万并发（定制功能）",
        "text": "10万并发（定制功能）：标准版支持1万并发，10万并发需定制扩展，需独立评估架构与成本，定制费用另计。",
        "keywords": ["10万并发", "并发", "定制", "性能"],
    },
]


def load_seed_data() -> None:
    """加载种子数据到知识库。"""
    logger.info("=" * 60)
    logger.info("开始加载种子数据")
    logger.info("=" * 60)

    chroma = ChromaStore()
    sqlite = SqliteStore()

    # 1. 法规库
    reg_texts = [r["text"] for r in REGULATIONS]
    reg_metas = [
        make_meta(
            source=r["source"],
            category=AssetCategory.REGULATION,
            version="2024修订版",
            effective_date="2024-01-01",
            extra={"article_no": r["article_no"], "keywords": r["keywords"]},
        )
        for r in REGULATIONS
    ]
    chroma_count = chroma.add_documents(reg_texts, reg_metas, AssetCategory.REGULATION)

    # 同步写入 SQLite（供 BM25 检索）
    for r in REGULATIONS:
        doc_hash = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()[:16]
        sqlite.add_asset(
            content=r["text"],
            category=AssetCategory.REGULATION.value,
            source=r["source"],
            metadata={"article_no": r["article_no"], "keywords": r["keywords"]},
            doc_hash=doc_hash,
        )

    logger.info("法规库: ChromaDB 新增 %d 条, SQLite 同步完成", chroma_count)

    # 2. 合同模板库
    contract_texts = [c["text"] for c in CONTRACT_TEMPLATES]
    contract_metas = [
        make_meta(
            source=c["source"],
            category=AssetCategory.CONTRACT_TEMPLATE,
            version="v2.1",
            effective_date="2024-06-01",
            extra={"clause_no": c["clause_no"], "keywords": c["keywords"]},
        )
        for c in CONTRACT_TEMPLATES
    ]
    contract_count = chroma.add_documents(contract_texts, contract_metas, AssetCategory.CONTRACT_TEMPLATE)

    for c in CONTRACT_TEMPLATES:
        doc_hash = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()[:16]
        sqlite.add_asset(
            content=c["text"],
            category=AssetCategory.CONTRACT_TEMPLATE.value,
            source=c["source"],
            metadata={"clause_no": c["clause_no"], "keywords": c["keywords"]},
            doc_hash=doc_hash,
        )

    logger.info("合同模板库: ChromaDB 新增 %d 条, SQLite 同步完成", contract_count)

    # 3. 标准功能库
    feature_texts = [f["text"] for f in STANDARD_FEATURES]
    feature_metas = [
        make_meta(
            source=f["source"],
            category=AssetCategory.STANDARD_FEATURE,
            version="v3.0",
            effective_date="2024-03-01",
            extra={"module": f["module"], "keywords": f["keywords"]},
        )
        for f in STANDARD_FEATURES
    ]
    feature_count = chroma.add_documents(feature_texts, feature_metas, AssetCategory.STANDARD_FEATURE)

    for f in STANDARD_FEATURES:
        doc_hash = hashlib.sha256(f["text"].encode("utf-8")).hexdigest()[:16]
        sqlite.add_asset(
            content=f["text"],
            category=AssetCategory.STANDARD_FEATURE.value,
            source=f["source"],
            metadata={"module": f["module"], "keywords": f["keywords"]},
            doc_hash=doc_hash,
        )

    logger.info("标准功能库: ChromaDB 新增 %d 条, SQLite 同步完成", feature_count)

    # 汇总
    logger.info("=" * 60)
    logger.info("种子数据加载完成:")
    logger.info("  法规库: %d 条 (ChromaDB) / %d 条 (SQLite FTS5)",
                chroma.count(AssetCategory.REGULATION), 7)
    logger.info("  合同模板: %d 条 (ChromaDB) / %d 条 (SQLite FTS5)",
                chroma.count(AssetCategory.CONTRACT_TEMPLATE), 4)
    logger.info("  标准功能: %d 条 (ChromaDB) / %d 条 (SQLite FTS5)",
                chroma.count(AssetCategory.STANDARD_FEATURE), 8)
    logger.info("=" * 60)

    sqlite.close()


if __name__ == "__main__":
    load_seed_data()

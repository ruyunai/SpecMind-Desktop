"""Mock Agent 节点 - LangGraph 节点函数（只返回更新的字段）。

LangGraph 规范：节点函数返回 dict 只包含本节点新增/更新的字段，
LangGraph 自动合并到全局 State。并行节点不能返回相同字段（除非有 reducer）。

每个节点：
- 读取 state 所需字段
- 返回 {更新字段: 值} 的部分 dict
- audit_snapshots 返回 [新快照]（列表），由 operator.add reducer 合并
"""
import time
import logging

from agents.state import SpecMindState, RiskLevel, FeatureTag
from core.logger import setup_logger

logger = setup_logger("specmind.agents")


def _make_snapshot(node_name: str) -> dict:
    """创建单条审计快照。"""
    return {"node": node_name, "timestamp": time.time()}


# ============================================================
# SAR Agent - 需求清洗
# ============================================================
def sar_agent(state: SpecMindState) -> dict:
    """SAR Agent：清洗脏需求，对齐企业标准能力，标注过度承诺。"""
    logger.info("=" * 60)
    logger.info("[SAR Agent] 节点启动 - 需求清洗")
    logger.info("[SAR Agent] 输入: raw_input 长度=%d 字符", len(state.get("raw_input", "")))

    raw = state.get("raw_input", "")
    client_name = state.get("client_info", {}).get("client_name", "未知")
    logger.info("[SAR Agent] 检测到需求来源: 微信聊天记录 + 口头承诺")
    logger.info("[SAR Agent] 提取客户信息: %s", client_name)
    logger.info("[SAR Agent] 对齐企业标准能力库...")

    cleaned_requirements = (
        "【客户】智联慧学教育科技\n"
        "【场景】在线教育平台，需为 K12 机构提供一站式教学管理\n"
        "【核心需求】\n"
        "1. 教师端：课程创建、排课、在线直播教学、作业批改\n"
        "2. 学生端：课程浏览、在线学习、作业提交、学习进度追踪\n"
        "3. 管理端：机构管理、教师/学生账号管理、数据看板\n"
        "4. 支付：课程购买、订单管理\n"
        "【交付期望】8 周内上线"
    )
    logger.info("[SAR Agent] 标准化需求生成完成, 长度=%d 字符", len(cleaned_requirements))

    overcommit_risks = [
        "销售承诺「终身免费升级」→ 企业标准仅含1年免费维护",
        "销售承诺「支持10万并发」→ 标准版上限为1万并发，需定制",
        "销售承诺「提供源代码」→ 企业政策不对外提供源码",
    ]
    logger.info("[SAR Agent] 过度承诺风险标注完成, 共 %d 项:", len(overcommit_risks))
    for i, risk in enumerate(overcommit_risks, 1):
        logger.info("[SAR Agent]   风险 %d: %s", i, risk)

    logger.info("[SAR Agent] 节点完成")
    logger.info("=" * 60)

    # 只返回本节点更新的字段
    return {
        "cleaned_requirements": cleaned_requirements,
        "overcommit_risks": overcommit_risks,
        "audit_snapshots": [_make_snapshot("sar_agent")],
        "current_node": "sar_agent",
    }


# ============================================================
# Legal Agent - 合规预检（中风险，不阻断）
# ============================================================
def legal_agent(state: SpecMindState) -> dict:
    """Legal Agent：本地法规库合规预检，输出风险等级（中风险不阻断）。"""
    logger.info("=" * 60)
    logger.info("[Legal Agent] 节点启动 - 合规预检")
    logger.info("[Legal Agent] ⚠ 本节点为辅助预检工具，输出不构成正式法律意见")
    logger.info("[Legal Agent] 输入: cleaned_requirements 长度=%d 字符",
                len(state.get("cleaned_requirements", "")))

    logger.info("[Legal Agent] 加载本地法规库...")
    logger.info("[Legal Agent] 法规库: 个人信息保护法、数据安全法、网络安全法、未成年人保护法、广告法")
    logger.info("[Legal Agent] 开始逐条匹配需求与法规...")

    legal_issues = [
        {
            "law": "《未成年人保护法》第七十四条",
            "issue": "收集未成年人个人信息需取得监护人同意",
            "suggestion": "学生注册流程增加监护人授权环节",
        },
        {
            "law": "《个人信息保护法》第十三条",
            "issue": "处理学生人脸识别（直播）需单独同意",
            "suggestion": "直播功能增加人脸授权弹窗",
        },
        {
            "law": "《广告法》第二十四条",
            "issue": "「终身免费」涉嫌违反广告法绝对化用语",
            "suggestion": "改为「首年免费维护」",
        },
    ]

    logger.info("[Legal Agent] 法规匹配完成, 命中 %d 条:", len(legal_issues))
    for i, issue in enumerate(legal_issues, 1):
        logger.info("[Legal Agent]   %d. 法条: %s", i, issue["law"])
        logger.info("[Legal Agent]      问题: %s", issue["issue"])
        logger.info("[Legal Agent]      建议: %s", issue["suggestion"])

    risk_level = RiskLevel.MEDIUM
    legal_blocked = False
    logger.info("[Legal Agent] 综合风险评级: %s", risk_level.value)
    logger.info("[Legal Agent] 当前风险=%s → 判定: 放行", risk_level.value)
    logger.info("[Legal Agent] legal_blocked = %s", legal_blocked)
    logger.info("[Legal Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "legal_risk_level": risk_level.value,
        "legal_issues": legal_issues,
        "legal_blocked": legal_blocked,
        "audit_snapshots": [_make_snapshot("legal_agent")],
        "current_node": "legal_agent",
    }


# ============================================================
# Legal Agent - 高风险场景（阻断）
# ============================================================
def legal_agent_high_risk(state: SpecMindState) -> dict:
    """Legal Agent：高风险场景（测试 Interrupt 阻断逻辑）。"""
    logger.info("=" * 60)
    logger.info("[Legal Agent] 节点启动 - 合规预检（高风险场景）")
    logger.info("[Legal Agent] ⚠ 本节点为辅助预检工具，输出不构成正式法律意见")
    logger.info("[Legal Agent] 输入: cleaned_requirements 长度=%d 字符",
                len(state.get("cleaned_requirements", "")))

    logger.info("[Legal Agent] 加载本地法规库...")
    logger.info("[Legal Agent] 开始逐条匹配需求与法规...")

    legal_issues = [
        {
            "law": "《数据安全法》第三十一条",
            "issue": "涉及未成年人数据出境，未经安全评估",
            "suggestion": "需先通过数据出境安全评估",
        },
        {
            "law": "《个人信息保护法》第三十九条",
            "issue": "向境外提供个人信息未取得单独同意",
            "suggestion": "需取得个人信息主体单独同意",
        },
        {
            "law": "《未成年人保护法》第七十二条",
            "issue": "处理未满14周岁未成年人个人信息未经监护人同意",
            "suggestion": "必须取得监护人同意，且制定专门处理规则",
        },
    ]

    logger.warning("[Legal Agent] ⚠ 检测到高风险违规! 命中 %d 条:", len(legal_issues))
    for i, issue in enumerate(legal_issues, 1):
        logger.warning("[Legal Agent]   %d. 法条: %s", i, issue["law"])
        logger.warning("[Legal Agent]      问题: %s", issue["issue"])
        logger.warning("[Legal Agent]      建议: %s", issue["suggestion"])

    risk_level = RiskLevel.HIGH
    legal_blocked = True
    logger.warning("[Legal Agent] 综合风险评级: %s", risk_level.value)
    logger.warning("[Legal Agent] 当前风险=%s → 判定: 阻断", risk_level.value)
    logger.warning("[Legal Agent] ⛔ legal_blocked = True")
    logger.warning("[Legal Agent] ⛔ Interrupt 触发! PRD 生成将被阻断!")
    logger.warning("[Legal Agent] ⛔ 需人工确认后方可继续执行")
    logger.info("[Legal Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "legal_risk_level": risk_level.value,
        "legal_issues": legal_issues,
        "legal_blocked": legal_blocked,
        "audit_snapshots": [_make_snapshot("legal_agent")],
        "current_node": "legal_agent",
    }


# ============================================================
# PM Agent - PRD 生成
# ============================================================
def pm_agent(state: SpecMindState) -> dict:
    """PM Agent：严格遵循 8 模块模板生成 PRD。"""
    logger.info("=" * 60)
    logger.info("[PM Agent] 节点启动 - PRD 生成")
    logger.info("[PM Agent] 输入: cleaned_requirements 长度=%d 字符",
                len(state.get("cleaned_requirements", "")))
    logger.info("[PM Agent] 检查 Legal 阻断状态: legal_blocked=%s",
                state.get("legal_blocked", False))

    logger.info("[PM Agent] 加载企业标准 PRD 模板 (8 模块)...")
    required_modules = ["背景目标", "用户故事", "功能列表", "In_Out范围",
                        "验收标准", "非功能需求", "埋点要求", "风险章节"]

    prd = {
        "背景目标": "为 K12 教育机构提供一站式在线教学管理平台，解决排课混乱、教学数据分散问题。",
        "用户故事": "作为教师，我希望能够创建课程并排课，以便管理教学计划；作为学生，我希望能够在线学习并提交作业，以便完成学习任务。",
        "功能列表": "1.课程管理 2.排课系统 3.在线直播 4.作业批改 5.学习进度 6.数据看板 7.支付系统 8.账号管理",
        "In_Out范围": "In: 教学管理核心流程、支付、数据看板；Out: 家校沟通、AI 推荐、多语言",
        "验收标准": "直播延迟≤2s；支持1000人同时在线；作业批改支持图片/文档；支付支持微信/支付宝",
        "非功能需求": "响应时间≤500ms；可用性99.9%；数据加密存储；支持Chrome/Edge/Safari",
        "埋点要求": "课程创建、直播参与、作业提交、支付完成 4 个核心事件埋点",
        "风险章节": "1.10万并发需定制（标准版上限1万）2.源代码不对外提供 3.首年免费维护（非终身）",
    }
    logger.info("[PM Agent] PRD 生成完成, 模块数=%d/8", len(prd))
    for module in required_modules:
        logger.info("[PM Agent]   ✓ %s", module)

    prd_features = [
        {"name": "课程管理", "tag": FeatureTag.STANDARD.value, "desc": "标准课程CRUD"},
        {"name": "排课系统", "tag": FeatureTag.STANDARD.value, "desc": "日历式排课"},
        {"name": "在线直播", "tag": FeatureTag.STANDARD.value, "desc": "标准直播能力"},
        {"name": "作业批改", "tag": FeatureTag.STANDARD.value, "desc": "支持图文批改"},
        {"name": "学习进度追踪", "tag": FeatureTag.STANDARD.value, "desc": "标准进度追踪"},
        {"name": "数据看板", "tag": FeatureTag.STANDARD.value, "desc": "标准BI看板"},
        {"name": "支付系统", "tag": FeatureTag.STANDARD.value, "desc": "微信/支付宝"},
        {"name": "10万并发", "tag": FeatureTag.CUSTOM.value, "desc": "标准版1万，需定制扩展"},
        {"name": "AI智能推荐", "tag": FeatureTag.UNSUPPORTED.value, "desc": "本期暂不支持"},
        {"name": "提供源代码", "tag": FeatureTag.UNSUPPORTED.value, "desc": "企业政策不允许"},
    ]
    tag_counts = {}
    for feat in prd_features:
        tag_counts[feat["tag"]] = tag_counts.get(feat["tag"], 0) + 1
    logger.info("[PM Agent] 功能点标注完成, 共 %d 个:", len(prd_features))
    for tag, count in tag_counts.items():
        logger.info("[PM Agent]   %s: %d 个", tag, count)

    logger.info("[PM Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "prd": prd,
        "prd_features": prd_features,
        "audit_snapshots": [_make_snapshot("pm_agent")],
        "current_node": "pm_agent",
    }


# ============================================================
# Commercial Agent - 双报价
# ============================================================
def commercial_agent(state: SpecMindState) -> dict:
    """Commercial Agent：基于功能点匹配成本模型，输出双报价。"""
    logger.info("=" * 60)
    logger.info("[Commercial Agent] 节点启动 - 双报价生成")
    logger.info("[Commercial Agent] 输入: prd_features 数量=%d",
                len(state.get("prd_features", [])))

    logger.info("[Commercial Agent] 加载成本模型...")
    logger.info("[Commercial Agent] 人力成本: 3000元/人天 | 基础设施: 5000元/月 | 运维: 3000元/月")

    quotes = {
        "标准版": {
            "功能数": 7, "人天": 120, "开发费": 360000,
            "维护费": 36000, "毛利": 144000, "毛利率": 0.40,
        },
        "裁剪版": {
            "功能数": 5, "人天": 80, "开发费": 240000,
            "维护费": 24000, "毛利": 96000, "毛利率": 0.40,
        },
    }

    logger.info("[Commercial Agent] 报价生成完成:")
    for version, quote in quotes.items():
        logger.info("[Commercial Agent]   %s: 开发费=%d元 维护费=%d元 毛利=%d元 毛利率=%.0f%%",
                    version, quote["开发费"], quote["维护费"], quote["毛利"], quote["毛利率"] * 100)

    logger.info("[Commercial Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "quotes": quotes,
        "audit_snapshots": [_make_snapshot("commercial_agent")],
    }


# ============================================================
# Contract Agent - 合同比对（重点日志）
# ============================================================
def contract_agent(state: SpecMindState) -> dict:
    """Contract Agent：对比 PRD 与合同草案，标注条款冲突。"""
    logger.info("=" * 60)
    logger.info("[Contract Agent] 节点启动 - 合同条款比对")
    logger.info("[Contract Agent] 输入: prd 模块数=%d", len(state.get("prd", {})))

    logger.info("[Contract Agent] 加载合同草案...")
    logger.info("[Contract Agent] 合同草案条款数: 12 条")
    logger.info("[Contract Agent] 开始逐条比对 PRD 与合同条款...")

    contract_conflicts = [
        {
            "prd_clause": "首年免费维护",
            "contract_clause": "终身免费维护",
            "conflict": "合同草案与 PRD 不一致，需修改合同",
            "risk": "high",
        },
        {
            "prd_clause": "标准版支持1万并发",
            "contract_clause": "支持10万并发",
            "conflict": "合同承诺超出标准能力，需定制或修改",
            "risk": "high",
        },
        {
            "prd_clause": "不提供源代码",
            "contract_clause": "交付源代码",
            "conflict": "合同要求与企业政策冲突",
            "risk": "high",
        },
    ]

    logger.info("[Contract Agent] 逐条比对结果:")
    for i, conflict in enumerate(contract_conflicts, 1):
        logger.warning("[Contract Agent]   冲突 %d [风险=%s]:", i, conflict["risk"].upper())
        logger.warning("[Contract Agent]     PRD 条款:   %s", conflict["prd_clause"])
        logger.warning("[Contract Agent]     合同条款:   %s", conflict["contract_clause"])
        logger.warning("[Contract Agent]     冲突说明:   %s", conflict["conflict"])

    high_count = sum(1 for c in contract_conflicts if c["risk"] == "high")
    logger.warning("[Contract Agent] 冲突汇总: 共 %d 项, 其中高风险 %d 项",
                   len(contract_conflicts), high_count)
    logger.info("[Contract Agent] ⚠ 高风险合同冲突需 Interrupt 人工确认后方可继续")
    logger.info("[Contract Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "contract_conflicts": contract_conflicts,
        "audit_snapshots": [_make_snapshot("contract_agent")],
    }


# ============================================================
# Review Agent - 多维评审
# ============================================================
def review_agent(state: SpecMindState) -> dict:
    """Review Agent：Tech/Design/QA 三维评审。"""
    logger.info("=" * 60)
    logger.info("[Review Agent] 节点启动 - 多维评审 (Tech/Design/QA)")
    logger.info("[Review Agent] 输入: prd 模块数=%d, prd_features 数量=%d",
                len(state.get("prd", {})), len(state.get("prd_features", [])))

    review_comments = {
        "tech": [
            "直播模块建议使用 WebRTC + SFU 架构",
            "10万并发需独立评估，建议分阶段扩容",
            "支付系统需对接第三方支付网关，预留2周联调",
        ],
        "design": [
            "学生端建议增加学习日历可视化",
            "教师排课界面交互复杂，建议简化为拖拽式",
            "数据看板需明确核心指标优先级",
        ],
        "qa": [
            "直播并发测试需覆盖1000人场景",
            "支付流程需覆盖异常订单回滚",
            "未成年人信息采集需增加合规测试用例",
        ],
    }

    logger.info("[Review Agent] 评审意见生成完成:")
    for dimension, comments in review_comments.items():
        logger.info("[Review Agent]   %s: %d 条意见", dimension.upper(), len(comments))
        for c in comments:
            logger.info("[Review Agent]     - %s", c)

    review_pass = True
    logger.info("[Review Agent] 评审结论: %s", "通过" if review_pass else "不通过")
    logger.info("[Review Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "review_comments": review_comments,
        "review_pass": review_pass,
        "audit_snapshots": [_make_snapshot("review_agent")],
    }


# ============================================================
# Planner Agent - 交付计划
# ============================================================
def planner_agent(state: SpecMindState) -> dict:
    """Planner Agent：生成配套交付计划。"""
    logger.info("=" * 60)
    logger.info("[Planner Agent] 节点启动 - 交付计划生成")
    logger.info("[Planner Agent] 输入: prd 模块数=%d", len(state.get("prd", {})))

    delivery_plan = [
        {"phase": "需求确认", "duration": "1周", "deliverable": "PRD 终稿 + 评审记录"},
        {"phase": "设计阶段", "duration": "2周", "deliverable": "UI 设计稿 + 技术方案"},
        {"phase": "开发阶段", "duration": "3周", "deliverable": "核心功能代码 + 单元测试"},
        {"phase": "联调测试", "duration": "1周", "deliverable": "集成测试报告 + Bug 修复"},
        {"phase": "上线交付", "duration": "1周", "deliverable": "生产环境部署 + 验收文档"},
    ]

    total_weeks = sum(int(p["duration"].replace("周", "")) for p in delivery_plan)
    logger.info("[Planner Agent] 交付计划生成完成, 共 %d 阶段, 总工期 %d 周:",
                len(delivery_plan), total_weeks)
    for phase in delivery_plan:
        logger.info("[Planner Agent]   %s (%s): %s",
                    phase["phase"], phase["duration"], phase["deliverable"])

    logger.info("[Planner Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "delivery_plan": delivery_plan,
        "audit_snapshots": [_make_snapshot("planner_agent")],
        "current_node": "planner_agent",
    }

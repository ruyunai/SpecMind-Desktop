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
    """PM Agent：调用 LLM 生成 PRD 和功能点标注。"""
    logger.info("=" * 60)
    logger.info("[PM Agent] 节点启动 - PRD 生成")
    logger.info("[PM Agent] 输入: cleaned_requirements 长度=%d 字符",
                len(state.get("cleaned_requirements", "")))

    cleaned = state.get("cleaned_requirements", "")
    legal_issues = state.get("legal_issues", [])
    legal_risk = state.get("legal_risk_level", "low")

    # 尝试调用 LLM
    llm_reply = ""
    try:
        from agents.prompts import build_pm_prompt
        from agents.llm_client import invoke_llm
        prompt = build_pm_prompt(cleaned, legal_issues, legal_risk)
        logger.info("[PM Agent] Prompt 构建完成, 长度=%d", len(prompt))
        llm_reply = invoke_llm("pm", prompt)
        logger.info("[PM Agent] LLM 返回 %d 字符", len(llm_reply))
    except Exception as e:
        logger.error("[PM Agent] LLM 调用失败，回退到 mock: %s", e)

    # 回退：mock PRD
    if not llm_reply:
        logger.info("[PM Agent] 加载企业标准 PRD 模板 (8 模块)...")
    required_modules = ["背景目标", "用户故事", "功能列表", "In_Out范围",
                        "验收标准", "非功能需求", "埋点要求", "风险章节"]

    if llm_reply:
        prd = {"llm_output": llm_reply}
        # 尝试从 LLM 回复中提取 JSON
        prd_features = _parse_llm_features(llm_reply)
    else:
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
        tag = feat.get("tag", FeatureTag.STANDARD.value)
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    logger.info("[PM Agent] PRD 生成完成, 功能点=%d", len(prd_features))
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


def _parse_llm_features(llm_text: str) -> list:
    """尝试从 LLM 返回文本中提取功能点列表。"""
    import json
    # 尝JSON 提取
    try:
        # 查找 JSON 数组或对象
        start = llm_text.find("[")
        end = llm_text.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(llm_text[start:end])
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, ValueError):
        pass
    # 回退：返回简单结构
    return [{"name": "LLM 输出", "tag": FeatureTag.STANDARD.value,
             "desc": llm_text[:200]}]


def _parse_llm_delivery_plan(llm_text: str) -> list:
    """从 LLM 返回文本中提取交付计划列表。

    期望 LLM 输出 JSON 数组，每项含 phase/weeks(or duration)/deliverables(or deliverable)。
    回退时构造单阶段占位结构，避免下游 key 不存在崩溃。
    """
    import json
    try:
        start = llm_text.find("[")
        end = llm_text.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(llm_text[start:end])
            if isinstance(data, list) and data:
                # 规范化 key：deliverables → deliverable，保证下游一致
                normalized = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    phase_name = item.get("phase", item.get("name", "未命名阶段"))
                    duration = item.get("weeks", item.get("duration", "0周"))
                    deliverable = item.get("deliverables", item.get("deliverable", "未指定"))
                    normalized.append({
                        "phase": phase_name,
                        "duration": duration,
                        "deliverable": deliverable,
                    })
                return normalized if normalized else []
    except (json.JSONDecodeError, ValueError):
        pass
    # 回退：将 LLM 文本作为单阶段描述（避免下游访问 None）
    return [{"phase": "LLM 输出", "duration": "0周",
             "deliverable": llm_text[:200]}]


# ============================================================
# Commercial Agent - 动态双报价（基于功能点 × 成本参数）
# ============================================================
def commercial_agent(state: SpecMindState) -> dict:
    """Commercial Agent：基于 PM 输出的 prd_features 和成本参数动态计算报价。

    公式:
      标准版 = 所有 STANDARD + CUSTOM 功能
      裁剪版 = 核心 STANDARD 功能（前 60%）
      人天 = std_count × days_per_std + custom_count × days_per_std × custom_multiplier
      开发费 = 人天 × person_day_rate
      维护费 = 开发费 × maintenance_rate
      毛利 = 开发费 × margin_rate
    """
    from core.config import get_config

    logger.info("=" * 60)
    logger.info("[Commercial Agent] 节点启动 - 动态双报价生成")

    features = state.get("prd_features", [])
    logger.info("[Commercial Agent] 输入: prd_features 数量=%d", len(features))

    # 分类统计功能点
    std_features = [f for f in features if f.get("tag") == FeatureTag.STANDARD.value]
    custom_features = [f for f in features if f.get("tag") == FeatureTag.CUSTOM.value]
    unsupported = [f for f in features if f.get("tag") == FeatureTag.UNSUPPORTED.value]

    logger.info("[Commercial Agent] 功能分类: 标准=%d, 定制=%d, 不支持=%d",
                len(std_features), len(custom_features), len(unsupported))

    # 加载成本参数
    cfg = get_config()
    cost = cfg.cost
    pd_rate = cost.person_day_rate
    days_std = cost.days_per_std_feature
    custom_mul = cost.custom_multiplier
    margin = cost.margin_rate
    maint = cost.maintenance_rate

    logger.info("[Commercial Agent] 成本参数: 人天费率=%d元, 标准人天/功能=%d, "
                "定制倍率=%.1fx, 毛利率=%.0f%%, 维护费率=%.0f%%",
                pd_rate, days_std, custom_mul, margin * 100, maint * 100)

    # ---- 标准版：所有 STANDARD + CUSTOM ----
    std_pd = len(std_features) * days_std
    custom_pd = len(custom_features) * int(days_std * custom_mul)
    total_pd_standard = std_pd + custom_pd
    dev_fee_standard = total_pd_standard * pd_rate

    # ---- 裁剪版：核心 STANDARD 功能（前 60%） ----
    core_count = max(1, int(len(std_features) * 0.6))
    total_pd_trimmed = core_count * days_std
    dev_fee_trimmed = total_pd_trimmed * pd_rate

    quotes = {
        "标准版": {
            "功能数": len(std_features) + len(custom_features),
            "人天": total_pd_standard,
            "开发费": dev_fee_standard,
            "维护费": int(dev_fee_standard * maint),
            "毛利": int(dev_fee_standard * margin),
            "毛利率": margin,
        },
        "裁剪版": {
            "功能数": core_count,
            "人天": total_pd_trimmed,
            "开发费": dev_fee_trimmed,
            "维护费": int(dev_fee_trimmed * maint),
            "毛利": int(dev_fee_trimmed * margin),
            "毛利率": margin,
        },
    }

    logger.info("[Commercial Agent] 报价生成完成:")
    for version, quote in quotes.items():
        logger.info("[Commercial Agent]   %s: 功能=%d, 人天=%d, 开发费=%d元, "
                    "维护费=%d元, 毛利=%d元 (%.0f%%)",
                    version, quote["功能数"], quote["人天"], quote["开发费"],
                    quote["维护费"], quote["毛利"], quote["毛利率"] * 100)

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
    """Review Agent：调用 LLM 进行 Tech/Design/QA 三维评审。"""
    logger.info("=" * 60)
    logger.info("[Review Agent] 节点启动 - 多维评审 (Tech/Design/QA)")
    prd = state.get("prd", {})
    features = state.get("prd_features", [])

    llm_reply = ""
    try:
        from agents.prompts import build_review_prompt
        from agents.llm_client import invoke_llm
        prd_text = str(prd)
        prompt = build_review_prompt(prd_text, features)
        logger.info("[Review Agent] Prompt 构建完成, 长度=%d", len(prompt))
        llm_reply = invoke_llm("review", prompt)
        logger.info("[Review Agent] LLM 返回 %d 字符", len(llm_reply))
    except Exception as e:
        logger.error("[Review Agent] LLM 调用失败，回退到 mock: %s", e)

    if llm_reply:
        review_pass = "不通过" not in llm_reply[:500]
        review_comments = {"tech": [llm_reply[:300]],
                           "design": ["见 LLM 完整输出"],
                           "qa": ["见 LLM 完整输出"]}
    else:
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
        review_pass = True

    logger.info("[Review Agent] 评审结论: %s", "通过" if review_pass else "不通过")
    for dimension, comments in review_comments.items():
        logger.info("[Review Agent]   %s: %d 条意见", dimension.upper(), len(comments))

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
    """Planner Agent：调用 LLM 生成交付计划。"""
    logger.info("=" * 60)
    logger.info("[Planner Agent] 节点启动 - 交付计划生成")
    prd = state.get("prd", {})

    llm_reply = ""
    try:
        from agents.prompts import build_planner_prompt
        from agents.llm_client import invoke_llm
        prd_text = str(prd)
        prompt = build_planner_prompt(prd_text)
        logger.info("[Planner Agent] Prompt 构建完成, 长度=%d", len(prompt))
        llm_reply = invoke_llm("planner", prompt)
        logger.info("[Planner Agent] LLM 返回 %d 字符", len(llm_reply))
    except Exception as e:
        logger.error("[Planner Agent] LLM 调用失败，回退到 mock: %s", e)

    if llm_reply:
        delivery_plan = _parse_llm_delivery_plan(llm_reply)
    else:
        delivery_plan = [
            {"phase": "需求确认", "duration": "1周", "deliverable": "PRD 终稿 + 评审记录"},
            {"phase": "设计阶段", "duration": "2周", "deliverable": "UI 设计稿 + 技术方案"},
            {"phase": "开发阶段", "duration": "3周", "deliverable": "核心功能代码 + 单元测试"},
            {"phase": "联调测试", "duration": "1周", "deliverable": "集成测试报告 + Bug 修复"},
            {"phase": "上线交付", "duration": "1周", "deliverable": "生产环境部署 + 验收文档"},
        ]

    # 安全计算总时长（处理 LLM 输出格式多样化："3周"/3/"3" 均接受）
    def _parse_weeks(item: dict) -> int:
        for key in ("duration", "weeks"):
            val = item.get(key)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str):
                return int(val.replace("周", "").strip() or "0")
        return 0
    total_weeks = sum(_parse_weeks(p) for p in delivery_plan)

    logger.info("[Planner Agent] 交付计划生成完成, 共 %d 阶段, 总工期 %d 周:",
                len(delivery_plan), total_weeks)
    for phase in delivery_plan:
        dur = phase.get("duration", phase.get("weeks", "N/A"))
        # dur 可能是 int/str，统一转为字符串用于日志
        dur_str = f"{dur}周" if isinstance(dur, (int, float)) else str(dur)
        ph = phase.get("phase", phase.get("name", "?"))
        dlv = phase.get("deliverable", phase.get("deliverables", "?"))
        logger.info("[Planner Agent]   %s (%s): %s", ph, dur_str, dlv)

    logger.info("[Planner Agent] 节点完成")
    logger.info("=" * 60)

    return {
        "delivery_plan": delivery_plan,
        "audit_snapshots": [_make_snapshot("planner_agent")],
        "current_node": "planner_agent",
    }

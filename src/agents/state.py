"""LangGraph State 定义 - 贯穿 7 Agent 的全局状态。

State 在各 Agent 间传递，每个 Agent 读取所需字段、写入产出字段。
TypedDict 保证类型安全，LangGraph 自动合并 State 更新。

注意：audit_snapshots 使用 Annotated+operator.add reducer，
因为 Commercial/Contract/Review 三个并行节点会同时追加快照。
"""
from typing import TypedDict, List, Dict, Optional, Literal, Annotated
from enum import Enum
import operator


class RiskLevel(str, Enum):
    """合规风险等级。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeatureTag(str, Enum):
    """功能点标注。"""
    STANDARD = "标准功能"
    CUSTOM = "定制功能"
    UNSUPPORTED = "暂不支持"


class SpecMindState(TypedDict, total=False):
    """SpecMind 工作流全局 State。

    字段分组：
    - 输入：raw_input, client_info
    - SAR：cleaned_requirements, overcommit_risks
    - Legal：legal_risk_level, legal_issues, legal_blocked
    - PM：prd, prd_features
    - Commercial：quotes
    - Contract：contract_conflicts
    - Review：review_comments, review_pass
    - Planner：delivery_plan
    - 审计：audit_snapshots, current_node
    """
    # === 输入 ===
    raw_input: str                          # 原始脏需求（微信记录/口头/文档）
    client_info: Dict[str, str]             # 客户信息

    # === SAR Agent 输出 ===
    cleaned_requirements: str               # 清洗后的标准化需求
    overcommit_risks: List[str]             # 过度承诺风险标注

    # === Legal Agent 输出 ===
    legal_risk_level: str                   # 合规风险等级（存字符串，避免 Enum 反序列化警告）
    legal_issues: List[Dict[str, str]]      # 疑似法条与说明
    legal_blocked: bool                     # 高风险阻断标记

    # === PM Agent 输出 ===
    prd: Dict[str, str]                     # PRD 8 模块
    prd_features: List[Dict[str, str]]      # 功能点列表（含标注）

    # === Commercial Agent 输出 ===
    quotes: Dict[str, Dict[str, float]]     # 标准版/裁剪版报价

    # === Contract Agent 输出 ===
    contract_conflicts: List[Dict[str, str]]  # 条款冲突

    # === Review Agent 输出 ===
    review_comments: Dict[str, List[str]]   # Tech/Design/QA 评审意见
    review_pass: bool                       # 评审是否通过

    # === Planner Agent 输出 ===
    delivery_plan: List[Dict[str, str]]     # 交付计划

    # === 审计（reducer: 并行节点追加合并） ===
    audit_snapshots: Annotated[List[Dict], operator.add]  # State 快照（并行安全）
    current_node: str                       # 当前执行节点

    # === LLM 错误追踪（reducer: 并行节点追加合并） ===
    llm_errors: Annotated[List[str], operator.add]  # LLM 调用失败信息（非空=有回退到 mock）

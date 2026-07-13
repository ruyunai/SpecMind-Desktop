"""LLM 客户端 — 统一管理 ChatOpenAI 实例，按 Agent 路由模型。

用法：
  from agents.llm_client import get_llm, invoke_llm

  llm = get_llm("legal")           # 获取 Legal Agent 的 ChatOpenAI 实例
  reply = invoke_llm("legal", prompt)  # 同步调用并返回文本

所有 API Key 通过加密存储读取，不硬编码。
DeepSeek API 完全兼容 OpenAI 格式（base_url="https://api.deepseek.com/v1"）。
"""
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.config import get_config, AGENT_KEYS

logger = logging.getLogger("specmind.llm")


# ---- 缓存：按 agent_key 缓存 ChatOpenAI 实例 ----
_llm_cache: dict = {}


def _create_llm(agent_key: str) -> ChatOpenAI:
    """为指定 Agent 创建 ChatOpenAI 实例。"""
    cfg = get_config()
    agent_cfg = cfg.agents.get(agent_key)

    model = agent_cfg.model if agent_cfg and agent_cfg.model else "deepseek-chat"
    base_url = cfg.get_agent_base_url(agent_key)
    api_key = cfg.get_agent_api_key(agent_key)

    if not api_key:
        raise ValueError(
            f"未配置 API Key。请在 GUI 设置（Ctrl+, → 模型配置）中输入 DeepSeek API Key，"
            f"或设置环境变量 SPECMIND_API_KEY"
        )

    return ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0.3,
        timeout=120,
        max_retries=2,
    )


def get_llm(agent_key: str) -> ChatOpenAI:
    """获取 Agent 对应的 ChatOpenAI 实例（带缓存）。"""
    if agent_key not in _llm_cache:
        _llm_cache[agent_key] = _create_llm(agent_key)
    return _llm_cache[agent_key]


def invoke_llm(agent_key: str, prompt: str) -> str:
    """同步调用 LLM，返回文本内容。

    Args:
        agent_key: Agent 标识（sar/legal/pm/commercial/contract/review/planner）
        prompt: 完整 Prompt（含 System + User，用 "\\n\\n" 分隔）

    Returns:
        LLM 返回的文本
    """
    llm = get_llm(agent_key)

    # 尝试从 prompt 中分离 System/User 消息
    if prompt.startswith("System:"):
        parts = prompt.split("\n\nUser:", 1) if "\n\nUser:" in prompt else (prompt, "")
        system = parts[0].replace("System:", "").strip() if len(parts) > 1 else ""
        user = parts[1].strip() if len(parts) > 1 else prompt
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ]
    else:
        messages = [HumanMessage(content=prompt)]

    logger.info("[LLM] %s → 调用中 (model=%s)...", agent_key, llm.model_name)
    response = llm.invoke(messages)
    content = response.content.strip() if hasattr(response, "content") else str(response)
    logger.info("[LLM] %s ← 返回 %d 字符", agent_key, len(content))
    return content


def clear_llm_cache() -> None:
    """清除 LLM 实例缓存（配置变更后调用）。"""
    _llm_cache.clear()
    logger.info("[LLM] 缓存已清除")

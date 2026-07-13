"""LLM 客户端 — 统一管理 ChatOpenAI 实例，按 Agent 路由模型。

用法：
  from agents.llm_client import get_llm, invoke_llm

  llm = get_llm("legal")           # 获取 Legal Agent 的 ChatOpenAI 实例
  reply = invoke_llm("legal", prompt)  # 同步调用并返回文本

所有 API Key 通过加密存储读取，不硬编码。
DeepSeek API 完全兼容 OpenAI 格式（base_url="https://api.deepseek.com/v1"）。
"""
import logging
import time
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.config import get_config, AGENT_KEYS

logger = logging.getLogger("specmind.llm")

# ---- 重试配置 ----
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0          # 首次重试等待 2s
RETRY_BACKOFF_FACTOR = 2.0      # 每次翻倍：2s → 4s → 8s
RETRYABLE_ERRORS = (
    "timeout",
    "connection",
    "rate limit",
    "server error",
    "service unavailable",
    "too many requests",
    "internal server error",
    "bad gateway",
    "gateway timeout",
)


def _is_retryable(error: Exception) -> bool:
    """判断异常是否可重试（网络/服务端错误可重试，认证/参数错误不重试）。"""
    # 按异常类型判断（Python 内置异常可能无消息文本）
    type_name = type(error).__name__.lower()
    if any(kw in type_name for kw in ("timeout", "connection", "oserror")):
        return True

    msg = str(error).lower()
    return any(keyword in msg for keyword in RETRYABLE_ERRORS)


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
        max_retries=2,  # langchain 内置重试
    )


def get_llm(agent_key: str) -> ChatOpenAI:
    """获取 Agent 对应的 ChatOpenAI 实例（带缓存）。"""
    if agent_key not in _llm_cache:
        _llm_cache[agent_key] = _create_llm(agent_key)
    return _llm_cache[agent_key]


def invoke_llm(agent_key: str, prompt: str) -> str:
    """同步调用 LLM，带重试机制。

    最多重试 MAX_RETRIES 次（默认 3 次），指数退避 (2s → 4s → 8s)。
    仅对网络/超时/服务端错误重试，认证错误直接抛出。

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

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            logger.info(
                "[LLM] %s → 调用中 (model=%s, attempt=%d/%d)...",
                agent_key, llm.model_name, attempt, 1 + MAX_RETRIES,
            )
            response = llm.invoke(messages)
            content = (
                response.content.strip()
                if hasattr(response, "content")
                else str(response)
            )
            logger.info("[LLM] %s ← 返回 %d 字符", agent_key, len(content))
            if attempt > 0:
                logger.info("[LLM] %s 重试成功 (第 %d 次)", agent_key, attempt)
            return content

        except Exception as e:
            last_error = e
            if attempt >= MAX_RETRIES:
                logger.error(
                    "[LLM] %s 重试 %d 次后仍失败: %s",
                    agent_key, MAX_RETRIES, e,
                )
                raise

            if not _is_retryable(e):
                logger.error("[LLM] %s 不可重试错误，直接抛出: %s", agent_key, e)
                raise

            delay = RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.warning(
                "[LLM] %s 调用失败 (attempt=%d): %s → %ss 后重试...",
                agent_key, attempt, str(e)[:100], delay,
            )
            time.sleep(delay)

    # 不应到达此处
    raise last_error  # type: ignore[misc]


def clear_llm_cache() -> None:
    """清除 LLM 实例缓存（配置变更后调用）。"""
    _llm_cache.clear()
    logger.info("[LLM] 缓存已清除")

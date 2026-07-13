"""配置管理 - 全局 + 每 Agent 独立的 LLM 配置。

配置目录：%APPDATA%/SpecMindDesktop/config/
- app.json：明文配置（模型映射、Base URL、路径）
- secrets.enc：Fernet 加密的 API Key（全局 + 各 Agent 独立）

支持：GUI 可视化输入切换每个 Agent 的模型/API Key/Base URL。
"""
import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict

from core.crypto import get_crypto
from core.logger import setup_logger

_config_logger = setup_logger("specmind.core")


# 7 个 Agent 的固定标识
AGENT_KEYS = ["sar", "legal", "pm", "commercial", "contract", "review", "planner"]

# 预设模型路由策略（DeepSeek 默认）
PRESET_ROUTING = {
    "混合路由（推荐）": {
        "sar": "deepseek-chat",
        "legal": "deepseek-chat",
        "pm": "deepseek-chat",
        "commercial": "deepseek-chat",
        "contract": "deepseek-chat",
        "review": "deepseek-chat",
        "planner": "deepseek-chat",
    },
    "全 DeepSeek-V3": {k: "deepseek-chat" for k in AGENT_KEYS},
    "全 DeepSeek-R1": {k: "deepseek-reasoner" for k in AGENT_KEYS},
    "全硅基 GLM-4": {k: "THUDM/glm-4-flash" for k in AGENT_KEYS},
}

# 常用模型列表（供 GUI 下拉选择）
COMMON_MODELS = [
    "deepseek-chat",
    "deepseek-reasoner",
    "THUDM/glm-4-flash",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "meta-llama/Meta-Llama-3.1-405B-Instruct",
]


@dataclass
class AgentModelConfig:
    """单个 Agent 的模型配置。"""
    model: str = ""                    # 模型名
    api_key_enc: str = ""              # 独立 API Key（Fernet 加密，空则用全局）
    base_url: str = ""                 # 独立 Base URL（空则用全局）
    use_global_key: bool = True        # 是否使用全局 API Key


@dataclass
class CostConfig:
    """报价成本参数（可在 GUI 成本参数 Tab 中配置）。

    不同公司/项目可通过调整这些参数灵活控制报价。
    """
    person_day_rate: int = 3000            # 元/人天
    days_per_std_feature: int = 15         # 每个标准功能所需人天
    custom_multiplier: float = 2.0         # 定制功能人天倍率（相对标准功能）
    margin_rate: float = 0.40              # 毛利率
    maintenance_rate: float = 0.10         # 维护费占开发费比例
    project_months: int = 3                # 项目周期（月）


def _get_app_data_dir() -> Path:
    """获取应用数据目录。

    - 便携模式：exe 同级
    - 其他：%APPDATA%/SpecMindDesktop/
    """
    from core import get_app_root
    return get_app_root()


def _default_agents() -> Dict[str, AgentModelConfig]:
    """默认 Agent 配置（混合路由）。"""
    preset = PRESET_ROUTING["混合路由（推荐）"]
    return {k: AgentModelConfig(model=preset[k]) for k in AGENT_KEYS}


@dataclass
class AppConfig:
    """应用配置（全局 + 每 Agent）。"""
    global_base_url: str = "https://api.deepseek.com/v1"
    global_api_key_enc: str = ""       # 全局 API Key（Fernet 加密）
    embedding_model: str = "BAAI/bge-m3"
    agents: Dict[str, AgentModelConfig] = field(default_factory=_default_agents)
    cost: CostConfig = field(default_factory=CostConfig)
    data_dir: Path = field(default_factory=_get_app_data_dir)

    @property
    def config_dir(self) -> Path:
        """配置文件目录。"""
        return self.data_dir / "config"

    @property
    def app_config_path(self) -> Path:
        """明文配置路径。"""
        return self.config_dir / "app.json"

    @property
    def secrets_path(self) -> Path:
        """加密密钥路径。"""
        return self.config_dir / "secrets.enc"

    @property
    def chroma_path(self) -> Path:
        """ChromaDB 路径。"""
        return self.data_dir / "chroma"

    @property
    def sqlite_path(self) -> Path:
        """SQLite 路径。"""
        return self.data_dir / "audit.db"

    def get_global_api_key(self) -> str:
        """解密返回全局 API Key 明文。

        优先级：环境变量 SPECMIND_API_KEY > 加密存储。
        """
        env_key = os.environ.get("SPECMIND_API_KEY", "").strip()
        if env_key:
            return env_key
        return get_crypto().decrypt(self.global_api_key_enc)

    def set_global_api_key(self, plaintext: str) -> None:
        """加密存储全局 API Key。"""
        self.global_api_key_enc = get_crypto().encrypt(plaintext)

    def get_agent_api_key(self, agent_key: str) -> str:
        """获取 Agent 实际使用的 API Key（独立 > 全局）。"""
        agent = self.agents.get(agent_key)
        if agent and not agent.use_global_key and agent.api_key_enc:
            return get_crypto().decrypt(agent.api_key_enc)
        return self.get_global_api_key()

    def get_agent_base_url(self, agent_key: str) -> str:
        """获取 Agent 实际使用的 Base URL（独立 > 全局）。"""
        agent = self.agents.get(agent_key)
        if agent and agent.base_url:
            return agent.base_url
        return self.global_base_url

    def ensure_dirs(self) -> None:
        """确保必要目录存在。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """保存配置（app.json 明文 + secrets.enc 加密）。

        保存前自动迁移旧格式（硬编码密码）加密的 API Key 到新密钥。
        """
        self.ensure_dirs()
        self._migrate_keys_if_needed()
        data = {
            "global_base_url": self.global_base_url,
            "global_api_key_enc": self.global_api_key_enc,
            "embedding_model": self.embedding_model,
            "data_dir": str(self.data_dir),
            "agents": {k: asdict(v) for k, v in self.agents.items()},
            "cost": asdict(self.cost),
        }
        self.app_config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _migrate_keys_if_needed(self) -> None:
        """检测并迁移旧格式加密的 API Key 到新密钥。"""
        crypto = get_crypto()
        migrated = False

        # 迁移全局 API Key
        if self.global_api_key_enc and crypto.needs_migration(self.global_api_key_enc):
            plaintext = crypto.decrypt(self.global_api_key_enc)
            if plaintext:
                self.global_api_key_enc = crypto.encrypt(plaintext)
                migrated = True

        # 迁移各 Agent 独立 API Key
        for agent_key, agent_config in self.agents.items():
            if agent_config.api_key_enc and crypto.needs_migration(agent_config.api_key_enc):
                plaintext = crypto.decrypt(agent_config.api_key_enc)
                if plaintext:
                    agent_config.api_key_enc = crypto.encrypt(plaintext)
                    migrated = True

        if migrated:
            _config_logger.info(
                "API Key 已从旧格式迁移到新密钥（随机 key_seed + 机器绑定）"
            )

    @classmethod
    def load(cls) -> "AppConfig":
        """从 app.json 加载，不存在则返回默认。"""
        config = cls()
        if config.app_config_path.exists():
            try:
                data = json.loads(config.app_config_path.read_text(encoding="utf-8"))
                config.global_base_url = data.get("global_base_url", config.global_base_url)
                config.global_api_key_enc = data.get("global_api_key_enc", "")
                config.embedding_model = data.get("embedding_model", config.embedding_model)
                agents_data = data.get("agents", {})
                config.agents = {
                    k: AgentModelConfig(**agents_data[k]) for k in AGENT_KEYS if k in agents_data
                } or _default_agents()
                cost_data = data.get("cost", {})
                if cost_data:
                    config.cost = CostConfig(**cost_data)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        config.ensure_dirs()
        return config


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取全局配置单例。"""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置（GUI 保存后调用）。"""
    global _config
    _config = AppConfig.load()
    return _config

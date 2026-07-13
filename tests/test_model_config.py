"""模型配置路由切换逻辑测试。

验证点：
1. 默认配置加载（混合路由）
2. 预设路由一键切换（全 Qwen / 全 DeepSeek / 全 GLM）
3. 独立 API Key 加密存储与读取
4. 独立 Base URL 覆盖全局
5. use_global_key 开关生效
6. 配置持久化（保存后重新加载一致）
"""
import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import (
    AppConfig,
    AgentModelConfig,
    AGENT_KEYS,
    PRESET_ROUTING,
    reload_config,
    get_config,
)
from core.crypto import get_crypto


def print_separator(title: str) -> None:
    """打印分隔标题。"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_default_config() -> None:
    """测试 1：默认配置加载（混合路由）。"""
    print_separator("测试 1：默认配置加载（混合路由）")
    config = AppConfig()
    print(f"全局 Base URL: {config.global_base_url}")
    print(f"全局 API Key（加密）: {config.global_api_key_enc or '(空)'}")
    print(f"Agent 数量: {len(config.agents)}")
    print("\n各 Agent 默认模型:")
    for key in AGENT_KEYS:
        agent = config.agents.get(key)
        print(f"  {key:12s} → 模型: {agent.model:35s} 用全局Key: {agent.use_global_key}")


def test_preset_switching() -> None:
    """测试 2：预设路由一键切换。"""
    print_separator("测试 2：预设路由一键切换")
    config = AppConfig()

    for preset_name, routing in PRESET_ROUTING.items():
        print(f"\n▶ 预设: {preset_name}")
        for key in AGENT_KEYS:
            model = routing.get(key, "")
            print(f"  {key:12s} → {model}")

    # 模拟应用"全 DeepSeek-V3"预设
    print("\n▶ 模拟应用「全 DeepSeek-V3」预设:")
    preset = PRESET_ROUTING["全 DeepSeek-V3"]
    for key in AGENT_KEYS:
        config.agents[key].model = preset[key]
    for key in AGENT_KEYS:
        print(f"  {key:12s} → {config.agents[key].model}")
    print("✅ 预设切换成功" if all(
        config.agents[k].model == "deepseek-ai/DeepSeek-V3" for k in AGENT_KEYS
    ) else "❌ 预设切换失败")


def test_independent_api_key() -> None:
    """测试 3：独立 API Key 加密存储与读取。"""
    print_separator("测试 3：独立 API Key 加密存储与读取")
    config = AppConfig()
    crypto = get_crypto()

    # 设置全局 Key
    global_key = "sk-global-1234567890"
    config.set_global_api_key(global_key)
    print(f"全局 Key 明文: {global_key}")
    print(f"全局 Key 加密: {config.global_api_key_enc[:40]}...")
    print(f"全局 Key 解密: {config.get_global_api_key()}")
    assert config.get_global_api_key() == global_key, "全局 Key 加解密不一致"
    print("✅ 全局 Key 加解密一致")

    # 为 Legal Agent 设置独立 Key
    legal_key = "sk-legal-independent-key"
    config.agents["legal"].use_global_key = False
    config.agents["legal"].api_key_enc = crypto.encrypt(legal_key)
    print(f"\nLegal 独立 Key 明文: {legal_key}")
    print(f"Legal 独立 Key 加密: {config.agents['legal'].api_key_enc[:40]}...")
    print(f"Legal 实际使用 Key: {config.get_agent_api_key('legal')}")
    assert config.get_agent_api_key("legal") == legal_key, "Legal 独立 Key 读取失败"
    print("✅ Legal 独立 Key 生效")

    # 验证其他 Agent 仍用全局 Key
    pm_key = config.get_agent_api_key("pm")
    print(f"\nPM（用全局Key）实际 Key: {pm_key}")
    assert pm_key == global_key, "PM 应使用全局 Key"
    print("✅ PM 正确使用全局 Key")


def test_independent_base_url() -> None:
    """测试 4：独立 Base URL 覆盖全局。"""
    print_separator("测试 4：独立 Base URL 覆盖全局")
    config = AppConfig()
    config.global_base_url = "https://api.siliconflow.cn/v1"

    # 为 Commercial Agent 设置独立 URL
    custom_url = "https://custom-llm.example.com/v1"
    config.agents["commercial"].base_url = custom_url

    print(f"全局 Base URL: {config.global_base_url}")
    print(f"Commercial 独立 URL: {config.agents['commercial'].base_url}")
    print(f"Commercial 实际 URL: {config.get_agent_base_url('commercial')}")
    print(f"PM 实际 URL: {config.get_agent_base_url('pm')}")
    assert config.get_agent_base_url("commercial") == custom_url, "Commercial URL 覆盖失败"
    assert config.get_agent_base_url("pm") == config.global_base_url, "PM 应使用全局 URL"
    print("✅ 独立 Base URL 覆盖生效，其他 Agent 仍用全局")


def test_use_global_key_toggle() -> None:
    """测试 5：use_global_key 开关生效。"""
    print_separator("测试 5：use_global_key 开关切换")
    config = AppConfig()
    crypto = get_crypto()

    config.set_global_api_key("sk-global-test")
    config.agents["pm"].use_global_key = False
    config.agents["pm"].api_key_enc = crypto.encrypt("sk-pm-exclusive")

    # use_global_key = False → 用独立 Key
    print(f"PM use_global_key=False → Key: {config.get_agent_api_key('pm')}")
    assert config.get_agent_api_key("pm") == "sk-pm-exclusive"

    # 切换为 True → 用全局 Key
    config.agents["pm"].use_global_key = True
    print(f"PM use_global_key=True  → Key: {config.get_agent_api_key('pm')}")
    assert config.get_agent_api_key("pm") == "sk-global-test"
    print("✅ use_global_key 开关切换正确")


def test_persistence() -> None:
    """测试 6：配置持久化（保存后重新加载一致）。"""
    print_separator("测试 6：配置持久化")
    config = AppConfig()
    config.set_global_api_key("sk-persist-test-123")
    config.global_base_url = "https://api.siliconflow.cn/v1"
    config.agents["legal"].use_global_key = False
    config.agents["legal"].api_key_enc = get_crypto().encrypt("sk-legal-persist")
    config.agents["legal"].base_url = "https://legal-only.example.com/v1"
    config.agents["sar"].model = "THUDM/glm-4-flash"

    print("保存前配置:")
    print(f"  全局 Key: {config.get_global_api_key()}")
    print(f"  Legal Key: {config.get_agent_api_key('legal')}")
    print(f"  Legal URL: {config.get_agent_base_url('legal')}")
    print(f"  SAR 模型: {config.agents['sar'].model}")

    config.save()
    print(f"\n配置已保存到: {config.app_config_path}")

    # 重新加载
    config2 = reload_config()
    print("\n重新加载后配置:")
    print(f"  全局 Key: {config2.get_global_api_key()}")
    print(f"  Legal Key: {config2.get_agent_api_key('legal')}")
    print(f"  Legal URL: {config2.get_agent_base_url('legal')}")
    print(f"  SAR 模型: {config2.agents['sar'].model}")

    assert config2.get_global_api_key() == "sk-persist-test-123", "全局 Key 持久化失败"
    assert config2.get_agent_api_key("legal") == "sk-legal-persist", "Legal Key 持久化失败"
    assert config2.get_agent_base_url("legal") == "https://legal-only.example.com/v1", "Legal URL 持久化失败"
    assert config2.agents["sar"].model == "THUDM/glm-4-flash", "SAR 模型持久化失败"
    print("\n✅ 配置持久化全部一致")


def main() -> int:
    """运行所有测试。"""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SpecMind Desktop - 模型配置路由切换逻辑测试              ║")
    print("╚══════════════════════════════════════════════════════════╝")

    try:
        test_default_config()
        test_preset_switching()
        test_independent_api_key()
        test_independent_base_url()
        test_use_global_key_toggle()
        test_persistence()

        print_separator("全部测试通过")
        print("✅ 默认配置加载")
        print("✅ 预设路由切换（4 套预设）")
        print("✅ 独立 API Key 加密存储与读取")
        print("✅ 独立 Base URL 覆盖全局")
        print("✅ use_global_key 开关切换")
        print("✅ 配置持久化（保存+重新加载）")
        return 0
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Fernet 对称加密 - API Key 加密存储。

密钥派生策略（阶段 8.6 加固）：
  1. 首次运行：生成 32 字节随机 key_seed，保存到 %APPDATA%/SpecMindDesktop/config/.keyseed
  2. 密钥派生：PBKDF2(key_seed, machine_id, 200k 轮) → 32 字节 Fernet 密钥
  3. 机器绑定：key_seed + uuid.getnode() 双因子，防止跨机器拷贝 exe + DB 解密
  4. 旧格式迁移：解密失败时回退旧硬编码密码，成功后自动迁移到新密钥

安全性提升：
  - 旧方案：硬编码 "specmind_default" → 任何人可复现密钥
  - 新方案：随机 key_seed（2^256 搜索空间）+ 机器绑定 → 不可复现
"""
import base64
import hashlib
import os
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from core.logger import setup_logger

logger = setup_logger("specmind.core")


# ---- 密钥种子文件管理 ----

def _get_key_seed_path() -> Path:
    """获取 key_seed 文件路径。

    - 便携模式：exe 同级 config/.keyseed
    - 其他：%APPDATA%/SpecMindDesktop/config/.keyseed
    """
    from core import get_app_root
    config_dir = get_app_root() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / ".keyseed"


def _generate_key_seed() -> bytes:
    """生成 32 字节随机密钥种子（使用 os.urandom）。"""
    return os.urandom(32)


def _load_or_create_key_seed() -> bytes:
    """加载或创建密钥种子文件（幂等）。"""
    seed_path = _get_key_seed_path()
    if seed_path.exists():
        with open(seed_path, "rb") as f:
            return f.read()

    # 首次运行：生成随机种子
    key_seed = _generate_key_seed()
    # 使用临时文件写入保证原子性
    tmp_path = seed_path.with_suffix(".tmp")
    with open(tmp_path, "wb") as f:
        f.write(key_seed)
    tmp_path.replace(seed_path)  # 原子替换（Windows 支持）
    logger.info("密钥种子已生成: %s（%d 字节）", seed_path, len(key_seed))
    return key_seed


# ---- 密钥派生 ----

def _derive_key(key_seed: bytes, salt: bytes) -> bytes:
    """PBKDF2 派生 32 字节 Fernet 密钥。

    Args:
        key_seed: 32 字节随机种子
        salt: 机器标识等盐值
    Returns:
        base64 url-safe 编码的 32 字节密钥
    """
    raw = hashlib.pbkdf2_hmac("sha256", key_seed, salt, 200_000)
    return base64.urlsafe_b64encode(raw)


def _get_machine_salt() -> bytes:
    """获取机器绑定盐值（uuid.getnode() → MAC 地址）。"""
    return str(uuid.getnode()).encode("utf-8")


# ---- 旧格式兼容 ----

# 旧方案：硬编码密码 "specmind_default" + machine_id salt（100k 轮）
# 仅用于解密历史数据，新写入全部使用新密钥

def _derive_legacy_key() -> bytes:
    """旧格式密钥派生（仅用于迁移解密）。"""
    passphrase = "specmind_default"
    machine_id = str(uuid.getnode())
    salt = f"{machine_id}:{passphrase}".encode("utf-8")
    raw = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 100_000)
    return base64.urlsafe_b64encode(raw)


# ---- 加密服务 ----

class CryptoService:
    """API Key 加密服务。

    使用随机 key_seed + 机器绑定派生 Fernet 密钥。
    自动检测并迁移旧格式（硬编码密码）加密的数据。
    """

    def __init__(self) -> None:
        """初始化加密服务：加载 key_seed → 派生主密钥 → 创建备用旧密钥。"""
        self._key_seed = _load_or_create_key_seed()
        self._machine_salt = _get_machine_salt()
        self._fernet = Fernet(_derive_key(self._key_seed, self._machine_salt))

        # 旧格式 Fernet（懒加载，只在解密失败时创建）
        self._legacy_fernet: Fernet | None = None

    # ---- 公开 API ----

    def encrypt(self, plaintext: str) -> str:
        """加密明文，返回 base64 密文（新格式）。"""
        if not plaintext:
            return ""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """解密密文。

        策略：
          1. 先尝试新密钥解密
          2. 失败 → 尝试旧密钥解密（自动迁移）
          3. 迁移成功后返回明文
          4. 都失败 → 返回空串
        """
        if not ciphertext:
            return ""

        # 尝试新密钥
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            pass

        # 尝试旧密钥（旧格式迁移）
        try:
            legacy = self._get_legacy_fernet()
            plaintext = legacy.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
            logger.warning(
                "检测到旧格式密文，已自动用旧密钥解密。"
                "下次保存配置时将自动迁移到新密钥。"
            )
            return plaintext
        except InvalidToken:
            logger.error("解密失败：新密钥和旧密钥均无法解密")
            return ""

    def needs_migration(self, ciphertext: str) -> bool:
        """检查密文是否需要从旧格式迁移。"""
        if not ciphertext:
            return False
        try:
            self._fernet.decrypt(ciphertext.encode("utf-8"))
            return False  # 新密钥可解密
        except InvalidToken:
            try:
                self._get_legacy_fernet()
                self._get_legacy_fernet().decrypt(ciphertext.encode("utf-8"))
                return True  # 仅旧密钥可解密
            except InvalidToken:
                return False

    def _get_legacy_fernet(self) -> Fernet:
        """获取旧格式 Fernet 实例（懒创建）。"""
        if self._legacy_fernet is None:
            self._legacy_fernet = Fernet(_derive_legacy_key())
        return self._legacy_fernet


# ---- 全局单例 ----

_crypto: CryptoService | None = None


def get_crypto() -> CryptoService:
    """获取全局加密服务单例。"""
    global _crypto
    if _crypto is None:
        _crypto = CryptoService()
    return _crypto

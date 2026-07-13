"""测试 8.6 S1 密钥派生加固。"""
import os
import sys
from pathlib import Path

# 确保 src 在 path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.crypto import get_crypto, _load_or_create_key_seed, _get_key_seed_path


def test_basic_encrypt_decrypt():
    """测试 1: 基本加密解密。"""
    # 清理旧 key_seed，模拟全新环境
    import core.crypto
    seed_path = _get_key_seed_path()
    if seed_path.exists():
        seed_path.unlink()
    core.crypto._crypto = None  # 重置单例

    crypto = get_crypto()
    plaintext = "sk-this-is-a-test-api-key-12345"
    cipher = crypto.encrypt(plaintext)
    decrypted = crypto.decrypt(cipher)

    assert plaintext == decrypted, f"FAIL: {plaintext} != {decrypted}"
    assert seed_path.exists(), "FAIL: key_seed not created"
    assert seed_path.stat().st_size == 32, "FAIL: wrong seed size"
    print("PASS: test_basic_encrypt_decrypt")


def test_empty_string():
    """测试 2: 空字符串处理。"""
    crypto = get_crypto()
    assert crypto.encrypt("") == "", "FAIL: encrypt empty"
    assert crypto.decrypt("") == "", "FAIL: decrypt empty"
    print("PASS: test_empty_string")


def test_invalid_ciphertext():
    """测试 3: 无效密文。"""
    crypto = get_crypto()
    result = crypto.decrypt("not-valid-base64!!!")
    assert result == "", "FAIL: should return empty"
    print("PASS: test_invalid_ciphertext")


def test_needs_migration_new_format():
    """测试 4: 新格式密文不需要迁移。"""
    crypto = get_crypto()
    cipher = crypto.encrypt("test-key")
    needs = crypto.needs_migration(cipher)
    assert not needs, "FAIL: new format should not need migration"
    print("PASS: test_needs_migration_new_format")


def test_no_stale_tmp_file():
    """测试 5: 临时文件已清理。"""
    seed_path = _get_key_seed_path()
    tmp_path = seed_path.with_suffix(".tmp")
    assert not tmp_path.exists(), "FAIL: tmp file left behind"
    print("PASS: test_no_stale_tmp_file")


def test_key_seed_is_random():
    """测试 6: key_seed 是随机的（不同时间创建的不同）。"""
    seed_path = _get_key_seed_path()
    if seed_path.exists():
        seed_path.unlink()

    import core.crypto
    core.crypto._crypto = None
    seed1 = _load_or_create_key_seed()
    seed_path.unlink()
    # 不重置 _crypto 单例，但强制重新加载 seed
    seed2 = _load_or_create_key_seed()

    assert seed1 != seed2, "FAIL: seeds should differ (random)"
    print("PASS: test_key_seed_is_random")


if __name__ == "__main__":
    test_basic_encrypt_decrypt()
    test_empty_string()
    test_invalid_ciphertext()
    test_needs_migration_new_format()
    test_no_stale_tmp_file()
    test_key_seed_is_random()
    print("\nAll 6 tests passed!")

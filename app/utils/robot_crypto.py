"""
机器人ID加解密工具
使用AES-256-CBC对机器人真实ID进行加密/解密
数据库中存储加密后的机器人ID，系统使用时动态解密还原真实ID
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

_ROBOT_CRYPTO_SEED = "qianfang-air-cargo-robot-id-encryption-key-2026"


def _derive_key(seed: str = _ROBOT_CRYPTO_SEED) -> bytes:
    """
    从种子字符串派生32字节AES-256密钥（SHA-256）
    
    Args:
        seed: 密钥种子字符串
    
    Returns:
        32字节密钥
    """
    return hashlib.sha256(seed.encode("utf-8")).digest()


def encrypt_robot_id(plain_robot_id: str) -> str:
    """
    加密机器人真实ID
    
    加密流程：明文 -> PKCS7填充 -> AES-256-CBC加密 -> IV + 密文 -> Base64编码（URL安全）
    
    Args:
        plain_robot_id: 机器人真实ID（明文）
    
    Returns:
        加密后的字符串（URL安全的Base64编码）
    """
    if not plain_robot_id:
        raise ValueError("机器人ID不能为空")
    
    key = _derive_key()
    iv = os.urandom(16)  
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain_robot_id.encode("utf-8")) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    encrypted_bytes = iv + ciphertext
    return base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")


def decrypt_robot_id(encrypted_robot_id: str) -> str:
    """
    解密机器人ID，还原为真实ID
    
    解密流程：Base64解码 -> 分离IV和密文 -> AES-256-CBC解密 -> 去除PKCS7填充 -> 明文
    
    Args:
        encrypted_robot_id: 加密后的机器人ID（URL安全的Base64编码）
    
    Returns:
        解密后的机器人真实ID（明文）
    
    Raises:
        ValueError: 加密数据格式错误或解密失败
    """
    if not encrypted_robot_id:
        raise ValueError("加密的机器人ID不能为空")
    
    try:
        key = _derive_key()
        
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_robot_id.encode("utf-8"))
        
        if len(encrypted_bytes) < 32:  
            raise ValueError("加密数据长度不足")
        
        iv = encrypted_bytes[:16]
        ciphertext = encrypted_bytes[16:]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        plain_data = unpadder.update(padded_data) + unpadder.finalize()
        
        return plain_data.decode("utf-8")
    except Exception as e:
        raise ValueError(f"机器人ID解密失败: {e}")

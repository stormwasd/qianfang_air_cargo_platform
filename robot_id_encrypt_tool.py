#!/usr/bin/env python3
"""
机器人ID加密工具（独立脚本）

使用方法：
    python robot_id_encrypt_tool.py

功能：
    1. 加密：输入机器人真实ID，输出加密后的字符串（用于录入系统表单）
    2. 解密：输入加密后的字符串，还原机器人真实ID（用于验证）

注意：
    - 此脚本使用固定密钥种子，与系统运行时使用的密钥一致
    - 加密后的ID可以安全地在表单中输入和存储
    - 系统在使用机器人ID时会自动解密
"""
import sys
import os

# 将项目根目录加入 sys.path，使脚本可以直接引用 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.robot_crypto import encrypt_robot_id, decrypt_robot_id


def main():
    print("=" * 60)
    print("  千方航空物流平台 — 机器人ID加解密工具")
    print("=" * 60)
    print()
    print("请选择操作：")
    print("  1. 加密（输入真实机器人ID -> 输出加密ID）")
    print("  2. 解密（输入加密ID -> 输出真实机器人ID）")
    print("  3. 退出")
    print()

    while True:
        choice = input("请输入选项 (1/2/3): ").strip()

        if choice == "1":
            plain_id = input("请输入机器人真实ID: ").strip()
            if not plain_id:
                print("❌ 机器人ID不能为空！")
                continue
            try:
                encrypted = encrypt_robot_id(plain_id)
                print()
                print("✅ 加密成功！")
                print(f"   真实ID:   {plain_id}")
                print(f"   加密后ID: {encrypted}")
                print()
                print("📋 请将「加密后ID」复制并粘贴到系统管理后台的机器人ID表单中。")
                print()
            except Exception as e:
                print(f"❌ 加密失败: {e}")
                print()

        elif choice == "2":
            encrypted_id = input("请输入加密后的机器人ID: ").strip()
            if not encrypted_id:
                print("❌ 加密ID不能为空！")
                continue
            try:
                decrypted = decrypt_robot_id(encrypted_id)
                print()
                print("✅ 解密成功！")
                print(f"   加密ID:   {encrypted_id}")
                print(f"   真实ID:   {decrypted}")
                print()
            except ValueError as e:
                print(f"❌ 解密失败: {e}")
                print()

        elif choice == "3":
            print("再见！")
            break

        else:
            print("❌ 无效选项，请输入 1、2 或 3")
            print()


if __name__ == "__main__":
    main()

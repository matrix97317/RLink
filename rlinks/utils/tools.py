# -*- coding: utf-8 -*-
"""RLink Tools."""

import re
import uuid
import socket
import asyncio

import requests


def is_valid_ip(ip_str):
    """检查字符串是否为有效的IPv4地址"""
    pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return bool(re.match(pattern, ip_str))


def run_async(func):
    """装饰器：自动运行异步函数"""

    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def get_my_ip_safe() -> str:
    """
    安全获取本机IP地址
    """
    # 方法1: 尝试获取公网IP
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=2)
        if response.status_code == 200:
            return response.json()["ip"]
    except BaseException:
        pass

    # 方法2: 尝试获取私有IP
    try:
        # 创建一个临时socket连接
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        # 连接一个外部地址但不发送数据
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except BaseException:
        pass

    # 方法3: 回退到默认值
    return "127.0.0.1"


def get_ip_based_uuid_v3(ip_address: str = None, namespace: str = "myapp") -> str:
    """
    使用 UUID v3 基于 IP 生成 UUID
    v3 使用 MD5 哈希
    """
    if ip_address is None:
        ip_address = get_my_ip_safe()
    namespace_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, namespace)
    ip_uuid = uuid.uuid3(namespace_uuid, ip_address)

    return str(ip_uuid) + f"_{ip_address}"


if __name__ == "__main__":
    # 测试用例
    test_ips = [
        "192.168.1.1",  # 有效
        "255.255.255.255",  # 有效
        "0.0.0.0",  # 有效
        "256.0.0.1",  # 无效 - 超过255
        "192.168.1",  # 无效 - 只有3段
        "192.168.1.1.1",  # 无效 - 有5段
        "192.168.01.1",  # 无效 - 有前导零（通常不允许）
        "abc.def.ghi.jkl",  # 无效 - 非数字
    ]

    for ip in test_ips:
        print(f"{ip}: {is_valid_ip(ip)}")

    print("ip ", get_ip_based_uuid_v3())

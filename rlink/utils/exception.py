# -*- coding: utf-8 -*-
"""RLink Exceptions."""

import sys


class FileNotFoundExitError(FileNotFoundError):
    """自定义文件未找到异常, 抛出后退出程序"""

    def __init__(self, message):
        super().__init__(message)
        print(f"{message} does not exist.")
        sys.exit(1)


class ValueWithExitError(Exception):
    """自定义值错误异常, 抛出后退出程序

    Args:
        Exception (Exception): _description_
    """

    def __init__(self, message):
        super().__init__(message)
        print(f"{message}. value is invalid.")
        sys.exit(1)


class InitWithExitError(Exception):
    """自定义初始化异常, 抛出后退出程序
    Args:
        Exception (Exception): _description_
    """

    def __init__(self, message):
        super().__init__(message)
        print(f"{message} init failed.")
        sys.exit(1)

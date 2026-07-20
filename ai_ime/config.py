# -*- coding: utf-8 -*-
"""AI 输入法 - 全局配置

集中管理路径、常量、调试开关。
路径解析基于本文件位置（ai_ime/config.py），开发态和部署态通用。
"""
import os

# ===== 调试 =====
# 写按键回调日志到 PIME 日志目录，方便验证输入法是否被触发
DEBUG_LOG = True

# ===== 候选显示 =====
MAX_CANDIDATES = 9        # 候选词最大数量（保留兼容，实际用 PAGE_SIZE）
SEL_KEYS = "123456789"    # 选词键（数字键 1-9 对应候选 1-9）

# ===== 翻页 =====
PAGE_SIZE = 9             # 每页候选数（与 SEL_KEYS 对齐）
MAX_TOTAL_CANDIDATES = 200  # 全部候选上限（防止极端简拼返回过多，如 'a' 简拼）

# ===== 翻页键虚拟键码（VK_OEM_*）=====
VK_OEM_MINUS = 0xBD       # '-' 键（上一页）
VK_OEM_PLUS = 0xBB        # '=' 键（下一页；Shift+= 才是 +，但 VK 不受 Shift 影响）

# ===== 中文标点全角化（输入法激活时自动转换）=====
# 仅在非组合状态下拦截标点键；组合中（输入拼音时）不拦截
# 代码常用符号（{} [] | * 等）保留半角，避免影响编程
PUNCTUATION_MAP = {
    ",": "\uff0c",   # ,  → ，
    ".": "\u3002",   # .  → 。
    "?": "\uff1f",   # ?  → ？
    "!": "\uff01",   # !  → ！
    ":": "\uff1a",   # :  → ：
    ";": "\uff1b",   # ;  → ；
    "(": "\uff08",   # (  → （
    ")": "\uff09",   # )  → ）
    "<": "\u300a",   # <  → 《
    ">": "\u300b",   # >  → 》
    "\\": "\u3001",  # \  → 、
    "$": "\uffe5",   # $  → ￥
    "^": "\u2026\u2026",  # ^ → ……（成对省略号）
    "\"": "\u201c",  # "  → "（左双引号；配对逻辑较复杂，第1期简化为左引号）
    "'": "\u2018",   # '  → '（左单引号）
    "[": "\u3010",   # [  → 【
    "]": "\u3011",   # ]  → 】
}
# 注意：以下符号保留半角（代码/URL 常用）
# - _ = + / ` ~ @ # % & * { } | 数字

# ===== 路径（基于本文件位置，开发/部署通用）=====
# 本文件所在目录（ai_ime/）
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据目录（ai_ime/data/）
DATA_DIR = os.path.join(PACKAGE_DIR, "data")

# 基础词库文件（第1期使用）
DICT_PATH = os.path.join(DATA_DIR, "base_dict.txt")

# 用户词频记忆文件（JSON 持久化）
USER_MEMORY_PATH = os.path.join(DATA_DIR, "user_memory.json")

# ===== 日志（PIME 标准日志位置）=====
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PIME", "Log")
LOG_FILE = os.path.join(LOG_DIR, "ai_ime_debug.log")


def get_dict_path():
    """返回基础词库的绝对路径"""
    return DICT_PATH


def get_data_dir():
    """返回数据目录的绝对路径"""
    return DATA_DIR

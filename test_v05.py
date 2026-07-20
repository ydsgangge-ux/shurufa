# -*- coding: utf-8 -*-
"""AI 输入法 v0.5 单元测试

测试内容：
1. 词库加载 + 常用词覆盖
2. 全拼输入（changyong → 常用）
3. 混合简拼（changy → 常用, cyong → 常用）
4. 纯简拼（n → 你, nh → 你好）
5. 中文标点全角化
6. 用户词频记忆
7. 性能测试
"""
import os
import sys
import time
import tempfile

# 设置路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_ime"))

from ai_ime import config
from ai_ime.pinyin.dict_loader import DictLoader
from ai_ime.pinyin.candidates import get_candidates
from ai_ime.pinyin.parser import mixed_split
from ai_ime.user_memory import UserMemory


def test_dict_load():
    """测试 1: 词库加载"""
    print("=== 测试 1: 词库加载 ===")
    loader = DictLoader()
    t0 = time.time()
    loader.load(config.get_dict_path())
    t1 = time.time()
    size = loader.size()
    assert size > 100000, "词库条数过少: {}".format(size)
    print("  OK 加载 {} 条, {:.0f}ms".format(size, (t1 - t0) * 1000))
    return loader


def test_full_pinyin(loader):
    """测试 2: 全拼输入"""
    print("\n=== 测试 2: 全拼输入 ===")
    cases = [
        ("changyong", "常用"),
        ("xianzai", "现在"),
        ("nihao", "你好"),
        ("jintian", "今天"),
        ("pengyou", "朋友"),
        ("dianzi", "电子"),
    ]
    for inp, expected in cases:
        r = get_candidates(inp, loader, 200)
        assert expected in r, "{} 未命中 {}".format(inp, expected)
        print("  OK {} -> first={}, {} in results".format(inp, r[0], expected))


def test_mixed_simplified(loader):
    """测试 3: 混合简拼（全拼+首字母）"""
    print("\n=== 测试 3: 混合简拼 ===")
    cases = [
        ("changy", "常用"),   # chang + y
        ("cyong", "常用"),    # c + yong
        ("xianz", "现在"),    # xian + z
        ("jint", "今天"),     # jin + t
    ]
    for inp, expected in cases:
        parts = mixed_split(inp)
        r = get_candidates(inp, loader, 200)
        assert expected in r, "{} (parts={}) 未命中 {}".format(inp, parts, expected)
        print("  OK {} parts={} -> first={}, {} in results".format(
            inp, parts, r[0], expected))


def test_pure_simplified(loader):
    """测试 4: 纯简拼（首字母序列）"""
    print("\n=== 测试 4: 纯简拼 ===")
    cases = [
        ("n", "你"),
        ("nh", "你好"),
        ("xz", "现在"),
    ]
    for inp, expected in cases:
        r = get_candidates(inp, loader, 200)
        assert expected in r, "{} 未命中 {}".format(inp, expected)
        print("  OK {} -> first={}, {} in results".format(inp, r[0], expected))


def test_punctuation():
    """测试 5: 中文标点全角化"""
    print("\n=== 测试 5: 中文标点全角化 ===")
    cases = [
        (",", "，"),
        (".", "。"),
        ("?", "？"),
        ("!", "！"),
        (":", "："),
        (";", "；"),
        ("(", "（"),
        (")", "）"),
        ("<", "《"),
        (">", "》"),
        ("\\", "、"),
        ("[", "【"),
        ("]", "】"),
    ]
    for half, expected in cases:
        full = config.PUNCTUATION_MAP.get(half)
        assert full == expected, "{} -> {} (期望 {})".format(half, full, expected)
        print("  OK {} -> {}".format(half, full))


def test_user_memory(loader):
    """测试 6: 用户词频记忆"""
    print("\n=== 测试 6: 用户词频记忆 ===")
    # 用临时文件测试
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        tmp_path = f.name
    try:
        mem = UserMemory(tmp_path)
        # 测试 record 和 get_bonus
        mem.record("手机")
        assert mem.get_bonus("手机") == 100, "bonus 应为 100"
        mem.record("手机")
        assert mem.get_bonus("手机") == 200, "bonus 应为 200"
        print("  OK record 累加: 手机 -> bonus={}".format(mem.get_bonus("手机")))

        # 测试 apply_bonus
        candidates = [("收集", 1603), ("手机", 4789), ("首级", 394)]
        result = mem.apply_bonus(candidates)
        # 手机 4789 + 200 = 4989, 收集 1603 + 0 = 1603
        assert result[0][0] == "手机", "手机应排第一"
        assert result[0][1] == 4989, "有效词频应为 4989"
        print("  OK apply_bonus: {} -> first={}".format(
            [(w, f) for w, f in result], result[0][0]))

        # 测试持久化
        mem2 = UserMemory(tmp_path)
        assert mem2.get_bonus("手机") == 200, "持久化后 bonus 应保留"
        print("  OK 持久化: 重载后手机 bonus={}".format(mem2.get_bonus("手机")))
    finally:
        os.unlink(tmp_path)


def test_performance(loader):
    """测试 7: 性能测试"""
    print("\n=== 测试 7: 性能测试 ===")
    cases = ["changyong", "changy", "cyong", "n", "nh", "xianzai", "xz"]
    for inp in cases:
        t0 = time.time()
        for _ in range(100):
            get_candidates(inp, loader, 200)
        t1 = time.time()
        avg_ms = (t1 - t0) * 10  # 100次平均，每次ms
        print("  {} -> {:.2f}ms/次".format(inp, avg_ms))
        assert avg_ms < 50, "{} 性能过慢: {:.2f}ms".format(inp, avg_ms)


def main():
    print("AI 输入法 v0.5 单元测试\n")
    loader = test_dict_load()
    test_full_pinyin(loader)
    test_mixed_simplified(loader)
    test_pure_simplified(loader)
    test_punctuation()
    test_user_memory(loader)
    test_performance(loader)
    print("\n=== 全部测试通过 ===")


if __name__ == "__main__":
    main()

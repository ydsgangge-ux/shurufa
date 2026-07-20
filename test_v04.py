# -*- coding: utf-8 -*-
"""AI 输入法 v0.4 单元测试"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_ime"))

from ai_ime.pinyin.dict_loader import DictLoader
from ai_ime.pinyin.candidates import get_candidates
from ai_ime import config


def main():
    print("=" * 60)
    print("AI 输入法 v0.4 单元测试")
    print("=" * 60)

    # 加载词库
    loader = DictLoader()
    t0 = time.time()
    loader.load(config.get_dict_path())
    t1 = time.time()
    print("\n[加载] 词库: {} 条, 耗时: {:.0f}ms".format(loader.size(), (t1 - t0) * 1000))
    assert loader.size() > 70000, "词库条数应 > 70000"

    print("\n--- dict_loader 测试 ---")

    # 测试 1: lookup_initial
    r = loader.lookup_initial("n")
    print("1. lookup_initial(n) 第一项:", r[0])
    assert r[0] == ("你", 925), "lookup_initial(n) 第一项应为 (你, 925)"
    print("   PASS")

    # 测试 2: lookup_phrase_initial
    r = loader.lookup_phrase_initial("nh")
    words = [w for w, f in r]
    print("2. lookup_phrase_initial(nh) 含你好:", "你好" in words, "| 前3:", r[:3])
    assert "你好" in words, "lookup_phrase_initial(nh) 应含 你好"
    print("   PASS")

    print("\n--- candidates 测试 ---")

    # 测试 3: 单字母简拼
    r = get_candidates("n", loader, 200)
    print("3. get_candidates(n) 第一项:", r[0])
    assert r[0] == "你", "get_candidates(n) 第一项应为 你"
    print("   PASS")

    # 测试 4: 多字母简拼
    r = get_candidates("nh", loader, 200)
    print("4. get_candidates(nh) 含你好:", "你好" in r, "| 前3:", r[:3])
    assert "你好" in r, "get_candidates(nh) 应含 你好"
    print("   PASS")

    # 测试 5: 全拼优先
    r = get_candidates("nihao", loader, 200)
    print("5. get_candidates(nihao):", r[:3])
    assert "你好" in r, "get_candidates(nihao) 应含 你好"
    print("   PASS")

    # 测试 6: 词组简拼 xz -> 现在
    r = get_candidates("xz", loader, 200)
    print("6. get_candidates(xz) 含现在:", "现在" in r, "| 前3:", r[:3])
    assert "现在" in r, "get_candidates(xz) 应含 现在"
    print("   PASS")

    # 测试 7: 词组全拼 xianzai -> 现在
    r = get_candidates("xianzai", loader, 200)
    print("7. get_candidates(xianzai):", r[:3])
    assert "现在" in r, "get_candidates(xianzai) 应含 现在"
    print("   PASS")

    # 测试 8: 合法单字母音节 a -> 啊
    r = get_candidates("a", loader, 200)
    print("8. get_candidates(a) 含啊:", "啊" in r, "| 前3:", r[:3])
    assert "啊" in r, "get_candidates(a) 应含 啊"
    print("   PASS")

    # 测试 9: 含空格输入
    r = get_candidates("ni hao", loader, 200)
    print("9. get_candidates(ni hao):", r[:3])
    assert "你好" in r, "get_candidates(ni hao) 应含 你好"
    print("   PASS")

    # 测试 10: echo fallback
    r = get_candidates("zzz", loader, 200)
    print("10. get_candidates(zzz):", r)
    assert r == ["zzz"], "get_candidates(zzz) 应 echo 返回 [zzz]"
    print("   PASS")

    # 测试 11: 候选数量上限
    r = get_candidates("n", loader, 200)
    print("11. get_candidates(n) 候选数:", len(r), "(应 <= 200)")
    assert len(r) <= 200, "候选数应 <= 200"
    print("   PASS")

    print("\n--- 翻页逻辑测试（模拟切片）---")
    PAGE_SIZE = config.PAGE_SIZE
    all_cands = get_candidates("n", loader, 200)
    total = len(all_cands)
    max_page = max(0, (total - 1) // PAGE_SIZE)
    print("12. n 简拼候选总数:", total, "| 每页:", PAGE_SIZE, "| 最大页码:", max_page)
    print("    第0页:", all_cands[0:PAGE_SIZE])
    print("    第1页:", all_cands[PAGE_SIZE:PAGE_SIZE * 2])
    if max_page >= 1:
        print("    第{}页(末页):".format(max_page),
              all_cands[max_page * PAGE_SIZE:(max_page + 1) * PAGE_SIZE])
    assert max_page >= 1, "n 简拼应有多页"
    print("   PASS")

    print("\n" + "=" * 60)
    print("全部 12 项测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()

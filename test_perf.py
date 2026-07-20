# -*- coding: utf-8 -*-
"""测试新词库 v0.3 的加载性能和查询性能"""
import time
import sys
sys.path.insert(0, "d:/AI软件/测试/shurufa/ai_ime")

from pinyin.dict_loader import DictLoader
from pinyin.candidates import get_candidates

# 1. 加载性能测试
print("=== 1. 加载性能测试 ===")
loader = DictLoader()
start = time.time()
loader.load("d:/AI软件/测试/shurufa/ai_ime/data/base_dict.txt.new")
elapsed = time.time() - start
print("加载时间: {:.3f}s".format(elapsed))
print("词条数: {}".format(loader.size()))

# 2. 查询性能测试
print("\n=== 2. 查询性能测试 ===")
tests = ["ni", "xian", "nihao", "shi", "zhongguo", "de", "kan", "abc", "z", "a"]
for k in tests:
    start = time.time()
    cands = get_candidates(k, loader, 9)
    elapsed = time.time() - start
    print("  {} -> {} ({:.2f}ms)".format(k, cands[:3] if len(cands) > 3 else cands, elapsed * 1000))

# 3. 内存占用估算
print("\n=== 3. 索引规模 ===")
print("索引键数: {}".format(len(loader._index)))

# 4. 对比旧词库
print("\n=== 4. 对比旧词库（342 条）===")
loader_old = DictLoader()
start = time.time()
loader_old.load("d:/AI软件/测试/shurufa/ai_ime/data/base_dict.txt")
elapsed = time.time() - start
print("旧词库加载时间: {:.3f}s".format(elapsed))
print("旧词库词条数: {}".format(loader_old.size()))

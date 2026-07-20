# -*- coding: utf-8 -*-
"""拼音解析、词库加载、候选生成的单元测试

可独立运行（不依赖 PIME）：
    python -m unittest ai_ime.pinyin.tests.test_parser -v
或在项目根目录：
    python -m pytest ai_ime/pinyin/tests/ -v
"""
import os
import sys
import unittest

# 注入 ai_ime 包路径，让 from pinyin.X import 和 import config 能工作
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AI_IME_DIR = os.path.dirname(os.path.dirname(_THIS_DIR))  # ai_ime/
if _AI_IME_DIR not in sys.path:
    sys.path.insert(0, _AI_IME_DIR)

from pinyin.parser import split_pinyin, best_split
from pinyin.dict_loader import DictLoader
from pinyin.candidates import get_candidates
from pinyin.syllables import VALID_SYLLABLES, MAX_SYLLABLE_LEN
import config


class TestSyllables(unittest.TestCase):
    """合法音节表测试"""

    def test_syllables_count(self):
        # 约 400 个音节
        self.assertGreater(len(VALID_SYLLABLES), 350)
        self.assertLess(len(VALID_SYLLABLES), 450)

    def test_max_syllable_len(self):
        self.assertEqual(MAX_SYLLABLE_LEN, 6)  # zhuang, chuang, shuang

    def test_common_syllables_exist(self):
        for syl in ["a", "yi", "wu", "ba", "ma", "de", "ni", "hao", "zhong", "guo", "xian", "zhuang"]:
            self.assertIn(syl, VALID_SYLLABLES, "缺失音节: " + syl)

    def test_invalid_syllables_not_exist(self):
        for syl in ["ab", "cd", "ef", "gh", "q", "x", "v", "kkk"]:
            self.assertNotIn(syl, VALID_SYLLABLES)


class TestParser(unittest.TestCase):
    """拼音切分测试"""

    def test_empty(self):
        self.assertEqual(split_pinyin(""), [[]])

    def test_single_syllable(self):
        self.assertEqual(split_pinyin("a"), [["a"]])
        # "yi" 只有一种切分（y 不是音节，yi 是）
        self.assertIn(["yi"], split_pinyin("yi"))
        # "hao" 有歧义切分（ha+o 也合法），但 hao 应该在结果中
        self.assertIn(["hao"], split_pinyin("hao"))

    def test_multi_syllable_nihao(self):
        # nihao 有多种切分（ni+ha+o 也合法），但 ni+hao 应该在结果中
        self.assertIn(["ni", "hao"], split_pinyin("nihao"))

    def test_ambiguous_xian(self):
        # xian 可切为 xian 或 xi+an
        splits = split_pinyin("xian")
        self.assertIn(["xian"], splits)
        self.assertIn(["xi", "an"], splits)
        self.assertEqual(len(splits), 2)

    def test_ambiguous_fangan(self):
        # fangan 可切为 fan+gan 或 fang+an（fang+gan 不可能，因 fang 占 4 字符后只剩 'an'）
        splits = split_pinyin("fangan")
        self.assertIn(["fan", "gan"], splits)
        self.assertIn(["fang", "an"], splits)

    def test_non_alpha_fallback(self):
        # 含非字母字符，原样返回
        self.assertEqual(split_pinyin("hello"), [["hello"]])  # h,e,l,l,o 无法切分
        self.assertEqual(split_pinyin("abc123"), [["abc123"]])
        self.assertEqual(split_pinyin("nihao1"), [["nihao1"]])

    def test_no_valid_split_fallback(self):
        # q 不是合法音节，无法切分
        self.assertEqual(split_pinyin("q"), [["q"]])
        self.assertEqual(split_pinyin("qxz"), [["qxz"]])

    def test_best_split_prefers_longer(self):
        # best_split 偏好音节数少（长音节）
        self.assertEqual(best_split("nihao"), ["ni", "hao"])
        self.assertEqual(best_split("xian"), ["xian"])  # 1 音节优于 2 音节

    def test_best_split_deterministic(self):
        # fangan 两种切分都是 2 音节，字典序小的优先
        self.assertEqual(best_split("fangan"), ["fan", "gan"])  # fan < fang

    def test_long_input(self):
        # 长输入能正确切分
        splits = split_pinyin("woaizhongguo")
        self.assertIn(["wo", "ai", "zhong", "guo"], splits)
        self.assertEqual(best_split("woaizhongguo"), ["wo", "ai", "zhong", "guo"])

    def test_uppercase_fallback(self):
        # 大写字母 fallback（输入法层已转小写，这里测试健壮性）
        self.assertEqual(split_pinyin("NIHAO"), [["NIHAO"]])


class TestDictLoader(unittest.TestCase):
    """词库加载测试"""

    @classmethod
    def setUpClass(cls):
        cls.loader = DictLoader()
        cls.dict_path = config.get_dict_path()
        cls.loader.load(cls.dict_path)

    def test_loaded(self):
        self.assertTrue(self.loader.is_loaded(), "词库未加载: " + self.dict_path)
        self.assertGreater(self.loader.size(), 100, "词库条目过少")

    def test_lookup_multi_syllable_space(self):
        # 空格分隔查询
        result = self.loader.lookup("ni hao")
        self.assertTrue(any(w == "你好" for w, f in result), "未找到 '你好'")

    def test_lookup_multi_syllable_concat(self):
        # 连写查询（应命中空格分隔的词条，因加载器索引了连写形式）
        result = self.loader.lookup("nihao")
        self.assertTrue(any(w == "你好" for w, f in result), "连写查询未命中")

    def test_lookup_single(self):
        result = self.loader.lookup("de")
        self.assertTrue(any(w == "的" for w, f in result))

    def test_lookup_not_found(self):
        result = self.loader.lookup("zzzzz")
        self.assertEqual(result, [])

    def test_lookup_sorted_by_freq(self):
        # 结果应按词频降序
        result = self.loader.lookup("shi")
        freqs = [f for w, f in result]
        self.assertEqual(freqs, sorted(freqs, reverse=True))

    def test_lookup_dedup(self):
        # 相同 word 去重
        result = self.loader.lookup("nihao")
        words = [w for w, f in result]
        self.assertEqual(len(words), len(set(words)), "存在重复词")


class TestCandidates(unittest.TestCase):
    """候选词生成测试"""

    @classmethod
    def setUpClass(cls):
        cls.loader = DictLoader()
        cls.loader.load(config.get_dict_path())

    def test_basic_nihao(self):
        cands = get_candidates("nihao", self.loader)
        self.assertIn("你好", cands)
        self.assertEqual(cands[0], "你好")  # 第一个候选应该是"你好"

    def test_concat_input(self):
        cands = get_candidates("nihao", self.loader)
        self.assertIn("你好", cands)

    def test_multi_word_zhongguo(self):
        cands = get_candidates("zhongguo", self.loader)
        self.assertIn("中国", cands)

    def test_echo_fallback(self):
        # 词库无命中，返回原输入
        cands = get_candidates("zzzzz", self.loader)
        self.assertEqual(cands, ["zzzzz"])

    def test_empty(self):
        cands = get_candidates("", self.loader)
        self.assertEqual(cands, [])

    def test_max_n(self):
        cands = get_candidates("shi", self.loader, max_n=3)
        self.assertLessEqual(len(cands), 3)

    def test_long_sentence(self):
        cands = get_candidates("woaizhongguo", self.loader)
        # 应该能匹配或 fallback，不报错
        self.assertIsInstance(cands, list)
        self.assertGreater(len(cands), 0)

    def test_space_separated_input(self):
        # 带空格的输入也能处理
        cands = get_candidates("ni hao", self.loader)
        self.assertIn("你好", cands)


if __name__ == "__main__":
    unittest.main(verbosity=2)

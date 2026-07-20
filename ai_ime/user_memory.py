# -*- coding: utf-8 -*-
"""用户词频记忆 + 用户造词（JSON 持久化）

功能：
1. 词频加成：每次选用一个词，bonus_freq += 100，下次排序提前
2. 用户造词：用户选用的词组如果不在基础词库中，自动保存为新词
   - 保存拼音、汉字、词频
   - 下次输入相同拼音或首字母简拼时能找到

JSON 格式：
{
  "freq": {"你好": 200, "中国": 100},
  "phrases": [
    {"pinyin": "song huo dan", "word": "送货单", "freq": 100}
  ]
}

向后兼容：旧格式（纯 dict）自动迁移为 {"freq": old_dict, "phrases": []}
"""
import os
import json


class UserMemory:
    """用户词频记忆 + 用户造词"""

    def __init__(self, path):
        self.path = path
        self._freq = {}      # {word: bonus_freq}
        self._phrases = []   # [{"pinyin": ..., "word": ..., "freq": ...}, ...]
        self._load()

    def _load(self):
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if "freq" in data:
                    # 新格式
                    self._freq = data.get("freq", {})
                    self._phrases = data.get("phrases", [])
                else:
                    # 旧格式兼容：纯 {word: freq} dict
                    self._freq = data
                    self._phrases = []
        except Exception:
            self._freq = {}
            self._phrases = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"freq": self._freq, "phrases": self._phrases},
                          f, ensure_ascii=False)
        except Exception:
            pass

    def record(self, word):
        """记录用户选用了一个词（词频加成）"""
        if not word:
            return
        self._freq[word] = self._freq.get(word, 0) + 100
        self._save()

    def add_phrase(self, pinyin, word):
        """添加用户造词

        如果该词已存在，增加词频；否则新增。
        初始词频设为较高值，确保一次造词就能排在前面。

        Args:
            pinyin: 空格分隔拼音（如 "song huo dan"）
            word: 汉字（如 "送货单"）
        """
        if not pinyin or not word:
            return 0
        for entry in self._phrases:
            if entry["pinyin"] == pinyin and entry["word"] == word:
                entry["freq"] += 500
                self._save()
                return entry["freq"]
        # 新造词：给一个高词频，确保排第一
        self._phrases.append({"pinyin": pinyin, "word": word, "freq": 9999})
        self._save()
        return 9999

    def get_phrases(self):
        """返回所有用户造词列表"""
        return list(self._phrases)

    def get_bonus(self, word):
        """返回用户词频加成"""
        return self._freq.get(word, 0)

    def apply_bonus(self, candidates):
        """对候选列表应用用户词频加成并重新排序"""
        if not candidates:
            return candidates
        result = []
        for word, freq in candidates:
            bonus = self._freq.get(word, 0)
            result.append((word, freq + bonus))
        result.sort(key=lambda x: -x[1])
        return result

# -*- coding: utf-8 -*-
"""用户词频记忆 + 用户造词 + 词序转移表（JSON 持久化）

功能：
1. 词频加成：每次选用一个词，bonus_freq += 100，下次排序提前
2. 用户造词：用户选用的词组如果不在基础词库中，自动保存为新词
   - 保存拼音、汉字、词频
   - 下次输入相同拼音或首字母简拼时能找到
3. 词序转移表（BigramMemory）：记录"上一个词→下一个词"的出现频次
   - 用于零延迟续写预测：上屏后立即查表，给出下一个大概率想打的词
   - 本质是一阶马尔可夫链，key=上一个词，value={下一个词: count}
   - 自然频次累加，不人为给高权重，抗噪
   - 带衰减机制，老旧搭配自然淘汰

JSON 格式：
{
  "freq": {"你好": 200, "中国": 100},
  "phrases": [
    {"pinyin": "song huo dan", "word": "送货单", "freq": 100}
  ],
  "bigram": {
    "绝缘电阻": {"要求": 12, "测试": 5},
    "线束": {"标识": 8, "型号": 6}
  }
}

向后兼容：旧格式（纯 dict / 无 bigram）自动迁移
"""
import os
import json
import time


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


class BigramMemory:
    """词序转移表（一阶马尔可夫链）

    记录"上一个词→下一个词"的出现频次，用于零延迟续写预测。

    存储路径与 UserMemory 同目录，独立文件 bigram.json。
    """

    MAX_NEXT_WORDS = 20       # 每个 prev_word 最多保留的 next_word 数量
    DECAY_FACTOR = 0.9        # 衰减系数
    DECAY_INTERVAL = 86400    # 衰减间隔（秒），默认 1 天
    DECAY_MIN_COUNT = 1       # 低于此值在衰减时删除

    def __init__(self, path):
        self.path = path
        self._data = {}   # {prev_word: {next_word: count}}
        self._last_decay = 0  # 上次衰减时间戳
        self._dirty = False
        self._load()

    def _load(self):
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                ts = data.get("_last_decay", 0)
                self._last_decay = ts
                self._data = {k: v for k, v in data.items()
                              if k != "_last_decay" and isinstance(v, dict)}
        except Exception:
            self._data = {}

    def _save(self):
        if not self._dirty:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            data = dict(self._data)
            data["_last_decay"] = self._last_decay
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self._dirty = False
        except Exception:
            pass

    def record(self, prev_word, next_word):
        """记录一次转移：prev_word → next_word

        Args:
            prev_word: 上一个上屏的词
            next_word: 紧接着上屏的词
        """
        if not prev_word or not next_word:
            return
        if prev_word == next_word:
            return

        self._data.setdefault(prev_word, {})
        self._data[prev_word][next_word] = self._data[prev_word].get(next_word, 0) + 1
        self._dirty = True

        # 超过 MAX_NEXT_WORDS，删掉 count 最低的
        if len(self._data[prev_word]) > self.MAX_NEXT_WORDS:
            sorted_items = sorted(self._data[prev_word].items(), key=lambda x: x[1])
            to_remove = sorted_items[:len(sorted_items) - self.MAX_NEXT_WORDS]
            for w, _ in to_remove:
                del self._data[prev_word][w]

        # 检查是否需要衰减
        now = time.time()
        if now - self._last_decay > self.DECAY_INTERVAL:
            self._decay()
            self._last_decay = now

        self._save()

    def undo(self, prev_word, next_word):
        """撤销一次转移（用户上屏后立即退格重打时调用）

        将 count 减 1，减到 0 则删除。
        """
        if not prev_word or not next_word:
            return
        if prev_word not in self._data:
            return
        if next_word not in self._data[prev_word]:
            return
        self._data[prev_word][next_word] -= 1
        if self._data[prev_word][next_word] <= 0:
            del self._data[prev_word][next_word]
        if not self._data[prev_word]:
            del self._data[prev_word]
        self._dirty = True
        self._save()

    def lookup(self, prev_word, top_n=5):
        """查询续写候选

        Args:
            prev_word: 上一个上屏的词
            top_n: 返回最多几个候选

        Returns:
            [(next_word, count), ...] 按 count 降序，最多 top_n 个；无命中返回 []
        """
        if not prev_word or prev_word not in self._data:
            return []
        items = sorted(self._data[prev_word].items(), key=lambda x: -x[1])
        return items[:top_n]

    def _decay(self):
        """衰减：所有 count 乘 DECAY_FACTOR，低于 DECAY_MIN_COUNT 的删除"""
        to_delete_prev = []
        for prev_word in list(self._data.keys()):
            to_delete_next = []
            for next_word in list(self._data[prev_word].keys()):
                new_count = self._data[prev_word][next_word] * self.DECAY_FACTOR
                if new_count < self.DECAY_MIN_COUNT:
                    to_delete_next.append(next_word)
                else:
                    self._data[prev_word][next_word] = int(new_count)
            for w in to_delete_next:
                del self._data[prev_word][w]
            if not self._data[prev_word]:
                to_delete_prev.append(prev_word)
        for w in to_delete_prev:
            del self._data[w]
        self._dirty = True

# -*- coding: utf-8 -*-
"""词库加载器

词库格式（UTF-8, Tab 分隔, 每行一条）：
    <拼音>\t<汉字>\t<词频>

拼音列支持两种写法，加载时同时索引：
    空格分隔多音节：ni hao
    连写：nihao

查找时 lookup() 接受任意一种形式均可命中。

简拼支持：
    lookup_initial(initial) - 单字母简拼（n → 你/倪/...）
    lookup_phrase_initial(initials) - 词组简拼（nh → 你好/女孩/...）
"""
import os


class DictLoader:
    """词库加载与查找

    索引结构：
        _index: {pinyin_key: [(word, freq), ...]}
            pinyin_key 同时存"空格分隔"和"连写"两种形式
        _initial_index: {单字母: [(单字, freq), ...]}
            仅收录单字（len(word)==1），键为拼音首字母
        _phrase_initial_index: {首字母序列: [(词组, freq), ...]}
            仅收录词组（len(word)>=2），键为各音节首字母连写（如 'nh'）
            仅对空格分隔拼音列构建（连写无法可靠切分）
    """

    def __init__(self):
        self._index = {}  # pinyin_key -> list of (word, freq)
        self._initial_index = {}  # 单字母 -> list of (单字, freq)
        self._phrase_initial_index = {}  # 首字母序列 -> list of (词组, freq)
        self._word_pinyin_index = {}  # word -> set of pinyin_key（仅空格分隔键，用于混合简拼反查）
        self._entry_count = 0
        self._loaded = False

    def load(self, path):
        """从文件加载词库

        Args:
            path: 词库文件路径（UTF-8, Tab 分隔）
        """
        self._index.clear()
        self._initial_index.clear()
        self._phrase_initial_index.clear()
        self._word_pinyin_index.clear()
        self._entry_count = 0

        if not os.path.isfile(path):
            self._loaded = False
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n").rstrip("\r")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                pinyin = parts[0].strip()
                word = parts[1].strip()
                if not pinyin or not word:
                    continue
                freq = 0
                if len(parts) >= 3:
                    try:
                        freq = int(parts[2].strip())
                    except ValueError:
                        freq = 0

                # 标准化：去空格得到连写形式
                pinyin_no_space = pinyin.replace(" ", "")
                # 两种键都指向同一候选
                self._index.setdefault(pinyin, []).append((word, freq))
                if pinyin_no_space != pinyin:
                    self._index.setdefault(pinyin_no_space, []).append((word, freq))

                # 构建简拼索引
                if len(word) == 1:
                    # 单字：取拼音首字母
                    initial = pinyin_no_space[0] if pinyin_no_space else ""
                    if initial:
                        self._initial_index.setdefault(initial, []).append((word, freq))
                else:
                    # 词组：仅对空格分隔拼音列构建首字母序列
                    if " " in pinyin:
                        syllables = pinyin.split()
                        initials = "".join(s[0] for s in syllables if s)
                        if initials:
                            self._phrase_initial_index.setdefault(initials, []).append((word, freq))
                        # 同时构建反向索引：word -> set of pinyin_key（用于混合简拼反查）
                        self._word_pinyin_index.setdefault(word, set()).add(pinyin)

                self._entry_count += 1

        # 对每个键的候选按词频降序排序
        for key in self._index:
            self._index[key].sort(key=lambda x: -x[1])
        for key in self._initial_index:
            self._initial_index[key].sort(key=lambda x: -x[1])
        for key in self._phrase_initial_index:
            self._phrase_initial_index[key].sort(key=lambda x: -x[1])

        self._loaded = True

    def lookup(self, pinyin_str):
        """查找候选词

        Args:
            pinyin_str: 拼音串（空格分隔或连写均可）

        Returns:
            [(word, freq), ...] 按词频降序，相同 word 已去重保留最高词频；无命中返回 []
        """
        if not pinyin_str:
            return []
        key = pinyin_str.strip()
        raw = self._index.get(key)
        if raw is None:
            # 尝试连写形式
            no_space = key.replace(" ", "")
            if no_space != key:
                raw = self._index.get(no_space)
        if not raw:
            return []
        # 去重：相同 word 只保留词频最高的（防止词库重复词条）
        seen = {}
        for word, freq in raw:
            if word not in seen or freq > seen[word]:
                seen[word] = freq
        return sorted(seen.items(), key=lambda x: -x[1])

    def lookup_initial(self, initial):
        """单字母简拼查找

        Args:
            initial: 单字母（如 'n'）

        Returns:
            [(word, freq), ...] 按词频降序，所有以该字母开头的单字；
            无命中返回 []。
        """
        if not initial:
            return []
        raw = self._initial_index.get(initial)
        if not raw:
            return []
        # 去重（同一字可能因多音字出现多次）
        seen = {}
        for word, freq in raw:
            if word not in seen or freq > seen[word]:
                seen[word] = freq
        return sorted(seen.items(), key=lambda x: -x[1])

    def lookup_phrase_initial(self, initials_str):
        """词组首字母序列简拼查找

        Args:
            initials_str: 首字母序列连写（如 'nh'）

        Returns:
            [(word, freq), ...] 按词频降序，所有匹配首字母序列的词组；
            无命中返回 []。
        """
        if not initials_str:
            return []
        raw = self._phrase_initial_index.get(initials_str)
        if not raw:
            return []
        # 去重
        seen = {}
        for word, freq in raw:
            if word not in seen or freq > seen[word]:
                seen[word] = freq
        return sorted(seen.items(), key=lambda x: -x[1])

    def lookup_mixed(self, parts):
        """混合简拼查找（全拼音节 + 单字母首字母组合）

        支持如 'changy' → ['chang', 'y'] 这种切分：
        - 'chang' 是完整音节，必须精确匹配词组对应位置的音节
        - 'y' 是单字母，匹配词组对应位置音节的首字母

        匹配策略（优化版，用反向索引）：
        1. 用首字母序列索引过滤候选（快速缩小范围）
        2. 对每个候选 word，用 _word_pinyin_index 反查其所有拼音键
        3. 验证完整音节部分是否精确匹配

        Args:
            parts: mixed_split 的结果，如 ['chang', 'y']

        Returns:
            [(word, freq), ...] 按词频降序；无命中返回 []。
        """
        if not parts:
            return []

        # 只对含至少一个完整音节（len>=2）的混合切分查询
        has_full_syllable = any(len(p) >= 2 for p in parts)
        if not has_full_syllable:
            return []

        # 构建首字母序列（用于索引过滤）
        initials = "".join(p[0] for p in parts)
        candidates = self._phrase_initial_index.get(initials, [])

        # 对每个候选 word，反查其拼音键并验证
        results = []
        for word, freq in candidates:
            pinyin_keys = self._word_pinyin_index.get(word, set())
            for key in pinyin_keys:
                syllables = key.split()
                if len(syllables) != len(parts):
                    continue
                # 验证每个位置：完整音节必须精确匹配，单字母部分已由首字母索引保证
                ok = True
                for syll, part in zip(syllables, parts):
                    if len(part) >= 2 and syll != part:
                        ok = False
                        break
                if ok:
                    results.append((word, freq))
                    break  # 一个 word 匹配一次即可

        if not results:
            return []
        # 去重并按词频降序
        seen = {}
        for word, freq in results:
            if word not in seen or freq > seen[word]:
                seen[word] = freq
        return sorted(seen.items(), key=lambda x: -x[1])

    def add_entry(self, pinyin, word, freq):
        """动态添加词条（用户造词时调用）

        同时更新主索引、简拼索引、首字母索引，与 load() 一致。
        添加后对受影响的键重新排序。

        Args:
            pinyin: 空格分隔拼音（如 "song huo dan"）
            word: 汉字（如 "送货单"）
            freq: 词频
        """
        pinyin_no_space = pinyin.replace(" ", "")

        # 主索引（空格分隔 + 连写）
        self._index.setdefault(pinyin, []).append((word, freq))
        if pinyin_no_space != pinyin:
            self._index.setdefault(pinyin_no_space, []).append((word, freq))

        # 简拼索引
        if len(word) == 1:
            initial = pinyin_no_space[0] if pinyin_no_space else ""
            if initial:
                self._initial_index.setdefault(initial, []).append((word, freq))
        else:
            if " " in pinyin:
                syllables = pinyin.split()
                initials = "".join(s[0] for s in syllables if s)
                if initials:
                    self._phrase_initial_index.setdefault(initials, []).append((word, freq))
                self._word_pinyin_index.setdefault(word, set()).add(pinyin)

        self._entry_count += 1

        # 重新排序受影响的键
        for key in [pinyin, pinyin_no_space]:
            if key in self._index:
                self._index[key].sort(key=lambda x: -x[1])
        if len(word) == 1:
            initial = pinyin_no_space[0] if pinyin_no_space else ""
            if initial and initial in self._initial_index:
                self._initial_index[initial].sort(key=lambda x: -x[1])
        elif " " in pinyin:
            syllables = pinyin.split()
            initials = "".join(s[0] for s in syllables if s)
            if initials and initials in self._phrase_initial_index:
                self._phrase_initial_index[initials].sort(key=lambda x: -x[1])

    def is_loaded(self):
        return self._loaded

    def size(self):
        """返回词条总数"""
        return self._entry_count

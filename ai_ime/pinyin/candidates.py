# -*- coding: utf-8 -*-
"""候选词生成器

策略（按优先级）：
1. 全拼切分匹配：best_split → 词库 lookup
2. 其他切分匹配：遍历 split_pinyin
3. 混合简拼 fallback
4. 贪心分词匹配（长词组）：整体无匹配时，贪心切分音节序列，每段匹配最长词组
5. echo fallback
"""
from .parser import best_split, split_pinyin, mixed_split
from .syllables import VALID_SYLLABLES


def _greedy_segment(syllables, dict_loader):
    """贪心分词匹配：从左到右，优先匹配双字词，无法匹配时降级为单字

    ABC 输入法习惯：优先匹配 2 音节词组（双字词），剩余音节匹配单字。
    例：['song','huo','dan'] → 送货 + 单 = 送货单
        ['song','huo','dan','fa','gei','wo'] → 送货 + 单发 + 给我 = 送货单发给我

    Args:
        syllables: 音节列表（如 ['song', 'huo', 'dan']）
        dict_loader: 已加载的 DictLoader 实例

    Returns:
        拼接后的字符串（如 "送货单"），无匹配返回 ""
    """
    n = len(syllables)
    if n == 0:
        return ""

    result_parts = []
    i = 0
    while i < n:
        matched = False
        # 先尝试 2 音节词组（双字词），再降级为单字
        # 不尝试 3+ 音节词组，因为词库匹配结果往往不是用户想要的
        max_len = min(2, n - i)
        for length in range(max_len, 1, -1):  # 2 only
            seg = syllables[i:i + length]
            key = " ".join(seg)
            r = dict_loader.lookup(key)
            if r:
                result_parts.append(r[0][0])  # 取词频最高的词
                i += length
                matched = True
                break
        if not matched:
            # 降级为单字
            key = syllables[i]
            r = dict_loader.lookup(key)
            if r:
                result_parts.append(r[0][0])
            else:
                result_parts.append(key)  # 无匹配时保留拼音
            i += 1

    return "".join(result_parts)


def get_candidates(input_str, dict_loader, max_n=200, with_freq=False):
    """生成候选词列表

    Args:
        input_str: 用户输入的拼音串（如 "nihao" 或 "ni hao"）
        dict_loader: 已加载的 DictLoader 实例
        max_n: 最多返回的候选数（默认 200，由 IME 层分页切片）
        with_freq: 若 True，返回 [(word, freq), ...]；否则返回 [word, ...]

    Returns:
        with_freq=False: 候选词列表 [word, ...]，按词频降序
        with_freq=True: [(word, freq), ...]，按词频降序
    """
    if not input_str:
        return []

    input_str = input_str.strip()
    results = []

    if " " in input_str:
        results = dict_loader.lookup(input_str)
    else:
        best = best_split(input_str)
        pinyin_key = " ".join(best)
        if all(syl in VALID_SYLLABLES for syl in best):
            results = dict_loader.lookup(pinyin_key)
            if not results:
                for split in split_pinyin(input_str):
                    if not all(syl in VALID_SYLLABLES for syl in split):
                        continue
                    key = " ".join(split)
                    if key == pinyin_key:
                        continue
                    results = dict_loader.lookup(key)
                    if results:
                        break

    # 简拼/混合简拼 fallback
    if not results and input_str.isalpha() and input_str.islower():
        if len(input_str) == 1:
            results = dict_loader.lookup_initial(input_str)
        else:
            parts = mixed_split(input_str)
            has_full_syllable = any(len(p) >= 2 for p in parts)
            if has_full_syllable:
                results = dict_loader.lookup_mixed(parts)
                if not results:
                    initials = "".join(p[0] for p in parts)
                    results = dict_loader.lookup_phrase_initial(initials)
            else:
                results = dict_loader.lookup_phrase_initial(input_str)

    # 贪心分词（长词组：始终生成，添加到候选末尾）
    # 对多音节输入，把音节序列分段匹配最长词组拼接（如 songhuodan → 送货+单 → 送货单）
    if input_str.isalpha() and input_str.islower() and len(input_str) > 2:
        syllables = best_split(input_str)
        if len(syllables) >= 2 and all(syl in VALID_SYLLABLES for syl in syllables):
            segmented = _greedy_segment(syllables, dict_loader)
            if segmented and segmented != input_str:
                # 去重：避免与已有候选重复
                if not any(word == segmented for word, freq in results):
                    results.append((segmented, 1))  # 低词频，排在后面，用户选用后会被记忆

    # echo fallback
    if not results:
        if with_freq:
            return [(input_str, 0)]
        return [input_str]

    if with_freq:
        return results[:max_n]
    return [word for word, freq in results[:max_n]]

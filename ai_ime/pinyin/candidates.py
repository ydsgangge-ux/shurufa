# -*- coding: utf-8 -*-
"""候选词生成器 v0.9

搜狗式交互流程：
1. 输入拼音 → 先展示完整句子候选（多种整句解释）
2. 翻页看更多完整句子
3. 翻到底 → 进入分词模式（一个词一个词确认）
4. 分词模式翻到底 → 拆分成更小的词/单字（保底）

generate_interpretations(): 生成多种完整句子解释
get_candidates(): 兼容旧接口
segment_pinyin(): 贪心分词（分词模式用）
get_segments(): 生成分词结构
"""
from .parser import best_split, split_pinyin, mixed_split
from .syllables import VALID_SYLLABLES


def segment_pinyin(syllables, dict_loader):
    """贪心分词：从左到右，优先匹配最长词组，然后降级为单字

    Args:
        syllables: 音节列表（可含单字母简拼）
        dict_loader: DictLoader 实例

    Returns:
        [(pinyin_key, syllables_slice, default_word, [word, ...]), ...]
    """
    n = len(syllables)
    if n == 0:
        return []

    segments = []
    i = 0
    while i < n:
        matched = False
        max_len = min(3, n - i)
        for length in range(max_len, 1, -1):  # 3, 2
            seg = syllables[i:i + length]
            if not all(s in VALID_SYLLABLES for s in seg):
                continue
            key = " ".join(seg)
            r = dict_loader.lookup(key)
            if r:
                words = [w for w, f in r]
                segments.append((key, seg, r[0][0], words))
                i += length
                matched = True
                break
        if not matched:
            key = syllables[i]
            if key in VALID_SYLLABLES:
                r = dict_loader.lookup(key)
                if r:
                    words = [w for w, f in r]
                    segments.append((key, [key], r[0][0], words))
                else:
                    segments.append((key, [key], key, [key]))
            else:
                r = dict_loader.lookup_initial(key)
                if r:
                    words = [w for w, f in r]
                    segments.append((key, [key], r[0][0], words))
                else:
                    segments.append((key, [key], key, [key]))
            i += 1

    return segments


def _get_syllables(input_str):
    """获取输入串的音节列表（全拼或混合简拼）"""
    if not input_str or not input_str.isalpha() or not input_str.islower():
        return []
    syllables = best_split(input_str)
    if len(syllables) < 2 or not all(syl in VALID_SYLLABLES for syl in syllables):
        syllables = mixed_split(input_str)
        if len(syllables) < 2:
            return []
    return syllables


def get_segments(input_str, dict_loader):
    """生成分段确认所需的结构化分词结果"""
    syllables = _get_syllables(input_str)
    if not syllables:
        return []
    return segment_pinyin(syllables, dict_loader)


def generate_interpretations(input_str, dict_loader, max_n=30):
    """生成多种完整句子解释（搜狗式候选）

    策略：
    1. 词库直接匹配的整句
    2. 贪心分词拼出的整句（默认分词）
    3. 拆分多音节段后的替代整句（如 youyidian → "有一点"）
    4. 各段候选词替换产生的变体

    Args:
        input_str: 用户输入的拼音串
        dict_loader: DictLoader 实例
        max_n: 最多返回的候选数

    Returns:
        [(text, freq), ...] 完整句子候选，按优先级降序
    """
    if not input_str or not input_str.isalpha() or not input_str.islower():
        return []

    results = []
    seen = set()

    def _add(text, freq):
        if text and text not in seen and text != input_str:
            seen.add(text)
            results.append((text, freq))

    # 1. 词库直接匹配（完整拼音键）
    syllables = best_split(input_str)
    if all(syl in VALID_SYLLABLES for syl in syllables):
        pinyin_key = " ".join(syllables)
        direct = dict_loader.lookup(pinyin_key)
        for word, freq in direct[:5]:
            _add(word, freq)

        # 其他切分匹配
        for split in split_pinyin(input_str):
            if not all(syl in VALID_SYLLABLES for syl in split):
                continue
            key = " ".join(split)
            if key == pinyin_key:
                continue
            alt = dict_loader.lookup(key)
            for word, freq in alt[:3]:
                _add(word, freq)

    # 2. 简拼/混合简拼匹配
    if not results:
        parts = mixed_split(input_str)
        has_full = any(len(p) >= 2 for p in parts)
        if has_full:
            mixed = dict_loader.lookup_mixed(parts)
            for word, freq in mixed[:3]:
                _add(word, freq)
        initials = "".join(p[0] for p in parts) if has_full else input_str
        init_r = dict_loader.lookup_phrase_initial(initials)
        for word, freq in init_r[:3]:
            _add(word, freq)

    # 3. 贪心分词拼出的整句（默认解释）
    all_syls = _get_syllables(input_str)
    if all_syls:
        segs = segment_pinyin(all_syls, dict_loader)
        default_text = "".join(word for _, _, word, _ in segs)
        _add(default_text, 500)

        # 4. 拆分多音节段 → 产生不同整句
        #    例：[you yi | dian] → 拆 you yi → [you | yi dian]
        #    → 整句从"友谊点"变成"有一点"
        for i, (py, syl, word, cands) in enumerate(segs):
            if len(syl) >= 2:
                prev_text = "".join(segs[k][2] for k in range(i))
                # 拆分：首音节单字 + 剩余（含后续段）重新分词
                first_segs = segment_pinyin([syl[0]], dict_loader)
                rest_syls = list(syl[1:])
                for j in range(i + 1, len(segs)):
                    rest_syls.extend(segs[j][1])
                rest_segs = segment_pinyin(rest_syls, dict_loader)
                split_text = prev_text + first_segs[0][2] + "".join(s[2] for s in rest_segs)
                _add(split_text, 400 - i * 50)

        # 5. 各段候选词替换产生变体
        #    例：[wo | bu zhi dao] → "wo"候选有"我/握/卧"
        #    → "我不知道" / "握不知道" / "卧不知道"
        if len(segs) <= 5:  # 避免组合爆炸
            for i, (py, syl, word, cands) in enumerate(segs):
                for alt_word in cands[1:4]:  # 前3个替代词
                    if alt_word == word:
                        continue
                    parts = [segs[k][2] for k in range(len(segs))]
                    parts[i] = alt_word
                    alt_text = "".join(parts)
                    _add(alt_text, 300 - i * 30)

    return results[:max_n]


def get_candidates(input_str, dict_loader, max_n=200, with_freq=False):
    """生成候选词列表（兼容旧接口）"""
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

    # 贪心分词结果
    if input_str.isalpha() and input_str.islower() and len(input_str) > 2:
        syllables = best_split(input_str)
        if len(syllables) >= 2 and all(syl in VALID_SYLLABLES for syl in syllables):
            segments = segment_pinyin(syllables, dict_loader)
            if segments:
                joined = "".join(word for _, _, word, _ in segments)
                if joined != input_str:
                    if not any(word == joined for word, freq in results):
                        results.append((joined, 1))

    if not results:
        if with_freq:
            return [(input_str, 0)]
        return [input_str]

    if with_freq:
        return results[:max_n]
    return [word for word, freq in results[:max_n]]

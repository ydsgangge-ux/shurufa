# -*- coding: utf-8 -*-
"""AI 输入法词库 v0.5 生成器

用 jieba dict.txt 替代 pypinyin phrases_dict：
- jieba dict.txt：337,466 条 2字+词组，100% 覆盖日常词，自带真实词频
- pypinyin phrases_dict：47,111 条，偏向成语，日常词覆盖率仅 23%

策略：
- 保留 v0.3 全量单字（27,283 条）
- 保留 v0.2 手工词组（178 条，高频）
- 新增 jieba dict.txt 中 freq>=10 的词组（约 96,456 条）
- 用 pypinyin 给 jieba 词组注音

预期结果：~123,000 条词条

使用：
    python gen_dict_v05.py
"""
import os
import shutil
import jieba
from pypinyin import pinyin, Style

DICT_PATH = "d:/AI软件/测试/shurufa/ai_ime/data/base_dict.txt"
MIN_FREQ = 10  # jieba 词频下限（过滤生僻词）


def read_existing(path):
    """读取现有词库，返回 (单字list, 词组list, 词组freq字典)

    词组freq字典：{(pinyin, word): freq}，用于后续比较 jieba 词频
    """
    singles = []
    phrases = []
    phrase_freq_map = {}  # {(pinyin, word): freq}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            py, word, freq_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
            try:
                freq = int(freq_str)
            except ValueError:
                freq = 100
            if not py or not word:
                continue
            if len(word) == 1:
                singles.append((py, word, freq))
            else:
                phrases.append((py, word, freq))
                # 记录每个 (pinyin, word) 的最大词频
                key = (py, word)
                if key not in phrase_freq_map or freq > phrase_freq_map[key]:
                    phrase_freq_map[key] = freq
    return singles, phrases, phrase_freq_map


def read_jieba_entries():
    """读取 jieba dict.txt，返回 [(word, freq), ...]（仅 2字+ 且 freq>=MIN_FREQ）"""
    jieba_dict_path = os.path.join(os.path.dirname(jieba.__file__), "dict.txt")
    print("jieba dict.txt:", jieba_dict_path)
    entries = []
    with open(jieba_dict_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            word = parts[0]
            try:
                freq = int(parts[1])
            except ValueError:
                continue
            # 只保留 2 字以上词组（单字已由 v0.3 全量覆盖）
            if len(word) >= 2 and freq >= MIN_FREQ:
                entries.append((word, freq))
    return entries


def main():
    if not os.path.isfile(DICT_PATH):
        print("ERROR: 词库文件不存在:", DICT_PATH)
        return

    # 1. 读取现有 v0.4 词库
    print("读取 v0.4 词库...")
    singles, existing_phrases, phrase_freq_map = read_existing(DICT_PATH)
    print("  单字: {} 条".format(len(singles)))
    print("  手工+v0.4 词组: {} 条".format(len(existing_phrases)))

    # 2. 备份 v0.4
    bak_path = DICT_PATH + ".v04.bak"
    if not os.path.isfile(bak_path):
        shutil.copy(DICT_PATH, bak_path)
        print("已备份 v0.4 → {}".format(bak_path))
    else:
        print("备份已存在，跳过: {}".format(bak_path))

    # 3. 读取 jieba 词典
    print("\n读取 jieba dict.txt (freq>={})...".format(MIN_FREQ))
    jieba_entries = read_jieba_entries()
    print("  jieba 词组数: {} 条".format(len(jieba_entries)))

    # 4. 用 pypinyin 给 jieba 词组注音
    # 策略：对每个 (pinyin_key, word)，
    #   - 若 jieba 词频 > 现有词频，更新现有词组的词频
    #   - 若不存在，新增
    print("\n用 pypinyin 注音并合并...")
    new_phrases = []  # jieba 新增的词组
    updated_count = 0  # jieba 更新词频的现有词组数
    skipped = 0
    # 用 dict 快速查找 existing_phrases 中的词组
    existing_phrase_map = {(py, word): idx for idx, (py, word, _) in enumerate(existing_phrases)}

    for i, (word, freq) in enumerate(jieba_entries):
        try:
            pys = pinyin(word, style=Style.NORMAL)
        except Exception:
            skipped += 1
            continue
        if len(pys) != len(word):
            skipped += 1
            continue
        pinyin_key = " ".join(p[0] for p in pys if p)
        if not pinyin_key:
            skipped += 1
            continue

        key = (pinyin_key, word)
        if key in existing_phrase_map:
            # 已有词组：若 jieba 词频更高，更新词频
            idx = existing_phrase_map[key]
            _, _, old_freq = existing_phrases[idx]
            if freq > old_freq:
                existing_phrases[idx] = (pinyin_key, word, freq)
                updated_count += 1
            # 否则保留现有词频
        else:
            # 新词组
            new_phrases.append((pinyin_key, word, freq))

        if (i + 1) % 20000 == 0:
            print("  已处理 {}/{}".format(i + 1, len(jieba_entries)))

    print("  新增词组: {} 条".format(len(new_phrases)))
    print("  更新词频: {} 条（jieba 词频更高）".format(updated_count))
    print("  跳过（注音失败）: {} 条".format(skipped))

    # 5. 写入 v0.5 词库
    print("\n写入 v0.5 词库...")
    total = len(singles) + len(existing_phrases) + len(new_phrases)
    with open(DICT_PATH, "w", encoding="utf-8") as f:
        f.write("# AI 输入法基础词库 v0.5（pypinyin 单字 + 手工词组 + jieba 词组）\n")
        f.write("# 格式：拼音<TAB>汉字<TAB>词频\n")
        f.write("# 单字：v0.3 保留（pypinyin 0.55.0 生成 CJK 基本区全量汉字）\n")
        f.write("# 词组：v0.2 手工词组（高频）+ jieba dict.txt 词组（freq>={})\n".format(MIN_FREQ))
        f.write("# 词频：jieba 真实语料词频（范围 10-142747），取 jieba 与手工的最大值\n")
        f.write("# 个人本地使用，不分发\n\n")
        f.write("# ===== 单字（v0.3 保留）=====\n")
        for py, ch, freq in singles:
            f.write("{}\t{}\t{}\n".format(py, ch, freq))
        f.write("\n# ===== 词组（v0.2 手工 + jieba）=====\n")
        # 现有词组（含被 jieba 更新词频的）
        for py, word, freq in existing_phrases:
            f.write("{}\t{}\t{}\n".format(py, word, freq))
        # jieba 新增词组
        for py, word, freq in new_phrases:
            f.write("{}\t{}\t{}\n".format(py, word, freq))

    print("\nv0.5 词库已生成: {}".format(DICT_PATH))
    print("  总条数: {}".format(total))
    print("  单字: {}".format(len(singles)))
    print("  手工+v0.4 词组: {} 条（含 {} 条被 jieba 更新词频）".format(len(existing_phrases), updated_count))
    print("  jieba 新增词组: {} 条".format(len(new_phrases)))


if __name__ == "__main__":
    main()

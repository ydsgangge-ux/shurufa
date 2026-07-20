# -*- coding: utf-8 -*-
"""AI 输入法词库 v0.4 生成器

在 v0.3 基础上扩充词组：
- 保留 v0.3 全量单字（27,283 条，pypinyin 生成）
- 保留 v0.2 手工词组（178 条，高频）
- 新增 pypinyin phrases_dict 47,111 条词组（去声调，NORMAL style）

预期结果：~74,000 条词条

使用：
    python gen_dict_v04.py
"""
import os
import shutil
from pypinyin import pinyin, Style
from pypinyin import phrases_dict as pd_module

DICT_PATH = "d:/AI软件/测试/shurufa/ai_ime/data/base_dict.txt"


def read_existing(path):
    """读取现有词库，返回 (单字list, 词组list, 词组键集合)

    单字：(pinyin, char, freq)
    词组：(pinyin, word, freq)
    词组键集合：{(pinyin, word)} 用于去重
    """
    singles = []
    phrases = []
    phrase_keys = set()
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
                phrase_keys.add((py, word))
    return singles, phrases, phrase_keys


def get_phrase_freq(word):
    """根据词长度给默认词频（2字 300, 3字 250, 4字 200, 5+ 150）"""
    n = len(word)
    if n == 2:
        return 300
    elif n == 3:
        return 250
    elif n == 4:
        return 200
    else:
        return 150


def main():
    if not os.path.isfile(DICT_PATH):
        print("ERROR: 词库文件不存在:", DICT_PATH)
        return

    # 1. 读取现有 v0.3 词库
    print("读取 v0.3 词库...")
    singles, existing_phrases, phrase_keys = read_existing(DICT_PATH)
    print("  单字: {} 条".format(len(singles)))
    print("  手工词组: {} 条".format(len(existing_phrases)))

    # 2. 备份 v0.3
    bak_path = DICT_PATH + ".v03.bak"
    if not os.path.isfile(bak_path):
        shutil.copy(DICT_PATH, bak_path)
        print("已备份 v0.3 → {}".format(bak_path))
    else:
        print("备份已存在，跳过: {}".format(bak_path))

    # 3. 从 pypinyin phrases_dict 生成新词组
    print("从 pypinyin 生成词组...")
    PHRASES = pd_module.phrases_dict  # dict, 47111 条
    print("  pypinyin phrases_dict 总数: {}".format(len(PHRASES)))

    new_phrases = []
    skipped = 0
    for word in PHRASES.keys():
        if len(word) < 2:
            skipped += 1
            continue  # 单字已在 v0.3 全量覆盖
        # 用 pinyin() 获取 NORMAL style 拼音（与 v0.3 单字一致：ü→v, 去声调）
        # 多音字由 pypinyin 根据词组上下文自动选择正确读音
        try:
            pys = pinyin(word, style=Style.NORMAL)
        except Exception:
            skipped += 1
            continue
        if not pys or len(pys) != len(word):
            skipped += 1
            continue  # 拼音数与字数不匹配，跳过
        pinyin_key = " ".join(p[0] for p in pys if p)
        if not pinyin_key:
            skipped += 1
            continue
        # 跳过已有手工词组（保留高频）
        if (pinyin_key, word) in phrase_keys:
            skipped += 1
            continue
        freq = get_phrase_freq(word)
        new_phrases.append((pinyin_key, word, freq))

    print("  新增词组: {} 条".format(len(new_phrases)))
    print("  跳过（已有/单字/异常）: {} 条".format(skipped))

    # 4. 写入 v0.4 词库
    print("写入 v0.4 词库...")
    total = len(singles) + len(existing_phrases) + len(new_phrases)
    with open(DICT_PATH, "w", encoding="utf-8") as f:
        f.write("# AI 输入法基础词库 v0.4（pypinyin 单字 + 手工词组 + pypinyin 47k 词组）\n")
        f.write("# 格式：拼音<TAB>汉字<TAB>词频\n")
        f.write("# 单字：v0.3 保留（pypinyin 0.55.0 生成 CJK 基本区全量汉字）\n")
        f.write("# 词组：v0.2 手工词组（高频）+ pypinyin phrases_dict 47k 词组\n")
        f.write("# 个人本地使用，不分发\n\n")
        f.write("# ===== 单字（v0.3 保留）=====\n")
        for py, ch, freq in singles:
            f.write("{}\t{}\t{}\n".format(py, ch, freq))
        f.write("\n# ===== 词组（v0.2 手工 + pypinyin 47k）=====\n")
        # 手工词组优先（词频高）
        for py, word, freq in existing_phrases:
            f.write("{}\t{}\t{}\n".format(py, word, freq))
        for py, word, freq in new_phrases:
            f.write("{}\t{}\t{}\n".format(py, word, freq))

    print("v0.4 词库已生成: {}".format(DICT_PATH))
    print("  总条数: {}".format(total))
    print("  单字: {}".format(len(singles)))
    print("  手工词组: {}".format(len(existing_phrases)))
    print("  pypinyin 新增词组: {}".format(len(new_phrases)))


if __name__ == "__main__":
    main()

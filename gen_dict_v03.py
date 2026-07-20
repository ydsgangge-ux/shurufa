# -*- coding: utf-8 -*-
"""用 pypinyin 自动生成全量单字词库，合并现有词组

策略：
1. 遍历 CJK 基本区（U+4E00 - U+9FA5），约 20,902 字
2. 用 pypinyin 获取每个字的拼音（多音字收录所有读音）
3. 现有词库中已有的单字，保留手工词频（更精确）
4. 新单字按 Unicode 码点反比给词频（码点小=常用=词频高）
5. 词组（多字词）全部保留自 v0.2
6. 生成新 base_dict.txt
"""
import os
from pypinyin import pinyin, Style

DICT_PATH = "d:/AI软件/测试/shurufa/ai_ime/data/base_dict.txt"


def read_existing():
    """读取现有词库，返回 (单字dict, 词组list)

    单字dict: {(pinyin, char): freq}
    词组list: [(pinyin, word, freq), ...]
    """
    singles = {}
    phrases = []
    with open(DICT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            py, word, freq_str = parts[0], parts[1], parts[2]
            try:
                freq = int(freq_str)
            except ValueError:
                freq = 100
            if len(word) == 1:
                singles[(py, word)] = freq
            else:
                phrases.append((py, word, freq))
    return singles, phrases


def get_default_freq(ch):
    """根据 GB2312 编码位置给默认词频

    GB2312 一级字库（3755 字，按拼音排序）：常用字，词频 150
    GB2312 二级字库（3008 字，按部首排序）：次常用字，词频 100
    不在 GB2312 中（生僻字）：词频 50

    手工词频（300-1000）远高于默认词频，确保高频字排前面。
    """
    try:
        b = ch.encode('gb2312')
        if len(b) == 2:
            high = b[0]
            if 0xB0 <= high <= 0xD7:
                return 150  # 一级字库（常用字）
            elif 0xD8 <= high <= 0xF7:
                return 100  # 二级字库（次常用字）
    except UnicodeEncodeError:
        pass
    return 50  # 不在 GB2312 中（生僻字）


def gen_all_singles(existing_singles):
    """生成全量单字，合并现有词频

    对 CJK 基本区每个字，用 pypinyin 获取所有读音。
    现有词库已有的 (拼音, 字) 保留原词频（高优先级）；
    新字用 GB2312 分级词频（50/100/150，远低于手工词频）。
    """
    result = []
    seen = set()
    for cp in range(0x4E00, 0x9FA6):
        ch = chr(cp)
        pys = pinyin(ch, style=Style.NORMAL, heteronym=True)
        if not pys or not pys[0]:
            continue
        default_freq = get_default_freq(ch)
        for py in pys[0]:
            if not py or py == ch:
                continue
            key = (py, ch)
            if key in seen:
                continue
            seen.add(key)
            # 现有词频优先（手工设置，300-1000，远高于默认 50-150）
            freq = existing_singles.get(key, default_freq)
            result.append((py, ch, freq))
    return result


def main():
    print("=== 1. 读取现有词库 ===")
    existing_singles, phrases = read_existing()
    print("现有单字: {} 条".format(len(existing_singles)))
    print("现有词组: {} 条".format(len(phrases)))

    print("\n=== 2. 生成全量单字（pypinyin 扫描 CJK 基本区）===")
    all_singles = gen_all_singles(existing_singles)
    print("全量单字: {} 条（含多音字）".format(len(all_singles)))

    # 写入新词库
    output_path = DICT_PATH + ".new"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# AI 输入法基础词库 v0.3（pypinyin 自动生成 + 手工词组）\n")
        f.write("# 格式：拼音<TAB>汉字<TAB>词频\n")
        f.write("# 单字：pypinyin 0.55.0 生成 CJK 基本区全量汉字，多音字全收录\n")
        f.write("# 词频：现有手工词频优先，新字按 Unicode 码点反比\n")
        f.write("# 词组：保留 v0.2 手工补充\n")
        f.write("# 个人本地使用，不分发\n\n")

        f.write("# ===== 单字（pypinyin 自动生成）=====\n")
        for py, ch, freq in all_singles:
            f.write("{}\t{}\t{}\n".format(py, ch, freq))

        f.write("\n# ===== 词组（v0.2 手工补充）=====\n")
        for py, word, freq in phrases:
            f.write("{}\t{}\t{}\n".format(py, word, freq))

    total = len(all_singles) + len(phrases)
    size = os.path.getsize(output_path)
    print("\n=== 3. 生成完成 ===")
    print("总条目数: {}".format(total))
    print("文件大小: {:.1f} KB".format(size / 1024))
    print("输出文件: {}".format(output_path))

    # 验证关键单字
    print("\n=== 4. 关键单字验证 ===")
    single_map = {}
    for py, ch, freq in all_singles:
        single_map.setdefault(py, []).append((ch, freq))
    test = ["ni", "xian", "kan", "ting", "ma", "zuo", "de", "shi", "chi", "hua"]
    for py in test:
        cands = single_map.get(py, [])
        top = sorted(cands, key=lambda x: -x[1])[:5]
        print("  {} -> {}".format(py, [(c, f) for c, f in top]))

    # 验证词组
    print("\n=== 5. 词组验证 ===")
    for py, word, freq in phrases[:5]:
        print("  {} -> {} ({})".format(py, word, freq))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""合法汉语拼音音节表（无声调，输入法用）

用途：拼音切分算法的核心数据。输入串被切分为若干合法音节的序列。

说明：
- 共约 400 个无声调音节
- j/q/x/y 后的 u 实际是 ü，输入法用 u 输入（如 ju=居, que=缺, yue=约）
- n/l 后的 ü 需用 v 输入（如 nv=女, lv=绿），v 当作 ü
- 来源：现代汉语拼音方案 + 实际输入法约定
"""

VALID_SYLLABLES = frozenset({
    # a 系（零声母）
    "a", "ai", "an", "ang", "ao",
    # b
    "ba", "bai", "ban", "bang", "bao", "bei", "ben", "beng",
    "bi", "bian", "biao", "bie", "bin", "bing", "bo", "bu",
    # c
    "ca", "cai", "can", "cang", "cao", "ce", "cen", "ceng",
    "ci", "cong", "cou", "cu", "cuan", "cui", "cun", "cuo",
    # ch
    "cha", "chai", "chan", "chang", "chao", "che", "chen", "cheng",
    "chi", "chong", "chou", "chu", "chuai", "chuan", "chuang",
    "chui", "chun", "chuo",
    # d
    "da", "dai", "dan", "dang", "dao", "de", "dei", "den", "deng",
    "di", "dian", "diao", "die", "ding", "diu", "dong", "dou",
    "du", "duan", "dui", "dun", "duo",
    # e
    "e", "ei", "en", "eng", "er",
    # f
    "fa", "fan", "fang", "fei", "fen", "feng", "fo", "fou", "fu",
    # g
    "ga", "gai", "gan", "gang", "gao", "ge", "gei", "gen", "geng",
    "gong", "gou", "gu", "gua", "guai", "guan", "guang", "gui",
    "gun", "guo",
    # h
    "ha", "hai", "han", "hang", "hao", "he", "hei", "hen", "heng",
    "hong", "hou", "hu", "hua", "huai", "huan", "huang", "hui",
    "hun", "huo",
    # j
    "ji", "jia", "jian", "jiang", "jiao", "jie", "jin", "jing",
    "jiong", "jiu", "ju", "juan", "jue", "jun",
    # k
    "ka", "kai", "kan", "kang", "kao", "ke", "ken", "keng",
    "kong", "kou", "ku", "kua", "kuai", "kuan", "kuang", "kui",
    "kun", "kuo",
    # l
    "la", "lai", "lan", "lang", "lao", "le", "lei", "leng",
    "li", "lia", "lian", "liang", "liao", "lie", "lin", "ling",
    "liu", "long", "lou", "lu", "luan", "lun", "luo",
    "lv", "lve",
    # m
    "ma", "mai", "man", "mang", "mao", "me", "mei", "men", "meng",
    "mi", "mian", "miao", "mie", "min", "ming", "miu", "mo", "mou", "mu",
    # n
    "na", "nai", "nan", "nang", "nao", "ne", "nei", "nen", "neng",
    "ni", "nian", "niang", "niao", "nie", "nin", "ning", "niu",
    "nong", "nou", "nu", "nuan", "nuo",
    "nv", "nve",
    # o
    "o", "ou",
    # p
    "pa", "pai", "pan", "pang", "pao", "pei", "pen", "peng",
    "pi", "pian", "piao", "pie", "pin", "ping", "po", "pou", "pu",
    # q
    "qi", "qia", "qian", "qiang", "qiao", "qie", "qin", "qing",
    "qiong", "qiu", "qu", "quan", "que", "qun",
    # r
    "ran", "rang", "rao", "re", "ren", "reng", "ri", "rong", "rou",
    "ru", "rua", "ruan", "rui", "run", "ruo",
    # s
    "sa", "sai", "san", "sang", "sao", "se", "sen", "seng",
    "si", "song", "sou", "su", "suan", "sui", "sun", "suo",
    # sh
    "sha", "shai", "shan", "shang", "shao", "she", "shei", "shen", "sheng",
    "shi", "shou", "shu", "shua", "shuai", "shuan", "shuang",
    "shui", "shun", "shuo",
    # t
    "ta", "tai", "tan", "tang", "tao", "te", "teng",
    "ti", "tian", "tiao", "tie", "ting", "tong", "tou",
    "tu", "tuan", "tui", "tun", "tuo",
    # w
    "wa", "wai", "wan", "wang", "wei", "wen", "weng", "wo", "wu",
    # x
    "xi", "xia", "xian", "xiang", "xiao", "xie", "xin", "xing",
    "xiong", "xiu", "xu", "xuan", "xue", "xun",
    # y
    "ya", "yan", "yang", "yao", "ye", "yi", "yin", "ying",
    "yong", "you", "yu", "yuan", "yue", "yun",
    # z
    "za", "zai", "zan", "zang", "zao", "ze", "zei", "zen", "zeng",
    "zi", "zong", "zou", "zu", "zuan", "zui", "zun", "zuo",
    # zh
    "zha", "zhai", "zhan", "zhang", "zhao", "zhe", "zhen", "zheng",
    "zhi", "zhong", "zhou", "zhu", "zhua", "zhuai", "zhuan",
    "zhuang", "zhui", "zhun", "zhuo",
})

# 按首字母分组，加速切分时的候选生成（避免每次都全表扫描）
SYLLABLES_BY_INITIAL = {}
for _syl in VALID_SYLLABLES:
    _initial = _syl[0]
    SYLLABLES_BY_INITIAL.setdefault(_initial, []).append(_syl)

# 最长音节长度（如 "zhuang", "chuang", "shuang" 均为 6 字符）
MAX_SYLLABLE_LEN = max(len(s) for s in VALID_SYLLABLES)  # 6

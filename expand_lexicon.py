# -*- coding: utf-8 -*-
"""AI IME 词库扩展工具

输入一个领域名称，自动补充该领域的专业词汇到词库。

数据来源：
1. 内置领域词库（THUOCL 等，已有拼音）
2. 云端 LLM 生成（任意领域，API 生成 + pypinyin 自动加拼音）

用法：
    python expand_lexicon.py it          # 补充 IT 领域词汇
    python expand_lexicon.py 医学        # 补充医学词汇
    python expand_lexicon.py 线束制造     # 补充细分领域（LLM 生成）
    python expand_lexicon.py --list       # 列出所有内置领域
    python expand_lexicon.py --all        # 导入所有内置领域
"""

import os
import sys
import re
import json

# ===== 路径 =====
# 优先定位安装目录的词库，其次用项目开发目录
def _find_dict_dir():
    """定位词库目录：注册表 > PIME 安装目录 > 项目开发目录

    优先级：
    1. 注册表查找 Inno Setup 安装路径（适配任意安装位置）
    2. PIME/AI_IME 默认安装路径
    3. 开发目录兜底
    """
    import winreg

    search_paths = []

    # 1. 注册表查找 Inno Setup 安装路径（最可靠，适配任意盘符）
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\AI IME_is1",
            0, winreg.KEY_READ
        )
        install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
        if install_dir:
            # Inno Setup 安装根目录 → 词库子路径
            search_paths.append(os.path.join(
                install_dir.rstrip("\\"),
                "python", "input_methods", "ai_ime", "data"
            ))
    except OSError:
        pass

    # 2. PIME 框架默认路径（用环境变量，不硬编码盘符）
    pf = os.environ.get("ProgramFiles(x86)", "")
    if pf:
        search_paths.append(os.path.join(pf, "AI_IME", "python", "input_methods", "ai_ime", "data"))
        search_paths.append(os.path.join(pf, "PIME", "input_methods", "ai_ime", "data"))

    # 3. 开发目录
    search_paths.append(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ai_ime", "data"
    ))

    for d in search_paths:
        if os.path.isfile(os.path.join(d, "base_dict.txt")):
            return d

    # 兜底：开发目录
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_ime", "data")

DATA_DIR = _find_dict_dir()
BASE_DICT = os.path.join(DATA_DIR, "base_dict.txt")
THUOCL_DIR = os.path.join(DATA_DIR, "thuocl")
EXPANDED_FILE = os.path.join(DATA_DIR, "expanded.json")

# 确保 thuocl 目录存在
os.makedirs(THUOCL_DIR, exist_ok=True)

# ===== 内置领域映射 =====
# key: 用户输入的领域名 → (THUOCL文件, 显示名, 条数)
BUILTIN_DOMAINS = {
    "it":       ("THUOCL_it.txt",         "IT/计算机",      16000),
    "编程":      ("THUOCL_it.txt",         "IT/计算机",      16000),
    "计算机":    ("THUOCL_it.txt",         "IT/计算机",      16000),
    "财经":      ("THUOCL_caijing.txt",    "财经",           3830),
    "金融":      ("THUOCL_caijing.txt",    "财经",           3830),
    "成语":      ("THUOCL_chengyu.txt",    "成语",           8519),
    "地名":      ("THUOCL_diming.txt",     "地名",           44805),
    "地理":      ("THUOCL_diming.txt",     "地名",           44805),
    "历史名人":  ("THUOCL_lishimingren.txt","历史名人",       13658),
    "人名":      ("THUOCL_lishimingren.txt","历史名人",       13658),
    "诗词":      ("THUOCL_shici.txt",      "诗词",           13703),
    "古诗文":    ("THUOCL_shici.txt",      "诗词",           13703),
    "医学":      ("THUOCL_medical.txt",    "医学",           18749),
    "医疗":      ("THUOCL_medical.txt",    "医学",           18749),
    "饮食":      ("THUOCL_food.txt",       "饮食",           8974),
    "美食":      ("THUOCL_food.txt",       "饮食",           8974),
    "法律":      ("THUOCL_law.txt",        "法律",           9896),
    "汽车":      ("THUOCL_car.txt",        "汽车",           1752),
    "动物":      ("THUOCL_animal.txt",     "动物",           17287),
}


def _load_base_dict():
    """加载现有词库，返回 {(pinyin, word): freq}"""
    existing = {}
    if not os.path.isfile(BASE_DICT):
        return existing
    with open(BASE_DICT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                pinyin = parts[0].strip()
                word = parts[1].strip()
                freq = 100
                if len(parts) >= 3:
                    try:
                        freq = int(parts[2].strip())
                    except ValueError:
                        freq = 100
                key = (pinyin, word)
                if key not in existing or freq > existing[key]:
                    existing[key] = freq
    return existing


def _add_pinyin(words):
    """为词语列表添加拼音

    Args:
        words: [word, ...] 或 [(word, freq), ...]

    Returns:
        [(pinyin, word, freq), ...]
    """
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        print("[INFO] 正在安装 pypinyin...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypinyin", "-q"])
        from pypinyin import pinyin, Style

    results = []
    for item in words:
        if isinstance(item, tuple):
            word, freq = item
        else:
            word, freq = item, 9999

        if not word or not re.search(r'[\u4e00-\u9fff]', word):
            continue

        try:
            py = pinyin(word, style=Style.NORMAL)
            pinyin_key = " ".join(p[0] for p in py)
        except Exception:
            continue

        if pinyin_key and word:
            results.append((pinyin_key, word, freq))

    return results


def _import_thuocl(filepath, existing):
    """导入 THUOCL 格式的词库文件

    THUOCL 格式：word\\tDF值
    需要 pypinyin 添加拼音

    Returns:
        [(pinyin, word, freq), ...] 新增的词条
    """
    if not os.path.isfile(filepath):
        print("  文件不存在: {}".format(filepath))
        return []

    words = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            word = parts[0].strip()
            if not word or not re.search(r'[\u4e00-\u9fff]', word):
                continue
            # DF 值作为词频（归一化到合理范围）
            df = 9999
            if len(parts) >= 2:
                try:
                    df_val = int(parts[1].strip())
                    # DF 值范围 1-700万，归一化到 500-9999
                    df = min(9999, max(500, df_val // 100 + 500))
                except ValueError:
                    df = 9999
            # 过滤太长的词（>8字不太适合输入法）
            if len(word) > 8:
                continue
            words.append((word, df))

    print("  读取到 {} 条候选词".format(len(words)))

    # 批量加拼音
    entries = _add_pinyin(words)
    print("  拼音标注: {} 条成功".format(len(entries)))

    # 去重（与现有词库比较）
    new_entries = []
    for py, word, freq in entries:
        key = (py, word)
        if key not in existing:
            new_entries.append((py, word, freq))

    print("  去重后新增: {} 条".format(len(new_entries)))
    return new_entries


def _generate_by_llm(domain, existing, n=200):
    """用云端 LLM 生成领域词汇

    Args:
        domain: 领域名称（如"线束制造"、"半导体"等）
        existing: 现有词库
        n: 生成数量

    Returns:
        [(pinyin, word, freq), ...]
    """
    # 确保 ai_ime 包可导入（从项目根目录或脚本所在目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ai_ime_dir = os.path.join(script_dir, "ai_ime")
    if ai_ime_dir not in sys.path:
        sys.path.insert(0, ai_ime_dir)
    from ai.cloud_client import get_cloud_client

    cloud = get_cloud_client()
    if not cloud.is_available():
        print("[ERROR] 云端 API 不可用，请配置 api_config.json")
        return []

    # 分批生成（每批30个，快速迭代）
    all_words = []
    batch_size = 30
    stale_count = 0  # 连续无新词计数
    for batch in range((n + batch_size - 1) // batch_size):
        remaining = n - len(all_words)
        if remaining <= 0:
            break
        count = min(batch_size, remaining)

        messages = [
            {"role": "system", "content":
                "根据领域生成专业词汇列表。只输出词汇用逗号分隔，不要编号解释。"
            },
            {"role": "user", "content": "领域：医学，生成5个"},
            {"role": "assistant", "content": "听诊器,心电图,抗生素,核磁共振,病理切片"},
            {"role": "user", "content": "领域：金融，生成5个"},
            {"role": "assistant", "content": "对冲基金,市盈率,量化交易,信用评级,资产证券化"},
            {"role": "user", "content":
                "领域：{}，生成{}个".format(domain, count)
            },
        ]

        result = cloud.chat(messages, max_tokens=500)
        if not result:
            print("  第{}批生成失败".format(batch + 1))
            stale_count += 1
            if stale_count >= 3:
                print("  连续3批失败，提前终止")
                break
            continue

        # 解析结果
        parts = re.split(r'[,，、\n\s]+', result.strip())
        new_in_batch = 0
        for p in parts:
            p = p.strip()
            # 去掉编号
            p = re.sub(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+[.、)）]?\s*', '', p)
            if p and re.match(r'^[\u4e00-\u9fff]{2,6}$', p):
                if p not in set(all_words):
                    new_in_batch += 1
                all_words.append(p)

        print("  第{}批: +{} 新词".format(batch + 1, new_in_batch))

        # 连续3批无新词则提前终止
        if new_in_batch == 0:
            stale_count += 1
            if stale_count >= 3:
                print("  连续3批无新词，提前终止")
                break
        else:
            stale_count = 0

    # 去重
    seen = set()
    unique_words = []
    for w in all_words:
        if w not in seen:
            seen.add(w)
            unique_words.append(w)

    print("  去重后候选: {} 个".format(len(unique_words)))

    # 加拼音
    entries = _add_pinyin(unique_words)
    print("  拼音标注: {} 条成功".format(len(entries)))

    # 与现有词库去重
    new_entries = []
    for py, word, freq in entries:
        key = (py, word)
        if key not in existing:
            new_entries.append((py, word, freq))

    print("  与词库去重后新增: {} 条".format(len(new_entries)))
    return new_entries


def _merge_to_dict(new_entries):
    """将新词条合并到 base_dict.txt"""
    if not new_entries:
        print("没有新词条需要合并")
        return 0

    # 读取现有词库
    existing = _load_base_dict()

    # 合并
    added = 0
    for py, word, freq in new_entries:
        key = (py, word)
        if key not in existing:
            existing[key] = freq
            added += 1
        elif freq > existing[key]:
            existing[key] = freq
            added += 1

    if added == 0:
        print("没有新词条需要写入")
        return 0

    # 检查写入权限（Program Files 需要管理员）
    try:
        with open(BASE_DICT, "r", encoding="utf-8") as f:
            pass
    except PermissionError:
        print("\n[ERROR] 没有写入权限！请用管理员身份运行 PowerShell")
        print("  右键 PowerShell → 以管理员身份运行")
        print("  然后重新执行: python expand_lexicon.py <domain>")
        return 0
    comments = []
    if os.path.isfile(BASE_DICT):
        with open(BASE_DICT, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    comments.append(line.rstrip("\n"))

    sorted_entries = sorted(existing.items(), key=lambda x: (x[0][0], -x[1]))

    with open(BASE_DICT, "w", encoding="utf-8") as f:
        for line in comments:
            f.write(line + "\n")
        for (py, word), freq in sorted_entries:
            f.write("{}\t{}\t{}\n".format(py, word, freq))

    print("写入 {} 条新词条到 {} (总量: {})".format(added, os.path.basename(BASE_DICT), len(existing)))
    return added


def _save_expanded_record(domain, count):
    """记录已扩展的领域"""
    records = {}
    if os.path.isfile(EXPANDED_FILE):
        try:
            with open(EXPANDED_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            pass
    records[domain] = {"count": count, "time": str(os.path.getmtime(BASE_DICT))}
    with open(EXPANDED_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def expand_domain(domain):
    """扩展指定领域的词汇"""
    print("=" * 50)
    print("扩展领域: {}".format(domain))
    print("词库路径: {}".format(DATA_DIR))
    print("=" * 50)

    existing = _load_base_dict()
    print("现有词库: {} 条".format(len(existing)))

    # 1. 检查是否是内置领域
    if domain in BUILTIN_DOMAINS:
        filename, display_name, expected = BUILTIN_DOMAINS[domain]
        filepath = os.path.join(THUOCL_DIR, filename)
        print("\n[内置领域] {} (约{}条)".format(display_name, expected))

        if os.path.isfile(filepath):
            new_entries = _import_thuocl(filepath, existing)
        else:
            print("  THUOCL文件不存在: {}".format(filepath))
            print("  请手动下载: http://thuocl.thunlp.org/")
            print("  改用 LLM 生成...")
            new_entries = _generate_by_llm(domain, existing, n=200)
    else:
        # 2. 非内置领域，用 LLM 生成
        print("\n[LLM 生成] 领域: {}".format(domain))
        new_entries = _generate_by_llm(domain, existing, n=200)

    if not new_entries:
        print("\n没有新词条，词库无需更新")
        return

    # 3. 预览
    print("\n新增词条预览（前20条）:")
    for py, word, freq in new_entries[:20]:
        print("  {} → {} (freq={})".format(py, word, freq))
    if len(new_entries) > 20:
        print("  ... 共 {} 条".format(len(new_entries)))

    # 4. 合并
    print("\n合并到词库...")
    added = _merge_to_dict(new_entries)
    _save_expanded_record(domain, added)
    print("\n完成！重启输入法后生效。")


def list_domains():
    """列出所有可用的内置领域"""
    print("内置领域词库：")
    print("-" * 40)
    seen = set()
    for key, (filename, display_name, count) in sorted(BUILTIN_DOMAINS.items()):
        if filename not in seen:
            filepath = os.path.join(THUOCL_DIR, filename)
            status = "✓" if os.path.isfile(filepath) else "✗"
            print("  {} {:<8} {} ({}条)".format(status, key, display_name, count))
            seen.add(filename)

    print()
    print("提示：")
    print("  ✓ = THUOCL文件已就绪")
    print("  ✗ = 需要下载或改用LLM生成")
    print("  任何非内置领域名称会自动使用LLM生成")


def expand_all():
    """导入所有内置领域"""
    existing = _load_base_dict()
    print("现有词库: {} 条".format(len(existing)))

    total_added = 0
    seen = set()
    for key, (filename, display_name, _) in BUILTIN_DOMAINS.items():
        if filename in seen:
            continue
        seen.add(filename)

        filepath = os.path.join(THUOCL_DIR, filename)
        if not os.path.isfile(filepath):
            print("\n跳过 {} (文件不存在)".format(display_name))
            continue

        print("\n--- {} ---".format(display_name))
        new_entries = _import_thuocl(filepath, existing)
        if new_entries:
            for py, word, freq in new_entries:
                key_e = (py, word)
                if key_e not in existing:
                    existing[key_e] = freq
                    total_added += 1
            _save_expanded_record(key, len(new_entries))

    if total_added > 0:
        # 写入词库
        comments = []
        if os.path.isfile(BASE_DICT):
            with open(BASE_DICT, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        comments.append(line.rstrip("\n"))
        sorted_entries = sorted(existing.items(), key=lambda x: (x[0][0], -x[1]))
        with open(BASE_DICT, "w", encoding="utf-8") as f:
            for line in comments:
                f.write(line + "\n")
            for (py, word), freq in sorted_entries:
                f.write("{}\t{}\t{}\n".format(py, word, freq))

    print("\n总计新增: {} 条".format(total_added))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    arg = sys.argv[1]

    if arg == "--list":
        list_domains()
    elif arg == "--all":
        expand_all()
    else:
        expand_domain(arg)


if __name__ == "__main__":
    main()

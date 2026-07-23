# -*- coding: utf-8 -*-
"""AI IME 扩词库一键启动工具"""

import os
import sys
import subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DOMAINS = [
    ("1",  "it",          "IT/计算机"),
    ("2",  "财经",        "财经/金融"),
    ("3",  "医学",        "医学/医疗"),
    ("4",  "成语",        "成语"),
    ("5",  "地名",        "地名/地理"),
    ("6",  "诗词",        "诗词/古诗文"),
    ("7",  "历史名人",    "历史名人/人名"),
    ("8",  "饮食",        "饮食/美食"),
    ("9",  "法律",        "法律"),
    ("0",  "汽车",        "汽车"),
    ("A",  "动物",        "动物"),
    ("E",  "常用口语化短句词语", "常用口语化短句词语"),
]

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def show_menu():
    clear()
    print()
    print("=" * 44)
    print("   AI IME - AI 扩词库工具 v1.2.0")
    print("=" * 44)
    print()
    for key, _, desc in DOMAINS:
        print(f"  [{key}] {desc}")
    print("  [B] 导入所有内置领域")
    print("  [C] 自定义领域(输入名称)")
    print("  [D] 查看可用领域列表")
    print("  [Q] 退出")
    print()

def run_expand(arg):
    cmd = [sys.executable, "expand_lexicon.py", arg]
    subprocess.run(cmd)

def restart_prompt():
    print()
    print("=" * 44)
    print("  词库已更新! 是否重启输入法使新词生效?")
    print("=" * 44)
    print()
    r = input("重启输入法? (Y/N): ").strip().upper()
    if r == "Y":
        print("正在重启输入法...")
        bat = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restart_ime.bat")
        subprocess.run(bat, shell=True)
    else:
        print("跳过重启。可稍后双击 restart_ime.bat 手动重启。")
    input("\n按回车继续...")

def main():
    domain_map = {k: v for k, v, _ in DOMAINS}

    while True:
        show_menu()
        choice = input("请选择: ").strip().upper()

        if choice == "Q":
            break

        if choice == "D":
            run_expand("--list")
            input("\n按回车继续...")
            continue

        if choice == "B":
            run_expand("--all")
            restart_prompt()
            continue

        if choice == "C":
            domain = input("请输入领域名称(如: 半导体, 线束制造, 航空航天): ").strip()
            if domain:
                run_expand(domain)
                restart_prompt()
            continue

        if choice in domain_map:
            run_expand(domain_map[choice])
            restart_prompt()
            continue

        print("无效选择，按回车继续...")
        input()

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
AI 输入法 - 第0期自动化验证脚本

验证项：
  A. PIME 安装检查
  B. ai_ime 输入法部署检查
  C. PIMELauncher 运行检查
  D. 按键回调日志检查（需手动打字后运行）

用法:
    python validate_phase0.py

输出: JSON 报告 + 控制台摘要
"""

import os
import sys
import json
import subprocess
import datetime


PIME_PATHS = [
    r"C:\Program Files (x86)\PIME",
    r"C:\Program Files\PIME",
]

IME_NAME = "ai_ime"
LOG_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "PIME", "Log", "ai_ime_debug.log"
)


def check_pime_installed():
    """A. 检查 PIME 是否安装"""
    for path in PIME_PATHS:
        if os.path.isdir(path):
            im_dir = os.path.join(path, "python", "input_methods")
            if os.path.isdir(im_dir):
                return True, path
    return False, None


def check_ime_deployed(pime_path):
    """B. 检查 ai_ime 是否部署到 PIME 目录"""
    if not pime_path:
        return False, {}
    target = os.path.join(pime_path, "python", "input_methods", IME_NAME)
    if not os.path.isdir(target):
        return False, {"target": target, "exists": False}
    files = os.listdir(target)
    required = ["ime.json", "ai_ime_ime.py"]
    missing = [f for f in required if f not in files]
    return len(missing) == 0, {
        "target": target,
        "files": files,
        "missing": missing,
    }


def check_launcher_running():
    """C. 检查 PIMELauncher 是否运行"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PIMELauncher.exe"],
            capture_output=True, text=True, timeout=5
        )
        return "PIMELauncher.exe" in result.stdout
    except Exception:
        return False


def check_key_log():
    """D. 检查按键回调日志（需手动打字后才会有日志）"""
    if not os.path.isfile(LOG_FILE):
        return False, {"log_file": LOG_FILE, "exists": False, "lines": 0}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.strip().split("\n") if content.strip() else []
    has_key_event = any("onKeyDown" in line for line in lines)
    return has_key_event, {
        "log_file": LOG_FILE,
        "exists": True,
        "lines": len(lines),
        "has_key_event": has_key_event,
        "last_5_lines": lines[-5:] if len(lines) >= 5 else lines,
    }


def main():
    print("=" * 60)
    print("AI 输入法 - 第0期验证报告")
    print("时间: {}".format(datetime.datetime.now().isoformat()))
    print("=" * 60)

    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "windows_version": sys.platform,
    }

    # A. PIME 安装
    pime_ok, pime_path = check_pime_installed()
    report["pime_installed"] = pime_ok
    report["pime_path"] = pime_path
    status = "OK" if pime_ok else "FAIL"
    print("\n[A] PIME 安装检查: {}".format(status))
    if pime_ok:
        print("    路径: {}".format(pime_path))
    else:
        print("    PIME 未安装！请下载安装:")
        print("    https://github.com/EasyIME/PIME/releases/tag/v1.3.0-stable")

    # B. ai_ime 部署
    ime_ok, ime_info = check_ime_deployed(pime_path)
    report["ime_deployed"] = ime_ok
    report["ime_info"] = ime_info
    status = "OK" if ime_ok else "FAIL"
    print("\n[B] ai_ime 部署检查: {}".format(status))
    if pime_ok:
        print("    目标: {}".format(ime_info.get("target", "")))
        if ime_info.get("missing"):
            print("    缺失文件: {}".format(ime_info["missing"]))
        else:
            print("    文件: {}".format(ime_info.get("files", [])))
    else:
        print("    PIME 未安装，无法部署")

    # C. PIMELauncher
    launcher_ok = check_launcher_running()
    report["launcher_running"] = launcher_ok
    status = "OK" if launcher_ok else "FAIL"
    print("\n[C] PIMELauncher 运行: {}".format(status))
    if not launcher_ok:
        print("    PIMELauncher 未运行，请注销重登或手动启动")

    # D. 按键日志
    log_ok, log_info = check_key_log()
    report["key_log"] = log_info
    status = "OK" if log_ok else "PENDING"
    print("\n[D] 按键回调日志: {}".format(status))
    print("    日志文件: {}".format(log_info.get("log_file", "")))
    if log_info.get("exists"):
        print("    日志行数: {}".format(log_info["lines"]))
        print("    包含按键事件: {}".format(log_info["has_key_event"]))
        if log_info.get("last_5_lines"):
            print("    最后几行:")
            for line in log_info["last_5_lines"]:
                print("      {}".format(line))
    else:
        print("    日志尚未生成")
        print("    请切换到 AI输入法，在记事本中打字后再运行此脚本")

    # 总结
    all_ok = pime_ok and ime_ok and launcher_ok and log_ok
    report["overall"] = "PASS" if all_ok else "INCOMPLETE"

    print("\n" + "=" * 60)
    if all_ok:
        print("[PASS] 第0期验证通过！可以进入第1期开发")
    elif pime_ok and ime_ok and launcher_ok and not log_ok:
        print("[PENDING] 部署完成，请手动打字测试后重新运行验证")
        print("         测试步骤:")
        print("         1. 打开记事本")
        print("         2. 切换到 AI输入法 (Win+Space)")
        print("         3. 输入 hello，按空格")
        print("         4. 重新运行: python validate_phase0.py")
    else:
        print("[INCOMPLETE] 第0期验证未完成，请按上述提示修复")
    print("=" * 60)

    # 保存 JSON 报告
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "report_{}.json".format(
                                   datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n报告已保存: {}".format(report_path))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

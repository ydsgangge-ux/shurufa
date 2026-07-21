# -*- coding: utf-8 -*-
"""本地 LLM 客户端（通过 HTTP 调用 local_llm_server.py）

为什么用 HTTP 而不是内嵌加载？
- PIME 的 Python 是 3.8 32位，无法运行 llama-cpp-python
- 用系统 Python 单独跑 local_llm_server.py，PIME 通过 HTTP 调用
- 比 Ollama 更轻量（没有进程管理开销）

自动启动：
- 检测服务没运行时，自动用系统 Python 拉起 local_llm_server.py
- 无需手动启动
"""

import json
import urllib.request
import urllib.error
import os
import subprocess
import sys
import time
from typing import Optional, List

LOCAL_LLM_HOST = "http://localhost:11435"
DEFAULT_TIMEOUT = 2.0


def debug_log(msg):
    """写入调试日志"""
    try:
        log_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PIME", "Log")
        os.makedirs(log_dir, exist_ok=True)
        import datetime
        ts = datetime.datetime.now().isoformat(timespec="milliseconds")
        with open(os.path.join(log_dir, "ai_ime_debug.log"), "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(ts, msg))
    except Exception:
        pass


def _find_system_python():
    """查找系统 Python（非 PIME 的 3.8 32位）"""
    # 1. 环境变量中的 python
    for name in ["python", "python3"]:
        try:
            result = subprocess.run(
                [name, "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                py_path = result.stdout.strip()
                # 确认不是 PIME 的 Python
                if "PIME" not in py_path:
                    return name
        except Exception:
            pass
    return None


def _find_server_script():
    """查找 local_llm_server.py 脚本路径"""
    # 1. 在项目根目录查找
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(base_dir, "local_llm_server.py")
    if os.path.isfile(script):
        return script

    # 2. 在 ai_ime 同级目录查找
    parent = os.path.dirname(base_dir)
    script = os.path.join(parent, "local_llm_server.py")
    if os.path.isfile(script):
        return script

    return None


def _find_model_path():
    """查找 .gguf 模型文件"""
    search_dirs = [
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models"),
        os.path.expanduser("~"),
    ]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".gguf"):
                return os.path.join(d, f)
        # 下一级
        models_dir = os.path.join(d, "models")
        if os.path.isdir(models_dir):
            for f in os.listdir(models_dir):
                if f.endswith(".gguf"):
                    return os.path.join(models_dir, f)
    return None


class LocalLLMClient:
    """本地 LLM HTTP 客户端（带自动启动）"""

    def __init__(self, host: str = None, timeout: float = None):
        self.host = host or LOCAL_LLM_HOST
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._available = None
        self._server_started = False  # 是否已尝试自动启动
        self._start_time = 0          # 自动启动时间（用于延迟检测）

    def _try_auto_start(self):
        """尝试自动启动 local_llm_server.py

        策略：
        1. 查找系统 Python（64位，能跑 llama-cpp-python）
        2. 后台启动服务（不阻塞输入法）
        3. 不等待就绪，后续 is_available() 调用会自动检测
        """
        if self._server_started:
            return
        self._server_started = True

        python = _find_system_python()
        if not python:
            debug_log("LocalLLM: no system Python found for auto-start")
            return

        script = _find_server_script()
        if not script:
            debug_log("LocalLLM: no local_llm_server.py found for auto-start")
            return

        model = _find_model_path()
        cmd = [python, script, "--port", "11435"]
        if model:
            cmd.extend(["--model", model])

        try:
            # 后台启动，不阻塞
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                cmd,
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._start_time = time.time()
            debug_log("LocalLLM: auto-started {} (model={})".format(python, model or "auto"))
        except Exception as e:
            debug_log("LocalLLM: auto-start failed: {}".format(e))

    def chat(self, messages: List[dict], max_tokens: int = 20) -> Optional[str]:
        """调用本地 LLM chat API"""
        # 如果服务不可用且未尝试启动，先尝试自动启动
        if self._available is None:
            self.is_available()

        try:
            url = "{}/api/chat".format(self.host)
            payload = json.dumps({
                "messages": messages,
                "max_tokens": max_tokens,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={
                "Content-Type": "application/json",
            })
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")
            self._available = True
            return content.strip() if content else None
        except Exception:
            self._available = False
            return None

    def is_available(self) -> bool:
        """检查本地 LLM 服务是否可用，不可用则尝试自动启动

        每次都动态检测（不缓存），因为服务可能随时启动/停止
        """
        # 先快速检查当前状态
        try:
            url = "{}/api/health".format(self.host)
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=1.0)
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("model_loaded"):
                self._available = True
                return True
        except Exception:
            pass

        # 服务没运行，尝试自动启动（只试一次）
        if not self._server_started:
            self._try_auto_start()

        return self._available or False


# 全局单例
_local_llm = None

def get_local_llm() -> LocalLLMClient:
    global _local_llm
    if _local_llm is None:
        _local_llm = LocalLLMClient()
    return _local_llm

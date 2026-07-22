# -*- coding: utf-8 -*-
"""Ollama HTTP API 客户端

调用本地 Ollama 服务进行推理。
特点：
1. 超时控制（默认 3s，异步调用不阻塞用户）
2. 失败不阻塞（返回 None）
3. 关闭 thinking 模式（think:false）提速
4. 优先使用 chat 接口（支持 system prompt + few-shot）
"""

import json
import urllib.request
import urllib.error
import time
from typing import Optional, List

# Ollama 默认配置
OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:0.6b"
DEFAULT_TIMEOUT = 3.0  # 3秒（异步调用，不影响用户打字）


class OllamaClient:
    """Ollama HTTP API 客户端"""

    def __init__(self, host: str = None, model: str = None, timeout: float = None):
        self.host = host or OLLAMA_HOST
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._last_check_time = 0
        self._last_check_result = False

    def generate(self, prompt: str, max_tokens: int = 50) -> Optional[str]:
        """生成文本（单次请求，使用 generate 接口）

        Args:
            prompt: 输入提示词
            max_tokens: 最大生成 token 数

        Returns:
            生成的文本，失败返回 None
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,  # 关闭思考模式，直接输出
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.3,
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get('response', '').strip() or None
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError, OSError):
            return None

    def chat(self, messages: List[dict], max_tokens: int = 50) -> Optional[str]:
        """对话模式（推荐使用，支持 system + few-shot）

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            max_tokens: 最大生成 token 数

        Returns:
            生成的文本，失败返回 None
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,  # 关闭思考模式
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.2,  # 更稳定
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                content = result.get('message', {}).get('content', '').strip()
                return content or None
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError, OSError):
            return None

    def is_available(self) -> bool:
        """检查 Ollama 服务是否可用（缓存 5 秒，避免卡顿）"""
        now = time.time()
        if now - self._last_check_time < 5.0:
            return self._last_check_result

        self._last_check_time = now
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method='GET')
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                self._last_check_result = (resp.status == 200)
                return self._last_check_result
        except Exception:
            self._last_check_result = False
            return False


# 全局单例（避免重复创建）
_client = None

def get_client() -> OllamaClient:
    """获取全局 Ollama 客户端"""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client
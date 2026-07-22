# -*- coding: utf-8 -*-
"""云端 API 客户端（OpenAI 兼容）

支持：
- DeepSeek V4 Flash（默认，关闭思考模式）
- Qwen3 / Qwen3.5（关闭思考模式）
- OpenAI / 兼容 API
- 任何 OpenAI 兼容端点（vLLM, Ollama 等）

思考模式关闭方式（按模型不同）：
- DeepSeek V4/R1: thinking: {"type": "disabled"}
- Qwen3/Qwen3.5: Prompt 末尾追加 /no_think + extra_body chat_template_kwargs
- 其他推理模型: Prompt 末尾追加 /no_think

用法：
1. 创建 ~/.ai_ime/api_config.json 配置 api_key
2. 输入法自动加载配置
"""

import json
import urllib.request
import urllib.error
import os
from typing import Optional, List

# 默认模型
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"


class CloudClient:
    """OpenAI 兼容的云端 API 客户端"""

    def __init__(self, api_key: str = None, api_base: str = None,
                 model: str = None, timeout: float = None):
        self.api_key = api_key or ""
        self.api_base = (api_base or DEFAULT_API_BASE).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout or 5.0

    def _is_thinking_model(self, model: str) -> bool:
        """判断是否为默认开启 thinking 的推理模型

        包括：
        - DeepSeek V3/R1/V4/Flash/Reasoner
        - Qwen3 / Qwen3.5（含 Qwen3-8B, Qwen3-30B 等）
        """
        m = model.lower()
        # DeepSeek 推理系列
        if "deepseek" in m and any(kw in m for kw in ["v3", "r1", "v4", "flash", "reasoner"]):
            return True
        # Qwen3 / Qwen3.5 系列（所有 Qwen3 都默认开启 thinking）
        if "qwen3" in m or "qwen-3" in m:
            return True
        # QwQ（Qwen 推理模型）
        if "qwq" in m:
            return True
        return False

    def _is_qwen_thinking_model(self, model: str) -> bool:
        """判断是否为 Qwen3 系列推理模型"""
        m = model.lower()
        return "qwen3" in m or "qwen-3" in m or "qwq" in m

    def _is_deepseek_reasoning_model(self, model: str) -> bool:
        """判断是否为 DeepSeek 推理模型"""
        m = model.lower()
        if "deepseek" not in m:
            return False
        return any(kw in m for kw in ["v3", "r1", "v4", "flash", "reasoner"])

    def chat(self, messages: List[dict], max_tokens: int = 20) -> Optional[str]:
        """调用云端 chat API

        自动关闭推理模型的思考模式：
        - DeepSeek V4: thinking: {"type": "disabled"}
        - Qwen3/3.5: Prompt 末尾追加 /no_think + extra_body
        - 思考消耗大量 token（占 70%+），输入法场景必须关闭
        """
        if not self.api_key:
            return None

        url = "{}/chat/completions".format(self.api_base)

        # 处理模型名：旧名 deepseek-chat → deepseek-v4-flash
        model = self.model
        if model.lower() == "deepseek-chat":
            model = "deepseek-v4-flash"

        # 拷贝 messages，可能需要追加 /no_think
        msgs = [dict(m) for m in messages]

        # Qwen3 系列：在最后一条 user 消息末尾追加 /no_think
        if self._is_qwen_thinking_model(model):
            if msgs and msgs[-1].get("role") == "user":
                original = msgs[-1].get("content", "")
                if "/no_think" not in original:
                    msgs[-1]["content"] = original + " /no_think"

        payload = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": False,
        }

        # DeepSeek V4 系列关闭思考模式
        if self._is_deepseek_reasoning_model(model):
            payload["thinking"] = {"type": "disabled"}

        # Qwen3 系列通过 extra_body 关闭思考模式（vLLM/兼容 API）
        if self._is_qwen_thinking_model(model):
            payload["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.api_key),
        })

        # 云端超时：网络延迟 + 服务端排队
        cloud_timeout = max(self.timeout, 8.0)

        try:
            resp = urllib.request.urlopen(req, timeout=cloud_timeout)
            data = json.loads(resp.read().decode("utf-8"))
            message = data["choices"][0]["message"]
            # 优先取 content，兜底取 reasoning_content（非思考模式下不会有）
            content = message.get("content", "") or message.get("reasoning_content", "")
            return content.strip() if content else None
        except urllib.error.HTTPError as e:
            return None
        except Exception:
            return None

    def is_available(self) -> bool:
        """检查 API 是否可用（有 key）"""
        return bool(self.api_key)


def load_cloud_config() -> CloudClient:
    """从配置文件加载云端 API 配置

    配置文件搜索顺序：
    1. 用户目录：~/.ai_ime/api_config.json（推荐，不在 Program Files 里）
    2. 程序目录：ai_ime/data/api_config.json（兼容旧方式）

    格式：
    {
        "api_key": "sk-xxx",
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-flash",
        "timeout": 5.0
    }
    """
    # 1. 用户目录（推荐，更安全）
    user_config = os.path.join(
        os.path.expanduser("~"), ".ai_ime", "api_config.json"
    )
    # 2. 程序目录（兼容）
    app_config = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "api_config.json"
    )

    for config_path in [user_config, app_config]:
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return CloudClient(
                    api_key=cfg.get("api_key", ""),
                    api_base=cfg.get("api_base", DEFAULT_API_BASE),
                    model=cfg.get("model", DEFAULT_MODEL),
                    timeout=cfg.get("timeout", 5.0),
                )
            except Exception:
                pass

    # 无配置文件 → 不可用
    return CloudClient()


# 全局单例
_cloud_client = None

def get_cloud_client() -> CloudClient:
    """获取全局云端客户端"""
    global _cloud_client
    if _cloud_client is None:
        _cloud_client = load_cloud_config()
    return _cloud_client

def reload_cloud_config():
    """重新加载配置（修改 api_config.json 后调用）"""
    global _cloud_client
    _cloud_client = load_cloud_config()

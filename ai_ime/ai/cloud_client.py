# -*- coding: utf-8 -*-
"""云端 API 客户端（OpenAI 兼容）

支持：
- DeepSeek V4 Flash（默认，关闭思考模式）
- OpenAI / 兼容 API
- 任何 OpenAI 兼容端点

注意：
- deepseek-chat 将于 2026-07-24 下线
- 统一使用 deepseek-v4-flash + thinking:disabled
- 推理模型的 thinking 过程消耗大量 token，输入法场景必须关闭

用法：
1. 创建 ~/.ai_ime/api_config.json 配置 api_key
2. 输入法自动加载配置
"""

import json
import urllib.request
import urllib.error
import os
from typing import Optional, List

# 默认模型（deepseek-chat 已下线，统一用 v4-flash 关闭思考）
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

    def _is_deepseek_reasoning_model(self, model: str) -> bool:
        """判断是否为 DeepSeek 推理模型（默认开启 thinking）"""
        if "deepseek" not in model.lower():
            return False
        return any(kw in model.lower()
                   for kw in ["v3", "r1", "v4", "flash", "reasoner"])

    def chat(self, messages: List[dict], max_tokens: int = 20) -> Optional[str]:
        """调用云端 chat API

        对于 DeepSeek V4 系列模型，自动关闭思考模式：
        - thinking 消耗大量 token（占 70%+），输入法场景不需要
        - 正确格式：thinking: {"type": "disabled"}
        - 兼容旧模型名 deepseek-chat（已下线）
        """
        if not self.api_key:
            return None

        url = "{}/chat/completions".format(self.api_base)

        # 处理模型名：旧名 deepseek-chat → deepseek-v4-flash
        model = self.model
        if model.lower() == "deepseek-chat":
            model = "deepseek-v4-flash"

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": False,
        }

        # DeepSeek V4 系列必须关闭思考模式，否则 thinking 吃掉所有 token
        if self._is_deepseek_reasoning_model(model):
            payload["thinking"] = {"type": "disabled"}

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

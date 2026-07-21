# -*- coding: utf-8 -*-
"""AI 预测模块 - 双引擎（本地 Ollama + 云端 API）

场景：
1. 整句预测：根据拼音和上下文生成最可能的句子（云端）
2. 上下文续写：预测下一个词（云端/本地）
3. 兜底生成：词库无候选时 AI 补全（云端）

本地模型：qwen3:0.6b（Ollama）
云端模型：DeepSeek / OpenAI 兼容 API
"""

from .ollama_client import OllamaClient
from .cloud_client import CloudClient
from .local_llm_client import LocalLLMClient
from .predictor import AIPredictor

__all__ = ['OllamaClient', 'CloudClient', 'LocalLLMClient', 'AIPredictor']
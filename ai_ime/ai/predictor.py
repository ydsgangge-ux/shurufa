# -*- coding: utf-8 -*-
"""AI 预测器 v6 - 自然续写

核心改动（相比 v5）：
1. few-shot 示例从"俗语接龙"改为"自然口语续写"
2. 上下文长度从 20 字扩到 50 字
3. 结果解析允许单字、子串去重
4. 去掉互相矛盾的 system prompt

引擎优先级：
- 上下文续写：本地 llama-cpp → 云端 API（本地更快）
- 整句预测：云端 API → 本地 LLM（云端更准）
- 兜底生成：云端 API（只有云端能做拼音转中文）
"""

import threading
import re
import time
from typing import List, Optional
from .local_llm_client import get_local_llm
from .cloud_client import get_cloud_client
from .ollama_client import get_client as get_ollama


# ===== Few-shot 示例 =====
# 全部改成"自然口语续写"，不教俗语/歇后语
# 示例特点：
# - 输入是日常说话的前半段（不是名句）
# - 输出是1-3个字的自然续写（短、口语化）
# - 覆盖不同场景：日常、工作、疑问

# 本地小模型：最少示例，最短输出
CONTEXT_EXAMPLES_LOCAL = [
    ("现在用的是", "国标"),
    ("绝缘电阻要求", "不低于"),
    ("这批货什么时候", "到"),
    ("我想", "回家"),
    ("今天天气", "不错"),
]

# 云端大模型：更多示例
CONTEXT_EXAMPLES_CLOUD = [
    ("现在用的是", "国标线材"),
    ("绝缘电阻要求", "不低于100兆欧"),
    ("这批货什么时候", "发货"),
    ("我想", "回家"),
    ("今天天气", "不错"),
    ("下周", "开会"),
    ("这个问题", "怎么解决"),
]

# 整句预测（云端专用）
SENTENCE_EXAMPLES_CLOUD = [
    ("woxianghuijia", "我想回家"),
    ("xiacikaihui", "下次开会"),
    ("zheigeiwenti", "这个问题"),
]


class AIPredictor:
    """AI 预测器 v6 - 自然续写"""

    # 上下文长度：传入最近多少字给 AI
    CONTEXT_LEN = 50

    def __init__(self):
        self.local_llm = get_local_llm()
        self.cloud = get_cloud_client()
        self.ollama = get_ollama()
        self._context = ""
        self._lock = threading.Lock()

        # 异步结果
        self._ai_results = []
        self._ai_ready = False
        self._ai_request_id = 0

        # 引擎状态日志
        engines = []
        if self.local_llm.is_available():
            engines.append("local-llm")
        if self.cloud.is_available():
            engines.append("cloud")
        if self.ollama.is_available():
            engines.append("ollama")
        self._engines = engines

    def set_context(self, text: str):
        with self._lock:
            self._context = text[-200:] if len(text) > 200 else text

    def get_context(self) -> str:
        with self._lock:
            return self._context

    def get_engines(self) -> str:
        return "+".join(self._engines) if self._engines else "none"

    def _get_context_short(self) -> str:
        """取最近 CONTEXT_LEN 字的上下文"""
        ctx = self.get_context()
        return ctx[-self.CONTEXT_LEN:] if len(ctx) > self.CONTEXT_LEN else ctx

    def request_context_predict(self, pinyin: str, n: int = 3):
        """异步请求上下文续写（本地优先，云端降级）"""
        context = self.get_context()
        if not context or len(context) < 2:
            return

        with self._lock:
            self._ai_request_id += 1
            request_id = self._ai_request_id
            self._ai_ready = False
            self._ai_results = []

        def _worker():
            result = None
            ctx_short = self._get_context_short()

            # 1. 优先本地 LLM（最快）
            try:
                if self.local_llm.is_available():
                    messages = self._build_local_context_messages(ctx_short, n)
                    result = self.local_llm.chat(messages, max_tokens=12)
                    if result:
                        self._debug_log("local-llm result: '{}' (ctx='{}')".format(result, ctx_short[-15:]))
            except Exception:
                result = None

            # 2. 降级云端
            if not result:
                try:
                    if self.cloud.is_available():
                        messages = self._build_cloud_context_messages(ctx_short, n)
                        result = self.cloud.chat(messages, max_tokens=60)
                        if result:
                            self._debug_log("cloud result: '{}' (ctx='{}')".format(result, ctx_short[-15:]))
                except Exception:
                    result = None

            # 3. 降级 Ollama
            if not result:
                try:
                    if self.ollama.is_available():
                        messages = self._build_ollama_context_messages(ctx_short, n)
                        result = self.ollama.chat(messages, max_tokens=15)
                        if result:
                            self._debug_log("ollama result: '{}'".format(result))
                except Exception:
                    result = None

            with self._lock:
                if request_id != self._ai_request_id:
                    return
                if result:
                    words = self._parse_result(result, n, context=ctx_short)
                    self._ai_results = words
                else:
                    self._debug_log("ALL engines failed. local={}, cloud={}, ollama={}".format(
                        self.local_llm.is_available(), self.cloud.is_available(), self.ollama.is_available()))
                self._ai_ready = True

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def request_sentence_predict(self, pinyin: str, n: int = 3):
        """异步请求整句预测（云端优先，本地降级）"""
        with self._lock:
            self._ai_request_id += 1
            request_id = self._ai_request_id
            self._ai_ready = False
            self._ai_results = []

        def _worker():
            result = None
            context = self.get_context()

            # 1. 云端（拼音转中文只有大模型能做）
            if self.cloud.is_available():
                messages = self._build_sentence_messages(pinyin, context, n)
                result = self.cloud.chat(messages, max_tokens=120)

            # 2. 本地 LLM 试试（效果差但比没有强）
            if not result and self.local_llm.is_available():
                messages = self._build_local_sentence_messages(pinyin, n)
                result = self.local_llm.chat(messages, max_tokens=20)

            with self._lock:
                if request_id != self._ai_request_id:
                    return
                if result:
                    words = self._parse_result(result, n)
                    self._ai_results = words
                self._ai_ready = True

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def request_fallback_predict(self, pinyin: str, n: int = 3):
        """异步请求兜底生成（只有云端能做拼音转中文）"""
        with self._lock:
            self._ai_request_id += 1
            request_id = self._ai_request_id
            self._ai_ready = False
            self._ai_results = []

        def _worker():
            result = None

            if self.cloud.is_available():
                messages = self._build_fallback_messages_cloud(pinyin, n)
                result = self.cloud.chat(messages, max_tokens=100)

            with self._lock:
                if request_id != self._ai_request_id:
                    return
                if result:
                    words = self._parse_result(result, n)
                    self._ai_results = words
                self._ai_ready = True

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def poll_ai_results(self):
        """轮询 AI 结果（主线程调用）"""
        with self._lock:
            if not self._ai_ready:
                return []
            results = list(self._ai_results)
            self._ai_ready = False
            self._ai_results = []
        return results

    def cancel_request(self):
        with self._lock:
            self._ai_request_id += 1
            self._ai_ready = False
            self._ai_results = []

    # ===== Prompt 构建 =====

    def _build_local_context_messages(self, context_short: str, n: int) -> List[dict]:
        """本地 LLM 上下文续写

        设计要点：
        - system prompt 只说"续写"，不说"一个词"（避免和小模型能力矛盾）
        - 示例全用自然口语（不教俗语）
        - 传入完整上下文（50字）
        """
        messages = [
            {"role": "system", "content": "续写：接下去最可能输入的1-3个字"},
        ]
        for user_text, assistant_text in CONTEXT_EXAMPLES_LOCAL:
            messages.append({"role": "user", "content": user_text})
            messages.append({"role": "assistant", "content": assistant_text})
        messages.append({"role": "user", "content": context_short})
        return messages

    def _build_ollama_context_messages(self, context_short: str, n: int) -> List[dict]:
        """Ollama 上下文续写"""
        messages = [
            {"role": "system", "content": "续写：接下去最可能输入的1-3个字"},
        ]
        for user_text, assistant_text in CONTEXT_EXAMPLES_LOCAL:
            messages.append({"role": "user", "content": user_text})
            messages.append({"role": "assistant", "content": assistant_text})
        messages.append({"role": "user", "content": context_short})
        return messages

    def _build_cloud_context_messages(self, context_short: str, n: int) -> List[dict]:
        """云端上下文续写

        设计要点：
        - 明确要求"短续写"，不要求"一个词"（词/短语都可以）
        - 每行一个，好解析
        - 示例覆盖日常+工作场景
        """
        messages = [
            {"role": "system", "content": "根据已输入文字，续写接下来最可能输入的1-{}个短语（1-4字）。每行一个，不要编号，不要解释，不要重复输入内容".format(n)},
        ]
        for user_text, assistant_text in CONTEXT_EXAMPLES_CLOUD:
            messages.append({"role": "user", "content": "已输入：{}".format(user_text)})
            messages.append({"role": "assistant", "content": assistant_text})
        messages.append({"role": "user", "content": "已输入：{}".format(context_short)})
        return messages

    def _build_sentence_messages(self, pinyin: str, context: str, n: int) -> List[dict]:
        """云端整句预测"""
        messages = [
            {"role": "system", "content": "你是中文输入法AI。根据拼音和上下文，推测用户想输入的完整中文句子。每行一个，最多{}个，不要编号，不要解释".format(n)}
        ]
        for pinyin_in, chinese_out in SENTENCE_EXAMPLES_CLOUD:
            messages.append({"role": "user", "content": pinyin_in})
            messages.append({"role": "assistant", "content": chinese_out})

        if context and len(context) >= 2:
            ctx_short = context[-50:] if len(context) > 50 else context
            messages.append({"role": "user", "content": "上下文：{}\n拼音：{}".format(ctx_short, pinyin)})
        else:
            messages.append({"role": "user", "content": pinyin})
        return messages

    def _build_local_sentence_messages(self, pinyin: str, n: int) -> List[dict]:
        """本地整句预测（效果差，聊胜于无）"""
        messages = [
            {"role": "system", "content": "根据拼音输出中文，只输出中文"},
            {"role": "user", "content": "woxianghuijia"},
            {"role": "assistant", "content": "我想回家"},
            {"role": "user", "content": pinyin},
        ]
        return messages

    def _build_fallback_messages_cloud(self, pinyin: str, n: int) -> List[dict]:
        """云端兜底"""
        messages = [
            {"role": "system", "content": "将拼音转为最可能的中文，每行一个，最多{}个，不要解释".format(n)},
            {"role": "user", "content": "meiyouyongqi"},
            {"role": "assistant", "content": "没有勇气"},
            {"role": "user", "content": pinyin},
        ]
        return messages

    # ===== 结果解析 =====

    def _parse_result(self, result: str, n: int, context: str = "") -> List[str]:
        """解析 AI 输出，过滤无效结果

        改进（v6）：
        - 允许单字（"好""到""是" 等常见单字很有价值）
        - 子串去重：AI 重复输出输入内容的部分（如 ctx="今天天气" → AI输出"天气"应保留）
        - AI 输出包含输入内容时，只保留新增部分
        """
        # 先尝试：如果整行就是 1-4 个中文字，直接用
        stripped = result.strip()
        if re.match(r'^[\u4e00-\u9fff]{1,4}$', stripped):
            # 检查是否和上下文完全重复
            if context and stripped == context[-len(stripped):]:
                return []
            return [stripped]

        # 多行/多词解析
        parts = re.split(r'[\s\n、，,]+', stripped)
        words = []
        seen = set()
        for p in parts:
            p = p.strip()
            # 去掉编号
            while p and p[0].isdigit():
                p = p.lstrip('0123456789.、')
                p = p.strip()
            if not p:
                continue
            # 必须含中文
            if not re.search(r'[\u4e00-\u9fff]', p):
                continue
            # 去掉纯中文标点
            if re.match(r'^[\u3000-\u303f\uff00-\uffef]+$', p):
                continue
            # 去掉和完整上下文相同的输出
            if context and p == context:
                continue
            # 如果 AI 输出包含了上下文（如"今天天气好"但 ctx="今天天气"），只取新增部分
            if context and p.startswith(context[-len(p):]) and len(p) > len(context[-len(p):]):
                p = p[len(context[-len(p):]):]
            # 长度限制：1-6字
            if not re.match(r'^[\u4e00-\u9fff]{1,6}$', p):
                continue
            if p in seen:
                continue
            seen.add(p)
            words.append(p)
        return words[:n]

    # ===== 工具 =====

    def _debug_log(self, msg):
        """写入调试日志"""
        try:
            import os
            log_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PIME", "Log")
            os.makedirs(log_dir, exist_ok=True)
            import datetime
            ts = datetime.datetime.now().isoformat(timespec="milliseconds")
            with open(os.path.join(log_dir, "ai_ime_debug.log"), "a", encoding="utf-8") as f:
                f.write("[AI] {}\n".format(msg))
        except Exception:
            pass


# 全局单例
_predictor = None

def get_predictor() -> AIPredictor:
    global _predictor
    if _predictor is None:
        _predictor = AIPredictor()
    return _predictor

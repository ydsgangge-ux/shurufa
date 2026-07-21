# -*- coding: utf-8 -*-
"""词库自动扩充模块

根据用户打字习惯和内容，使用大模型自动扩充词库。

工作方式：
1. 收集用户最近打字记录（从 user_memory.json 和上下文）
2. 定期（半天/一天）触发一次扩充
3. 让大模型根据打字内容生成相关词汇
4. 生成的词自动加入用户词库（freq 9999）

触发方式：
- 用户上屏后累积文字，达到阈值时触发
- 不打字时不消耗资源

引擎选择：
- 云端 API（DeepSeek 等）：最准，能生成成语/俗语/专业术语
- 本地 LLM（qwen2.5-0.5b）：凑合用，至少能联想
"""

import json
import os
import re
import time
import threading
from typing import List, Optional

# 延迟导入，避免循环依赖
def _get_cloud_client():
    try:
        from .cloud_client import get_cloud_client
        return get_cloud_client()
    except Exception:
        return None

def _get_local_llm():
    try:
        from .local_llm_client import get_local_llm
        return get_local_llm()
    except Exception:
        return None


class LexiconExpander:
    """词库自动扩充器"""

    # 扩充触发阈值：累积上屏字符数
    TRIGGER_CHARS = 1000  # 每累积 1000 字触发一次
    # 最小触发间隔（秒），避免频繁调用
    MIN_INTERVAL = 600    # 10 分钟

    def __init__(self, memory_path: str, dict_loader=None):
        self._memory_path = memory_path
        self._dict_loader = dict_loader
        self._accumulated = ""       # 累积的上屏文字
        self._last_expand_time = 0   # 上次扩充时间
        self._lock = threading.Lock()
        self._expanding = False      # 是否正在扩充中
        self._history = []           # 最近打字历史（用于扩充）

    def accumulate(self, text: str):
        """累积用户上屏的文字，达到阈值时触发扩充"""
        if not text or len(text) < 2:
            return

        with self._lock:
            self._accumulated += text
            self._history.append(text)
            # 只保留最近 50 条
            if len(self._history) > 50:
                self._history = self._history[-50:]

            should_trigger = (
                len(self._accumulated) >= self.TRIGGER_CHARS
                and time.time() - self._last_expand_time >= self.MIN_INTERVAL
                and not self._expanding
            )

        if should_trigger:
            self._trigger_expand()

    def _trigger_expand(self):
        """后台触发词库扩充"""
        with self._lock:
            if self._expanding:
                return
            self._expanding = True
            text_to_expand = self._accumulated
            self._accumulated = ""

        thread = threading.Thread(
            target=self._do_expand,
            args=(text_to_expand,),
            daemon=True,
        )
        thread.start()

    def _do_expand(self, text: str):
        """执行词库扩充（后台线程）"""
        try:
            # 1. 提取用户最近打字的关键词
            recent_text = "".join(self._history[-20:])
            if len(recent_text) < 10:
                return

            # 2. 构造 prompt
            prompt = self._build_prompt(recent_text)

            # 3. 尝试各引擎
            words = None

            # 优先云端
            cloud = _get_cloud_client()
            if cloud and cloud.is_available():
                words = self._call_cloud(cloud, prompt)

            # 云端失败或不可用，尝试本地
            if not words:
                local = _get_local_llm()
                if local and local.is_available():
                    words = self._call_local(local, prompt)

            # 4. 写入词库
            if words:
                self._save_to_lexicon(words)

        except Exception:
            pass
        finally:
            with self._lock:
                self._expanding = False
                self._last_expand_time = time.time()

    def _build_prompt(self, recent_text: str) -> str:
        """构造扩充词库的 prompt"""
        # 截取最近 200 字
        sample = recent_text[-200:] if len(recent_text) > 200 else recent_text
        return (
            "根据以下用户最近输入的中文内容，生成10个相关的词汇（成语、俗语、专业术语、常用短语均可）。\n"
            "只输出词汇，用逗号分隔，不要解释。\n\n"
            "用户输入：{}\n\n相关词汇：".format(sample)
        )

    def _call_cloud(self, cloud, prompt: str) -> Optional[List[str]]:
        """调用云端 API"""
        try:
            messages = [
                {"role": "system", "content": "你是一个中文词汇专家。根据上下文生成相关词汇。只输出词汇，用逗号分隔。"},
                {"role": "user", "content": prompt},
            ]
            result = cloud.chat(messages, max_tokens=200)
            if result:
                return self._parse_words(result)
        except Exception:
            pass
        return None

    def _call_local(self, local, prompt: str) -> Optional[List[str]]:
        """调用本地 LLM"""
        try:
            messages = [
                {"role": "system", "content": "生成相关词汇，逗号分隔"},
                {"role": "user", "content": prompt},
            ]
            result = local.chat(messages, max_tokens=50)
            if result:
                return self._parse_words(result)
        except Exception:
            pass
        return None

    def _parse_words(self, text: str) -> List[str]:
        """从模型输出中解析词汇列表"""
        # 去掉编号、序号等
        text = re.sub(r'[\d①②③④⑤⑥⑦⑧⑨⑩][.、)）]\s*', '', text)
        # 按逗号、顿号分隔
        parts = re.split(r'[,，、；;\n]', text)
        words = []
        for p in parts:
            p = p.strip()
            # 过滤：必须是中文，2-6字
            if p and re.match(r'^[\u4e00-\u9fff]{2,6}$', p):
                words.append(p)
        return words[:10]

    def _save_to_lexicon(self, words: List[str]):
        """将生成的词写入用户词库"""
        if not words or not self._dict_loader:
            return

        # 从 pypinyin 获取拼音
        try:
            from pypinyin import pinyin, Style
        except ImportError:
            return

        added = []
        for word in words:
            # 获取拼音
            py = pinyin(word, style=Style.NORMAL)
            pinyin_key = " ".join(p[0] for p in py)

            # 检查是否已在词库中
            existing = self._dict_loader.lookup(pinyin_key)
            word_in_dict = any(w == word for w, f in existing)
            if word_in_dict:
                continue

            # 添加到词库（freq 9999 确保靠前）
            self._dict_loader.add_entry(pinyin_key, word, 9999)
            added.append(word)

        if added:
            # 写入 user_memory.json
            self._save_phrases(added)

    def _save_phrases(self, words: List[str]):
        """将生成的词保存到 user_memory.json"""
        try:
            from pypinyin import pinyin, Style

            data = {"freq": {}, "phrases": []}
            if os.path.isfile(self._memory_path):
                with open(self._memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            for word in words:
                py = pinyin(word, style=Style.NORMAL)
                pinyin_key = " ".join(p[0] for p in py)
                # 检查是否已存在
                exists = any(
                    p["word"] == word and p["pinyin"] == pinyin_key
                    for p in data.get("phrases", [])
                )
                if not exists:
                    data.setdefault("phrases", []).append({
                        "pinyin": pinyin_key,
                        "word": word,
                        "freq": 9999,
                    })

            os.makedirs(os.path.dirname(self._memory_path), exist_ok=True)
            with open(self._memory_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        except Exception:
            pass

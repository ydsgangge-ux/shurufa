# -*- coding: utf-8 -*-
"""
AI 输入法 v0.7

新增功能：
1. 贪心分词结果始终显示在候选中（songhuodan → 送货单 排在后面）
2. 用户造词：选用贪心分词结果后自动保存，下次输入拼音或简拼都能找到
3. Shift 键切换中/英文模式
4. 回车键上屏原始英文字母（空格上屏候选）
5. Caps Lock 临时切英文/大写
6. 修复 Ctrl/Alt 组合键被拦截
7. 翻页：- 上一页, = 下一页
"""

import os
import sys
import datetime

from textService import TextService

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import config
from pinyin.dict_loader import DictLoader
from pinyin.candidates import get_candidates as get_pinyin_candidates
from pinyin.parser import best_split
from user_memory import UserMemory

# 虚拟键码
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12       # Alt 键
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_CAPITAL = 0x14    # Caps Lock

DEBUG_LOG = True
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PIME", "Log")
LOG_FILE = os.path.join(LOG_DIR, "ai_ime_debug.log")


def debug_log(msg):
    if not DEBUG_LOG:
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().isoformat(timespec="milliseconds")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(timestamp, msg))
    except Exception:
        pass


class AIIMEService(TextService):
    """AI 输入法服务 v0.6"""

    _dict_loader = None
    _user_memory = None

    def __init__(self, client):
        super().__init__(client)
        self.composition = ""
        # 分页状态
        self._all_candidates = []
        self._page = 0
        # 中/英文模式：True=中文, False=英文
        self._chinese_mode = True
        # Shift 键状态跟踪（用于检测单按 Shift 切换）
        self._shift_pressed = False
        self._shift_key_down_time = None
        # 加载词库和用户词频
        if AIIMEService._dict_loader is None:
            loader = DictLoader()
            dict_path = config.get_dict_path()
            loader.load(dict_path)
            AIIMEService._dict_loader = loader
            debug_log("Dict loaded: {} entries from {}".format(loader.size(), dict_path))
        if AIIMEService._user_memory is None:
            AIIMEService._user_memory = UserMemory(config.USER_MEMORY_PATH)
            debug_log("UserMemory loaded: {} freq, {} phrases".format(
                len(AIIMEService._user_memory._freq),
                len(AIIMEService._user_memory._phrases)))
            # 将用户造词加载到 DictLoader 索引中
            for entry in AIIMEService._user_memory.get_phrases():
                AIIMEService._dict_loader.add_entry(
                    entry["pinyin"], entry["word"], entry["freq"])
                debug_log("User phrase loaded: {} -> {} (freq={})".format(
                    entry["pinyin"], entry["word"], entry["freq"]))
        debug_log("AIIMEService.__init__ called")

    def onActivate(self):
        debug_log("onActivate")
        self.isActivated = True

    def onDeactivate(self):
        debug_log("onDeactivate")
        self._clear_composition()

    # ===== 按键过滤 =====

    def filterKeyDown(self, keyEvent):
        """过滤按键：决定是否由输入法处理"""
        code = keyEvent.keyCode
        char_code = keyEvent.charCode

        # 修复问题4：Ctrl/Alt 组合键一律透传（Windows 快捷键不拦截）
        if keyEvent.isKeyDown(VK_CONTROL) or keyEvent.isKeyDown(VK_MENU):
            # Alt 的 VK 是 VK_MENU (0x12)
            return False

        # Shift 键：跟踪按下（用于单按切换中英文）
        if code == VK_SHIFT:
            return True  # 拦截 Shift 以检测单按

        # Caps Lock：拦截以切换英文模式
        if code == VK_CAPITAL:
            return True

        # 英文模式：只处理 Shift 切换回中文，其余全透传
        if not self._chinese_mode:
            return False

        # 以下为中文模式的处理逻辑

        # 正在组合时，处理更多键
        if self.composition:
            if code in (VK_SPACE, VK_RETURN, VK_BACK, VK_ESCAPE):
                return True
            if 0x31 <= code <= 0x39:
                return True
            if code in (config.VK_OEM_MINUS, config.VK_OEM_PLUS):
                return True

        # 字母键 A-Z（无修饰键时）
        if 0x41 <= code <= 0x5A:
            # Shift+字母：不追加到组合串（大写字母不应进入拼音）
            # 但仍由输入法处理，避免应用收到
            if keyEvent.isKeyDown(VK_SHIFT):
                return True
            return True

        # 中文标点全角化（仅在非组合状态下拦截）
        if not self.composition and char_code > 0:
            char = chr(char_code)
            if char in config.PUNCTUATION_MAP:
                return True

        return False

    def onKeyDown(self, keyEvent):
        """处理按键事件"""
        code = keyEvent.keyCode
        char_code = keyEvent.charCode

        debug_log("onKeyDown keyCode=0x{:02X} charCode=0x{:02X} composition='{}' chinese={} shift={}".format(
            code, char_code, self.composition, self._chinese_mode, self._shift_pressed))

        # Shift 键：跟踪按下
        if code == VK_SHIFT:
            if not self._shift_pressed:
                self._shift_pressed = True
                self._shift_key_down_time = datetime.datetime.now()
            return True

        # Caps Lock：切换英文/中文模式
        if code == VK_CAPITAL:
            # Caps Lock 切换时，检查当前状态
            caps_on = keyEvent.isKeyToggled(VK_CAPITAL)
            if caps_on:
                self._chinese_mode = False
                self._clear_composition()
                debug_log("CapsLock ON -> English mode")
            else:
                self._chinese_mode = True
                debug_log("CapsLock OFF -> Chinese mode")
            return True

        # 英文模式：字母直接上屏
        if not self._chinese_mode:
            if 0x41 <= code <= 0x5A:
                if char_code and char_code > 0:
                    char = chr(char_code)  # 保留原始大小写
                else:
                    char = chr(code)
                self.setCommitString(char)
                debug_log("English mode: commit '{}'".format(char))
                return True
            return False

        # 以下为中文模式的按键处理

        # ESC：清空组合串
        if code == VK_ESCAPE:
            self._clear_composition()
            return True

        # 退格：删除最后一个字符
        if code == VK_BACK:
            if self.composition:
                self.composition = self.composition[:-1]
                if self.composition:
                    self._update_composition_display()
                else:
                    self._clear_composition()
            return True

        # 翻页键
        if code == config.VK_OEM_MINUS:
            if self._page > 0:
                self._page -= 1
                self._render_candidates()
            return True
        if code == config.VK_OEM_PLUS:
            if self._all_candidates:
                max_page = max(0, (len(self._all_candidates) - 1) // config.PAGE_SIZE)
                if self._page < max_page:
                    self._page += 1
                    self._render_candidates()
            return True

        # 空格：上屏当前页第一个候选词
        if code == VK_SPACE:
            if self.composition:
                page_items = self._current_page_items()
                if page_items:
                    self._commit_word(page_items[0])
            return True

        # 回车：上屏原始英文字母（不是候选词）
        if code == VK_RETURN:
            if self.composition:
                debug_log("Enter: commit raw '{}'".format(self.composition))
                self.setCommitString(self.composition)
                self.setShowCandidates(False)
                self.composition = ""
                self.setCompositionString("")
                self._all_candidates = []
                self._page = 0
            return True

        # 数字键 1-9：选择当前页候选词
        if 0x31 <= code <= 0x39:
            idx = code - 0x31
            page_items = self._current_page_items()
            if idx < len(page_items):
                self._commit_word(page_items[idx])
                return True
            return False

        # 字母键 A-Z：追加到组合串
        if 0x41 <= code <= 0x5A:
            # Shift+字母：如果是中文模式且有组合串，追加小写
            # 如果没组合串且按了 Shift，可能是想输入大写英文字母
            if keyEvent.isKeyDown(VK_SHIFT) and not self.composition:
                # Shift+字母 在无组合串时：上屏大写字母
                if char_code and char_code > 0:
                    char = chr(char_code)  # Shift+A → 'A'
                else:
                    char = chr(code)
                self.setCommitString(char)
                debug_log("Shift+letter: commit '{}'".format(char))
                return True
            # 追加小写字母到组合串
            if char_code and char_code > 0:
                char = chr(char_code).lower()
            else:
                char = chr(code).lower()
            self.composition += char
            self._update_composition_display()
            return True

        # 中文标点全角化（仅在非组合状态下处理）
        if not self.composition and char_code > 0:
            char = chr(char_code)
            if char in config.PUNCTUATION_MAP:
                full = config.PUNCTUATION_MAP[char]
                debug_log("punct {} -> {}".format(char, full))
                self.setCommitString(full)
                return True

        return False

    def filterKeyUp(self, keyEvent):
        """Shift 键释放时检测单按切换"""
        if keyEvent.keyCode == VK_SHIFT:
            return True  # 拦截 Shift 释放
        return False

    def onKeyUp(self, keyEvent):
        """Shift 键释放：检测单按切换中/英文"""
        if keyEvent.keyCode == VK_SHIFT and self._shift_pressed:
            self._shift_pressed = False
            # 判断是否为"单按 Shift"（按下到释放之间没有其他键）
            # 简化判断：如果从按下到释放时间 < 300ms，认为是单按
            if self._shift_key_down_time:
                elapsed = (datetime.datetime.now() - self._shift_key_down_time).total_seconds()
                if elapsed < 0.3:
                    # 单按 Shift：切换中/英文模式
                    self._chinese_mode = not self._chinese_mode
                    mode = "Chinese" if self._chinese_mode else "English"
                    debug_log("Shift toggle -> {} mode".format(mode))
                    self.showMessage("{} mode".format(mode), 1)
                    if not self._chinese_mode:
                        self._clear_composition()
                self._shift_key_down_time = None
            return True
        return False

    def onCompositionTerminated(self, forced):
        debug_log("onCompositionTerminated forced={}".format(forced))
        self._clear_composition()

    # ===== 内部方法 =====

    def _current_page_items(self):
        if not self._all_candidates:
            return []
        start = self._page * config.PAGE_SIZE
        return self._all_candidates[start:start + config.PAGE_SIZE]

    def _update_composition_display(self):
        """组合串变化时：重新计算候选并渲染第一页"""
        self.setCompositionString(self.composition)
        self.setCompositionCursor(len(self.composition))
        # 计算候选（带词频），应用用户词频加成
        candidates_with_freq = get_pinyin_candidates(
            self.composition,
            AIIMEService._dict_loader,
            config.MAX_TOTAL_CANDIDATES,
            with_freq=True
        )
        candidates_with_freq = AIIMEService._user_memory.apply_bonus(candidates_with_freq)
        self._all_candidates = [word for word, freq in candidates_with_freq]
        self._page = 0
        debug_log("_update_composition_display composition='{}' candidates={}".format(
            self.composition, len(self._all_candidates)))
        self._render_candidates()

    def _render_candidates(self):
        page_items = self._current_page_items()
        if page_items:
            self.setCandidateList(page_items)
            self.setShowCandidates(True)
            self.setSelKeys(config.SEL_KEYS)
        else:
            self.setShowCandidates(False)

    def _commit_word(self, word):
        debug_log("_commit_word word='{}'".format(word))
        AIIMEService._user_memory.record(word)

        # 自动造词：如果提交的词组不在词库中，保存为用户造词
        # 这样下次输入相同拼音或简拼都能找到
        if len(word) >= 2 and self.composition:
            pinyin_syllables = best_split(self.composition)
            pinyin_key = " ".join(pinyin_syllables)
            # 检查词库中是否已有这个词（同拼音下）
            existing = AIIMEService._dict_loader.lookup(pinyin_key)
            word_in_dict = any(w == word for w, f in existing)
            if not word_in_dict:
                freq = AIIMEService._user_memory.add_phrase(pinyin_key, word)
                AIIMEService._dict_loader.add_entry(pinyin_key, word, freq)
                debug_log("User phrase created: {} -> {} (freq={})".format(
                    pinyin_key, word, freq))

        self.setCommitString(word)
        self.setShowCandidates(False)
        self.composition = ""
        self.setCompositionString("")
        self._all_candidates = []
        self._page = 0

    def _clear_composition(self):
        debug_log("_clear_composition")
        self.composition = ""
        self.setCompositionString("")
        self.setShowCandidates(False)
        self._all_candidates = []
        self._page = 0

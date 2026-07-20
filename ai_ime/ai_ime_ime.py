# -*- coding: utf-8 -*-
"""
AI 输入法 v0.9 - 搜狗式交互流程

核心交互（模仿搜狗输入法）：
1. 输入拼音 → 先展示完整句子候选（多种整句解释）
2. 空格选第一个候选，数字键1-9选对应候选
3. 翻页 = 看更多整句候选
4. 翻到底 → 自动进入分词模式（一个词一个词确认）
5. 分词模式中，翻到底 → 拆分成更小词/单字（保底）
6. 回车 → 上屏原始拼音字母
7. ESC → 取消

其他功能：
- Shift 键切换中/英文模式
- Caps Lock 临时切英文/大写
- Ctrl/Alt 组合键透传
- 中文标点全角化
- 用户造词记忆
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
from pinyin.candidates import get_candidates as get_pinyin_candidates, get_segments, generate_interpretations
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
    """AI 输入法服务 v0.8 - 分段确认"""

    _dict_loader = None
    _user_memory = None

    def __init__(self, client):
        super().__init__(client)
        self.composition = ""  # 原始拼音输入
        # 分页状态（整句候选模式用）
        self._all_candidates = []
        self._page = 0
        self._can_enter_seg_mode = False  # 是否可以进入分词模式
        self._seg_candidates_added = False  # 分词候选是否已追加过
        # 分段确认状态
        self._segments = []        # [(pinyin, word, [candidates]), ...]
        self._seg_idx = 0          # 当前段索引
        self._seg_committed = []   # 已确认的词 [(pinyin, word), ...]
        self._seg_page = 0         # 当前段的翻页
        self._seg_mode = False     # 是否在分段确认模式
        # 中/英文模式
        self._chinese_mode = True
        # Shift 键状态
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
            for entry in AIIMEService._user_memory.get_phrases():
                AIIMEService._dict_loader.add_entry(
                    entry["pinyin"], entry["word"], entry["freq"])
        debug_log("AIIMEService.__init__ called")

    def onActivate(self):
        debug_log("onActivate")
        self.isActivated = True

    def onDeactivate(self):
        debug_log("onDeactivate")
        self._clear_composition()

    # ===== 按键过滤 =====

    def filterKeyDown(self, keyEvent):
        code = keyEvent.keyCode
        char_code = keyEvent.charCode

        # Ctrl/Alt 组合键一律透传
        if keyEvent.isKeyDown(VK_CONTROL) or keyEvent.isKeyDown(VK_MENU):
            return False

        # Shift 键：跟踪按下
        if code == VK_SHIFT:
            return True

        # Caps Lock：拦截
        if code == VK_CAPITAL:
            return True

        # 英文模式：全透传
        if not self._chinese_mode:
            return False

        # 正在组合时（包括分段确认模式），处理更多键
        if self.composition:
            if code in (VK_SPACE, VK_RETURN, VK_BACK, VK_ESCAPE):
                return True
            if 0x31 <= code <= 0x39:
                return True
            if code in (config.VK_OEM_MINUS, config.VK_OEM_PLUS):
                return True

        # 字母键 A-Z
        if 0x41 <= code <= 0x5A:
            if keyEvent.isKeyDown(VK_SHIFT):
                return True
            return True

        # 中文标点
        if not self.composition and char_code > 0:
            char = chr(char_code)
            if char in config.PUNCTUATION_MAP:
                return True

        return False

    def onKeyDown(self, keyEvent):
        code = keyEvent.keyCode
        char_code = keyEvent.charCode

        debug_log("onKeyDown keyCode=0x{:02X} charCode=0x{:02X} comp='{}' seg_mode={} seg_idx={}".format(
            code, char_code, self.composition, self._seg_mode, self._seg_idx))

        # Shift 键：跟踪按下
        if code == VK_SHIFT:
            if not self._shift_pressed:
                self._shift_pressed = True
                self._shift_key_down_time = datetime.datetime.now()
            return True

        # Caps Lock：切换中/英文
        if code == VK_CAPITAL:
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
                    char = chr(char_code)
                else:
                    char = chr(code)
                self.setCommitString(char)
                debug_log("English mode: commit '{}'".format(char))
                return True
            return False

        # ===== 以下为中文模式 =====

        # ESC：取消全部
        if code == VK_ESCAPE:
            self._clear_composition()
            return True

        # 退格：分段模式下回退上一段，普通模式删字符
        if code == VK_BACK:
            if self._seg_mode:
                self._seg_backspace()
            else:
                if self.composition:
                    self.composition = self.composition[:-1]
                    if self.composition:
                        self._update_composition_display()
                    else:
                        self._clear_composition()
            return True

        # 翻页键
        if code == config.VK_OEM_MINUS:
            if self._seg_mode:
                if self._seg_page > 0:
                    self._seg_page -= 1
                    self._render_seg_candidates()
            else:
                if self._page > 0:
                    self._page -= 1
                    self._render_candidates()
            return True
        if code == config.VK_OEM_PLUS:
            if self._seg_mode:
                seg = self._segments[self._seg_idx]
                max_page = max(0, (len(seg[3]) - 1) // config.PAGE_SIZE)
                if self._seg_page < max_page:
                    self._seg_page += 1
                    self._render_seg_candidates()
                elif len(seg[1]) >= 2:
                    # 分词模式翻到底 → 拆分当前段
                    self._seg_split_current()
            else:
                if self._all_candidates:
                    max_page = max(0, (len(self._all_candidates) - 1) // config.PAGE_SIZE)
                    if self._page < max_page:
                        self._page += 1
                        self._render_candidates()
                    elif self._can_enter_seg_mode and not self._seg_candidates_added:
                        # 第一次到底 → 追加不同分词方式的整句候选
                        self._enter_seg_mode_from_composition()
                    elif self._can_enter_seg_mode:
                        # 第二次到底 → 进入逐段确认模式
                        segments = get_segments(self.composition, AIIMEService._dict_loader)
                        if segments:
                            self._enter_seg_mode(segments)
            return True

        # 空格：分段模式确认当前段，普通模式上屏第一候选
        if code == VK_SPACE:
            if self.composition:
                if self._seg_mode:
                    self._seg_confirm()
                else:
                    page_items = self._current_page_items()
                    if page_items:
                        self._commit_word(page_items[0])
            return True

        # 回车：上屏原始拼音
        if code == VK_RETURN:
            if self.composition:
                debug_log("Enter: commit raw '{}'".format(self.composition))
                self.setCommitString(self.composition)
                self.setShowCandidates(False)
                self.composition = ""
                self.setCompositionString("")
                self._reset_seg_state()
            return True

        # 数字键 1-9：分段模式选当前段候选，普通模式选候选
        if 0x31 <= code <= 0x39:
            idx = code - 0x31
            if self._seg_mode:
                seg = self._segments[self._seg_idx]
                cands = seg[3]  # 候选词列表（4元素元组的第4项）
                page_start = self._seg_page * config.PAGE_SIZE
                page_cands = cands[page_start:page_start + config.PAGE_SIZE]
                if idx < len(page_cands):
                    # 用选定词替换默认词
                    self._seg_confirm_word(page_cands[idx])
                return True
            else:
                page_items = self._current_page_items()
                if idx < len(page_items):
                    self._commit_word(page_items[idx])
                    return True
                return False

        # 字母键 A-Z：追加到组合串
        if 0x41 <= code <= 0x5A:
            if keyEvent.isKeyDown(VK_SHIFT) and not self.composition:
                if char_code and char_code > 0:
                    char = chr(char_code)
                else:
                    char = chr(code)
                self.setCommitString(char)
                debug_log("Shift+letter: commit '{}'".format(char))
                return True
            if char_code and char_code > 0:
                char = chr(char_code).lower()
            else:
                char = chr(code).lower()
            self.composition += char
            self._update_composition_display()
            return True

        # 中文标点
        if not self.composition and char_code > 0:
            char = chr(char_code)
            if char in config.PUNCTUATION_MAP:
                full = config.PUNCTUATION_MAP[char]
                debug_log("punct {} -> {}".format(char, full))
                self.setCommitString(full)
                return True

        return False

    def filterKeyUp(self, keyEvent):
        if keyEvent.keyCode == VK_SHIFT:
            return True
        return False

    def onKeyUp(self, keyEvent):
        if keyEvent.keyCode == VK_SHIFT and self._shift_pressed:
            self._shift_pressed = False
            if self._shift_key_down_time:
                elapsed = (datetime.datetime.now() - self._shift_key_down_time).total_seconds()
                if elapsed < 0.3:
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

    def _reset_seg_state(self):
        """重置分段确认状态"""
        self._segments = []
        self._seg_idx = 0
        self._seg_committed = []
        self._seg_page = 0
        self._seg_mode = False
        self._all_candidates = []
        self._page = 0
        self._can_enter_seg_mode = False
        self._seg_candidates_added = False

    def _current_page_items(self):
        if not self._all_candidates:
            return []
        start = self._page * config.PAGE_SIZE
        return self._all_candidates[start:start + config.PAGE_SIZE]

    def _update_composition_display(self):
        """组合串变化时：先显示整句候选，翻到底再进分词模式

        搜狗式流程：
        1. 生成多种整句解释 → 作为候选列表
        2. 用户翻页看更多整句
        3. 翻到底 → 进入分词模式
        """
        self.setCompositionString(self.composition)
        self.setCompositionCursor(len(self.composition))

        # 重置分词模式状态
        self._seg_mode = False

        # 生成整句候选（多种解释）
        interpretations = generate_interpretations(
            self.composition, AIIMEService._dict_loader)

        # 也加上传统的词库查找结果
        direct_results = get_pinyin_candidates(
            self.composition, AIIMEService._dict_loader,
            config.MAX_TOTAL_CANDIDATES, with_freq=True)

        # 合并去重：词库直接匹配优先，整句解释次之
        all_results = []
        seen = set()
        for word, freq in direct_results:
            if word not in seen and word != self.composition:
                seen.add(word)
                all_results.append((word, freq))
        for word, freq in interpretations:
            if word not in seen and word != self.composition:
                seen.add(word)
                all_results.append((word, freq))

        # 应用用户词频记忆
        all_results = AIIMEService._user_memory.apply_bonus(all_results)

        self._all_candidates = [word for word, freq in all_results]
        self._page = 0

        # 如果有2+音节，记住可以进分词模式（翻到底时触发）
        self._can_enter_seg_mode = len(self._all_candidates) > 0 and len(self.composition) >= 2

        debug_log("_update_composition_display comp='{}' cands={} seg_ready={}".format(
            self.composition, len(self._all_candidates), self._can_enter_seg_mode))
        self._render_candidates()

    def _enter_seg_mode(self, segments):
        """进入分段确认模式"""
        self._seg_mode = True
        self._segments = segments
        self._seg_idx = 0
        self._seg_committed = []
        self._seg_page = 0
        debug_log("_enter_seg_mode: {} segments, first='{}'".format(
            len(segments), segments[0][2]))
        # 显示完整分词结果
        self._render_seg_display()
        self._render_seg_candidates()

    def _enter_seg_mode_from_composition(self):
        """从整句候选翻到底，先展示不同分词方式的整句候选

        流程（3层递进）：
        1. 整句解释候选（已显示完毕）
        2. 不同分词方式的整句候选（本方法追加）
        3. 再翻到底 → 逐段确认模式
        """
        segments = get_segments(self.composition, AIIMEService._dict_loader)
        if not segments:
            debug_log("_enter_seg_mode_from_composition: no segments")
            return

        # 生成不同分词方式的整句候选
        new_cands = []
        seen = set(self._all_candidates)

        # 默认分词的整句
        default_text = "".join(word for _, _, word, _ in segments)
        if default_text not in seen:
            new_cands.append(default_text)
            seen.add(default_text)

        # 拆分多音节段产生不同的分词整句
        from pinyin.candidates import segment_pinyin
        for i, (py, syl, word, cands) in enumerate(segments):
            if len(syl) >= 2:
                # 拆分：首音节单字 + 剩余贪心分词
                first_segs = segment_pinyin([syl[0]], AIIMEService._dict_loader)
                rest_syls = list(syl[1:])
                for j in range(i + 1, len(segments)):
                    rest_syls.extend(segments[j][1])
                rest_segs = segment_pinyin(rest_syls, AIIMEService._dict_loader)

                # 前面的段不变 + 拆分后的段
                prefix = "".join(segments[k][2] for k in range(i))
                split_text = prefix + first_segs[0][2] + "".join(s[2] for s in rest_segs)
                if split_text not in seen:
                    new_cands.append(split_text)
                    seen.add(split_text)

                # 继续拆分rest中的多音节段（更深层的分词）
                for k, (_, r_syl, _, _) in enumerate(rest_segs):
                    if len(r_syl) >= 2:
                        r_first = segment_pinyin([r_syl[0]], AIIMEService._dict_loader)
                        r_rest_syls = list(r_syl[1:])
                        for m in range(k + 1, len(rest_segs)):
                            r_rest_syls.extend(rest_segs[m][1])
                        r_rest = segment_pinyin(r_rest_syls, AIIMEService._dict_loader)
                        deep_text = prefix + first_segs[0][2] + "".join(
                            rest_segs[n][2] for n in range(k)) + r_first[0][2] + "".join(
                            s[2] for s in r_rest)
                        if deep_text not in seen:
                            new_cands.append(deep_text)
                            seen.add(deep_text)

        # 各段候选词替换变体
        if len(segments) <= 5:
            for i, (py, syl, word, cands) in enumerate(segments):
                for alt_word in cands[1:3]:
                    if alt_word == word:
                        continue
                    parts = [segments[k][2] for k in range(len(segments))]
                    parts[i] = alt_word
                    alt_text = "".join(parts)
                    if alt_text not in seen:
                        new_cands.append(alt_text)
                        seen.add(alt_text)

        if new_cands:
            self._all_candidates.extend(new_cands)
            # 翻到新追加的候选页
            self._page = max(0, (len(self._all_candidates) - 1) // config.PAGE_SIZE)
            self._seg_candidates_added = True  # 标记分词候选已追加
            self._can_enter_seg_mode = True  # 还可以再翻到底进逐段模式
            debug_log("_enter_seg_mode_from_composition: appended {} segmentation candidates".format(
                len(new_cands)))
            self._render_candidates()
        else:
            # 没有新的分词候选，直接进逐段确认模式
            self._enter_seg_mode(segments)

    def _render_seg_display(self):
        """渲染分段确认的组合串显示

        全部内容显示在 compositionString 中（不 commit，避免无法回退）。
        compositionCursor 标记当前段和后续段的分界。
        已确认段 + 当前段 在 cursor 左边，后续段在 cursor 右边。
        """
        # 全部内容：已确认 + 当前 + 后续
        committed_text = "".join(word for _, word in self._seg_committed)
        current_and_rest = []
        for i in range(self._seg_idx, len(self._segments)):
            current_and_rest.append(self._segments[i][2])

        full_text = committed_text + "".join(current_and_rest)
        self.setCompositionString(full_text)

        # cursor 位置：已确认部分 + 当前段长度
        # cursor 左边是"已确认+当前段"，右边是"后续段"
        current_word_len = len(self._segments[self._seg_idx][2]) if self._seg_idx < len(self._segments) else 0
        cursor_pos = len(committed_text) + current_word_len
        self.setCompositionCursor(cursor_pos)

        debug_log("_render_seg_display: full='{}' committed='{}' cursor={}".format(
            full_text, committed_text, cursor_pos))

    def _render_seg_candidates(self):
        """渲染当前段的候选列表"""
        if self._seg_idx >= len(self._segments):
            self.setShowCandidates(False)
            return

        seg = self._segments[self._seg_idx]
        cands = seg[3]  # 候选词列表
        page_start = self._seg_page * config.PAGE_SIZE
        page_cands = cands[page_start:page_start + config.PAGE_SIZE]

        if page_cands:
            self.setCandidateList(page_cands)
            self.setShowCandidates(True)
            self.setSelKeys(config.SEL_KEYS)
        else:
            self.setShowCandidates(False)

        debug_log("_render_seg_candidates: seg[{}]='{}' page={} cands={}".format(
            self._seg_idx, seg[2], self._seg_page, page_cands[:5]))

    def _seg_confirm(self):
        """确认当前段（用默认词），移到下一段"""
        if self._seg_idx >= len(self._segments):
            return
        seg = self._segments[self._seg_idx]
        self._seg_confirm_word(seg[2])  # default_word

    def _seg_confirm_word(self, word):
        """确认当前段（用指定词），移到下一段

        如果选中的词只覆盖了段的部分音节（如从 you yi 段选了单字"有"），
        则剩余音节自动重新分词并插入到后续段之前。
        """
        if self._seg_idx >= len(self._segments):
            return

        seg = self._segments[self._seg_idx]
        pinyin = seg[0]
        seg_syllables = seg[1]  # 该段对应的音节列表
        debug_log("_seg_confirm_word: seg[{}] pinyin='{}' word='{}' syllables={}".format(
            self._seg_idx, pinyin, word, seg_syllables))

        # 判断选中的词是否只覆盖了部分音节
        # 单字 = 1 个字 = 对应 1 个音节
        consumed_syllables = len(word) if len(word) <= len(seg_syllables) else len(seg_syllables)
        remaining_syllables = seg_syllables[consumed_syllables:]

        # 记录用户词频和造词
        consumed_pinyin = " ".join(seg_syllables[:consumed_syllables])
        AIIMEService._user_memory.record(word)
        if len(word) >= 2:
            existing = AIIMEService._dict_loader.lookup(consumed_pinyin)
            word_in_dict = any(w == word for w, f in existing)
            if not word_in_dict:
                freq = AIIMEService._user_memory.add_phrase(consumed_pinyin, word)
                AIIMEService._dict_loader.add_entry(consumed_pinyin, word, freq)
                debug_log("User phrase created: {} -> {} (freq={})".format(
                    consumed_pinyin, word, freq))

        # 添加到已确认列表
        self._seg_committed.append((consumed_pinyin, word))

        # 如果有剩余音节，需要收集后续所有段的音节一起重新分词
        if remaining_syllables:
            # 收集当前段剩余 + 后续所有段的音节
            later_syllables = []
            for j in range(self._seg_idx + 1, len(self._segments)):
                later_syllables.extend(self._segments[j][1])
            all_remaining = remaining_syllables + later_syllables

            from pinyin.candidates import segment_pinyin
            new_segments = segment_pinyin(all_remaining, AIIMEService._dict_loader)
            # 替换当前段及之后的所有段
            self._segments = (
                self._segments[:self._seg_idx + 1] +  # 前面的段不变（含当前段）
                new_segments                          # 重新分词的段
            )
            debug_log("Re-segmented remaining {}: {} new segments".format(
                all_remaining, len(new_segments)))
        else:
            # 没有剩余音节，但当前段之后可能还有后续段，无需重组
            pass

        self._seg_idx += 1
        self._seg_page = 0

        if self._seg_idx >= len(self._segments):
            # 所有段确认完毕，上屏完整结果
            full_text = "".join(word for _, word in self._seg_committed)
            full_pinyin = " ".join(syl for py_syl, _ in self._seg_committed for syl in (py_syl.split() if ' ' in py_syl else [py_syl]))
            debug_log("All segments confirmed: '{}' pinyin='{}'".format(full_text, full_pinyin))

            # 对完整结果造词（2+字的词组都记入用户词库）
            if len(full_text) >= 2:
                AIIMEService._user_memory.record(full_text)
                existing = AIIMEService._dict_loader.lookup(full_pinyin)
                word_in_dict = any(w == full_text for w, f in existing)
                if not word_in_dict:
                    freq = AIIMEService._user_memory.add_phrase(full_pinyin, full_text)
                    AIIMEService._dict_loader.add_entry(full_pinyin, full_text, freq)
                    debug_log("Seg phrase created: {} -> {} (freq={})".format(
                        full_pinyin, full_text, freq))

            self.setCommitString(full_text)
            self.setShowCandidates(False)
            self.composition = ""
            self.setCompositionString("")
            self._reset_seg_state()
        else:
            # 还有段未确认，更新显示
            self._render_seg_display()
            self._render_seg_candidates()

    def _seg_backspace(self):
        """分段模式下退格：回退到上一段"""
        if self._seg_committed:
            # 撤销最后确认的段
            self._seg_committed.pop()
            self._seg_idx -= 1
            self._seg_page = 0
            debug_log("_seg_backspace: back to seg[{}]".format(self._seg_idx))
            self._render_seg_display()
            self._render_seg_candidates()
        else:
            # 还没确认过任何段，退出分段模式回到普通编辑
            self._seg_mode = False
            self._update_composition_display()

    def _seg_split_current(self):
        """翻页到底时自动拆分当前段：首音节单字 + 剩余音节（含后续段）重新贪心分词

        例：youyidian 分词为 [you yi | dian]
        → 翻页到底拆分：you（单字）+ [yi dian | ...后续段不变]
        → yi dian 重新贪心 = 一点
        → 结果：[有 | 一点]

        如果"一点"也翻到底：拆成 yi（单字）+ dian（单字）
        → 保底：一个字一个字确认
        """
        if self._seg_idx >= len(self._segments):
            return

        seg = self._segments[self._seg_idx]
        syllables = seg[1]  # 当前段的音节列表

        if len(syllables) < 2:
            debug_log("_seg_split_current: single syllable, nothing to split")
            return

        # 收集当前段剩余 + 后续所有段的音节，一起重新分词
        from pinyin.candidates import segment_pinyin
        first_segs = segment_pinyin([syllables[0]], AIIMEService._dict_loader)  # 首音节单字
        rest_syls = syllables[1:]
        for j in range(self._seg_idx + 1, len(self._segments)):
            rest_syls.extend(self._segments[j][1])
        rest_segs = segment_pinyin(rest_syls, AIIMEService._dict_loader)  # 剩余贪心分词

        # 替换当前段及之后的所有段
        new_segs = first_segs + rest_segs
        self._segments = (
            self._segments[:self._seg_idx] +  # 前面的段不变
            new_segs                           # 拆分后的段（替换当前段+后续段）
        )
        self._seg_page = 0

        debug_log("_seg_split_current: {} -> first={} rest_syls={} new_total={}".format(
            syllables, [s[2] for s in first_segs], rest_syls, len(self._segments)))

        self._render_seg_display()
        self._render_seg_candidates()

    def _render_candidates(self):
        page_items = self._current_page_items()
        if page_items:
            self.setCandidateList(page_items)
            self.setShowCandidates(True)
            self.setSelKeys(config.SEL_KEYS)
        else:
            self.setShowCandidates(False)

    def _commit_word(self, word):
        """普通模式提交词"""
        debug_log("_commit_word word='{}'".format(word))
        AIIMEService._user_memory.record(word)

        if len(word) >= 2 and self.composition:
            pinyin_syllables = best_split(self.composition)
            pinyin_key = " ".join(pinyin_syllables)
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
        self._reset_seg_state()

    def _clear_composition(self):
        debug_log("_clear_composition")
        self.composition = ""
        self.setCompositionString("")
        self.setShowCandidates(False)
        self._reset_seg_state()

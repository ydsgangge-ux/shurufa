# -*- coding: utf-8 -*-
"""
AI 输入法 v1.0 - AI 语义推断

核心交互（模仿搜狗输入法）：
1. 输入拼音 → 先展示词库候选
2. AI 异步推断 → 候选追加到末尾（歇后语/古诗文/成语接龙等）
3. 词库无候选时 → AI 兜底生成
4. 翻页 = 看更多候选
5. 翻到底 → 进入分词模式（一个词一个词确认）
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
from user_memory import UserMemory, BigramMemory
from ai.predictor import get_predictor
from ai.lexicon_expander import LexiconExpander

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
VK_DECIMAL = 0x6E    # Numpad . (小键盘句号)

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
    _bigram_memory = None
    _lexicon_expander = None

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
        # 引号配对状态
        self._double_quote_open = False  # False=下次输出"（左），True=下次输出"（右）
        self._single_quote_open = False  # False=下次输出'（左），True=下次输出'（右）
        # AI 预测器（"抢空闲"模式：上屏后预测下一个词）
        self._ai_predictor = get_predictor()
        self._ai_suggestions = []  # AI 预缓存的建议词（上屏后计算好的）
        self._ai_appended = False  # AI 结果是否已追加到候选
        # 词序续写（bigram + AI 兜底）
        self._last_committed_word = None  # 上一个上屏的词（用于 bigram 链）
        self._bigram_hint = []            # bigram 续写候选 [(word, count), ...]
        self._predict_ctx_id = 0          # 预测上下文 ID（用于丢弃过期 AI 结果）
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
        if AIIMEService._bigram_memory is None:
            bigram_path = os.path.join(os.path.dirname(config.USER_MEMORY_PATH), "bigram.json")
            AIIMEService._bigram_memory = BigramMemory(bigram_path)
            debug_log("BigramMemory loaded: {} prev_words".format(
                len(AIIMEService._bigram_memory._data)))
        # 初始化词库扩充器
        if AIIMEService._lexicon_expander is None:
            AIIMEService._lexicon_expander = LexiconExpander(
                config.USER_MEMORY_PATH, AIIMEService._dict_loader)
            debug_log("LexiconExpander initialized")
        debug_log("AIIMEService.__init__ called")

    def onActivate(self):
        debug_log("onActivate")
        self.isActivated = True

    def onDeactivate(self):
        debug_log("onDeactivate")
        self._last_committed_word = None  # 上下文不连续，断链
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
            if 0x30 <= code <= 0x39:  # 0-9
                return True
            if code in (config.VK_OEM_MINUS, config.VK_OEM_PLUS):
                return True

        # 字母键 A-Z
        if 0x41 <= code <= 0x5A:
            if keyEvent.isKeyDown(VK_SHIFT):
                return True
            return True

        # 中文标点（用 charCode 匹配）
        if not self.composition and char_code > 0:
            char = chr(char_code)
            if char in config.PUNCTUATION_MAP:
                return True
            # 引号配对
            if char in config.QUOTE_PAIRS:
                return True

        # 引号（keyCode 兜底，VK_OEM_7 = Shift+'）
        if not self.composition and code in config.QUOTE_VK_MAP:
            return True

        # Numpad . → 输出半角 .（不转全角）
        if code == VK_DECIMAL:
            return True

        return False

    def onKeyDown(self, keyEvent):
        code = keyEvent.keyCode
        char_code = keyEvent.charCode

        # 轮询 AI 结果（主线程，线程安全）
        self._poll_ai_and_refresh()

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
                elif self._seg_idx > 0:
                    # 不是第一段 → 回到上一段
                    pass  # 暂不实现回退段
                else:
                    # 分词模式第一页按 - → 退回整句候选模式
                    debug_log("Seg mode - : return to whole sentence mode")
                    self._seg_mode = False
                    self._seg_idx = 0
                    self._seg_committed = []
                    self._seg_page = 0
                    self._page = 0  # 回到整句第一页
                    self.setCompositionString(self.composition)
                    self.setCompositionCursor(len(self.composition))
                    self._render_candidates()
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
                self._last_committed_word = None  # 原始拼音上屏，断链
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
                # 有 AI 预测时，1=AI预测，2-9=词库第1-8位，0=词库第9位
                ai_word = self._get_ai_prediction()
                if ai_word:
                    if idx == 0:
                        # 按1 → 选择 AI 预测词
                        self._commit_word(ai_word)
                        debug_log("1 key: AI predict commit '{}'".format(ai_word))
                        return True
                    else:
                        # 按2-9 → 选择词库第1-8位
                        page_items = self._current_page_items()
                        word_idx = idx - 1  # 偏移1位（因为1被AI占了）
                        if word_idx < len(page_items):
                            self._commit_word(page_items[word_idx])
                            return True
                        return False
                else:
                    # 无 AI 预测，1-9 直接选词库第1-9位
                    page_items = self._current_page_items()
                    if idx < len(page_items):
                        self._commit_word(page_items[idx])
                        return True
                    return False

        # 数字键 0：有AI预测时选词库第9位，无AI预测时忽略
        if code == 0x30:
            if self.composition and not self._seg_mode:
                ai_word = self._get_ai_prediction()
                if ai_word:
                    # 有AI预测时，0=词库第9位
                    page_items = self._current_page_items()
                    if len(page_items) >= 9:
                        self._commit_word(page_items[8])
                        debug_log("0 key: dict word[8]='{}'".format(page_items[8]))
                # 无AI预测时0键无效（SEL_KEYS_NO_AI 不包含0）
            return True

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
                # 句子结束标点：断链
                if full in ("\u3002", "\uff1f", "\uff01"):  # 。？！
                    self._last_committed_word = None
                return True
            # 引号配对
            if char in config.QUOTE_PAIRS:
                return self._handle_quote(char)

        # 引号（keyCode 兜底）
        if not self.composition and code in config.QUOTE_VK_MAP:
            quote_char = config.QUOTE_VK_MAP[code]
            return self._handle_quote(quote_char)

        # Numpad . → 半角 .（不转全角，方便输入数字小数点）
        if code == VK_DECIMAL:
            self.setCommitString(".")
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
        """组合串变化时：先显示词库候选 + 预缓存的 AI 建议

        【"抢空闲"设计】AI 不追打字节奏，而是：
        1. 上屏后 → AI 利用词间停顿提前算好"下一个词"
        2. 用户开始打字时 → 直接消费预缓存结果
        3. 如果 AI 还没算完 → 每次按键轮询一次，算完就追加
        """
        self.setCompositionString(self.composition)
        self.setCompositionCursor(len(self.composition))

        # 重置分词模式状态
        self._seg_mode = False
        self._ai_appended = False

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

        # 特殊符号匹配（输入拼音匹配特殊符号，如 sheshidu → ℃）
        if self.composition in config.SYMBOL_MAP:
            for sym, desc in config.SYMBOL_MAP[self.composition]:
                if sym not in seen:
                    self._all_candidates.append(sym)
                    seen.add(sym)

        # 也匹配完整拼音中最后一个音节
        syllables = best_split(self.composition)
        if syllables and syllables[-1] in config.SYMBOL_MAP:
            for sym, desc in config.SYMBOL_MAP[syllables[-1]]:
                if sym not in seen:
                    self._all_candidates.append(sym)
                    seen.add(sym)

        # 如果有2+音节，记住可以进分词模式（翻到底时触发）
        self._can_enter_seg_mode = len(self._all_candidates) > 0 and len(self.composition) >= 2

        # 【关键】消费预缓存的 AI 建议（上屏后提前算好的）
        if self._ai_suggestions and not self._ai_appended:
            added = []
            for w in self._ai_suggestions:
                if w not in seen and w != self.composition:
                    self._all_candidates.append(w)
                    seen.add(w)
                    added.append(w)
            if added:
                self._ai_appended = True
                debug_log("AI pre-cached used: '{}'".format("','".join(added)))

        # 轮询：如果 AI 还在算，检查一下是否完成了
        self._poll_ai_and_refresh()

        debug_log("_update_composition_display comp='{}' cands={} seg_ready={} ai_cached={}".format(
            self.composition, len(self._all_candidates), self._can_enter_seg_mode,
            len(self._ai_suggestions)))

        # 显示候选
        self._render_candidates()

    def _request_ai_predict(self):
        """发起异步 AI 请求

        决策逻辑（优先级从高到低）：
        1. 词库候选 ≤ 1 个 → 整句预测 + 兜底生成
        2. 拼音 ≥ 6 字母（长句）→ 整句预测（最有价值场景）
        3. 有上下文 → 上下文续写
        """
        if len(self.composition) < 4:
            return

        has_cloud = self._ai_predictor.cloud.is_available()

        if len(self._all_candidates) <= 1:
            # 词库无结果或极少
            if has_cloud:
                debug_log("AI sentence+fallback: comp='{}' cands={}".format(
                    self.composition, len(self._all_candidates)))
                self._ai_predictor.request_sentence_predict(
                    self.composition, n=3)
            else:
                debug_log("AI fallback (local): comp='{}' cands={}".format(
                    self.composition, len(self._all_candidates)))
                self._ai_predictor.request_fallback_predict(
                    self.composition, n=3)

        elif has_cloud and len(self.composition) >= 6:
            # 长句输入 → 云端整句预测（最有价值场景）
            debug_log("AI sentence predict: comp='{}' cands={}".format(
                self.composition, len(self._all_candidates)))
            self._ai_predictor.request_sentence_predict(
                self.composition, n=3)

        else:
            # 有上下文 → 续写
            context = self._ai_predictor.get_context()
            if context:
                debug_log("AI context predict: comp='{}' ctx='{}'".format(
                    self.composition, context[-20:]))
                self._ai_predictor.request_context_predict(
                    self.composition, n=3)

    def _poll_ai_and_refresh(self):
        """轮询 AI 结果

        两种消费方式：
        1. 如果正在打字（有 composition）→ 追加到候选末尾并刷新
        2. 如果没在打字（上屏后空闲期）→ 缓存到 _ai_suggestions，下次打字时用
        """
        ai_words = self._ai_predictor.poll_ai_results()
        if not ai_words:
            return

        if self.composition:
            # 正在打字 → 直接追加到候选
            if self._ai_appended:
                return
            seen = set(self._all_candidates)
            added = []
            for w in ai_words:
                if w not in seen and w != self.composition:
                    self._all_candidates.append(w)
                    seen.add(w)
                    added.append(w)
            if added:
                self._ai_appended = True
                debug_log("AI appended: '{}'".format("','".join(added)))
                self._render_candidates()
        else:
            # 空闲期 → 缓存结果，下次打字时用
            self._ai_suggestions = ai_words
            debug_log("AI pre-cached: '{}'".format("','".join(ai_words)))

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

            # bigram：记录转移 + 查询续写
            if self._last_committed_word and AIIMEService._bigram_memory:
                AIIMEService._bigram_memory.record(self._last_committed_word, full_text)
            self._last_committed_word = full_text
            self._bigram_hint = []
            if AIIMEService._bigram_memory:
                self._bigram_hint = AIIMEService._bigram_memory.lookup(full_text, top_n=5)

            # 更新 AI 上下文 + 上屏后触发预测
            old_ctx = self._ai_predictor.get_context()
            new_ctx = old_ctx + full_text
            self._ai_predictor.set_context(new_ctx)
            self._ai_suggestions = []
            self._ai_predictor.cancel_request()

            if self._bigram_hint:
                self._ai_suggestions = [w for w, c in self._bigram_hint]
            elif len(new_ctx) >= 2:
                debug_log("AI predict-next (fallback): after seg commit '{}', ctx='{}'".format(
                    full_text, new_ctx[-20:]))
                self._ai_predictor.request_context_predict("", n=3)

            self.setShowCandidates(False)
            self.composition = ""
            self.setCompositionString("")
            self._reset_seg_state()

            # 词库自动扩充：累积上屏文字
            if AIIMEService._lexicon_expander and len(full_text) >= 2:
                AIIMEService._lexicon_expander.accumulate(full_text)
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
        """渲染候选列表，AI预测词插到第1位

        候选窗布局（有AI预测时）：
        1.✦AI预测  2.词库词  3.词库词 ... 9.词库词  0.词库词

        无AI预测时：
        1.词库词  2.词库词 ... 9.词库词
        """
        page_items = self._current_page_items()
        if not page_items:
            self.setShowCandidates(False)
            return

        # AI 预测词插到第1位
        ai_word = self._get_ai_prediction()
        if ai_word:
            # 前缀 ✦ 标识 AI 预测，与词库候选区分
            ai_display = "\u2726{}".format(ai_word)
            # 候选列表：AI预测在最前面 + 词库候选
            display_items = [ai_display] + list(page_items)
            self.setCandidateList(display_items)
            self.setSelKeys(config.SEL_KEYS)
            debug_log("candidates: AI[1]='{}' + {} items".format(ai_word, len(page_items)))
        else:
            self.setCandidateList(page_items)
            self.setSelKeys(config.SEL_KEYS_NO_AI)

        self.setShowCandidates(True)

    def _get_ai_prediction(self):
        """获取预测的下一个词（0位显示用）

        优先级：
        1. 已缓存的结果（bigram 或 AI）
        2. 轮询 AI 是否有新结果（带上下文校验）
        """
        # 1. 已缓存
        if self._ai_suggestions:
            return self._ai_suggestions[0]

        # 2. 轮询 AI 结果（仅在没有 composition 时接受，避免过期结果）
        if self.composition:
            return None
        ai_words = self._ai_predictor.poll_ai_results()
        if ai_words:
            self._ai_suggestions = ai_words
            return ai_words[0]

        return None

    def _commit_word(self, word):
        """普通模式提交词"""
        debug_log("_commit_word word='{}'".format(word))
        AIIMEService._user_memory.record(word)

        # 记录 bigram 转移：上一个词 → 这个词
        if self._last_committed_word and AIIMEService._bigram_memory:
            AIIMEService._bigram_memory.record(self._last_committed_word, word)
            debug_log("bigram record: '{}' -> '{}'".format(self._last_committed_word, word))

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

        # 更新 last_committed_word（维护 bigram 链）
        self._last_committed_word = word

        # 查询 bigram 续写候选（零延迟，纯查表）
        self._bigram_hint = []
        if AIIMEService._bigram_memory:
            self._bigram_hint = AIIMEService._bigram_memory.lookup(word, top_n=5)
            if self._bigram_hint:
                debug_log("bigram hint after '{}': {}".format(
                    word, [(w, c) for w, c in self._bigram_hint]))

        # 更新 AI 上下文（累积历史，保留最近 100 字）
        old_ctx = self._ai_predictor.get_context()
        new_ctx = old_ctx + word
        self._ai_predictor.set_context(new_ctx)

        # 上屏后触发预测：bigram 有结果就用 bigram，否则 AI 兜底
        self._ai_suggestions = []  # 清空旧建议
        self._ai_predictor.cancel_request()  # 取消旧请求
        self._predict_ctx_id += 1  # 递增上下文 ID，过期 AI 结果自动失效

        if not self._bigram_hint and len(new_ctx) >= 2:
            # bigram 没命中，走 AI 兜底
            debug_log("AI predict-next (fallback): after commit '{}', ctx='{}'".format(
                word, new_ctx[-20:]))
            self._ai_predictor.request_context_predict("", n=3)
        elif self._bigram_hint:
            # bigram 命中，把结果当作 ai_suggestions 直接用（零延迟）
            self._ai_suggestions = [w for w, c in self._bigram_hint]
            debug_log("bigram serves as prediction: {}".format(self._ai_suggestions))

        self.setShowCandidates(False)
        self.composition = ""
        self.setCompositionString("")
        self._reset_seg_state()

        # 词库自动扩充：累积上屏文字
        if AIIMEService._lexicon_expander and len(word) >= 2:
            AIIMEService._lexicon_expander.accumulate(word)

    def _handle_quote(self, char):
        """处理引号配对逻辑

        奇数次按 → 左引号（开），偶数次按 → 右引号（关）
        " → " → " → " → ...
        ' → ' → ' → ' → ...
        """
        left, right = config.QUOTE_PAIRS[char]
        if char == "\"":
            if not self._double_quote_open:
                self.setCommitString(left)
                self._double_quote_open = True
                debug_log("quote: left double \"")
            else:
                self.setCommitString(right)
                self._double_quote_open = False
                debug_log("quote: right double \"")
        elif char == "'":
            if not self._single_quote_open:
                self.setCommitString(left)
                self._single_quote_open = True
                debug_log("quote: left single '")
            else:
                self.setCommitString(right)
                self._single_quote_open = False
                debug_log("quote: right single '")
        return True

    def _clear_composition(self):
        debug_log("_clear_composition")
        self.composition = ""
        self.setCompositionString("")
        self.setShowCandidates(False)
        self._reset_seg_state()

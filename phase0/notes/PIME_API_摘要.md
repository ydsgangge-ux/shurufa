# PIME Python API 摘要

> 基于 PIME 源码研究，版本 1.3.0。此文档是 AI 输入法开发的基础参考。

## 1. PIME 架构概览

```
用户按键 → Windows TSF → PIMETextService.dll (C++客户端)
    → Windows named pipe → PIMELauncher.exe (中间件)
    → stdin/stdout → Python 后端服务 (业务逻辑)
```

- **C++ DLL (PIMETextService.dll)**: 加载到每个使用 PIME 的应用进程，只负责转发按键
- **PIMELauncher.exe**: 启动/监控 Python 后端，崩溃自动重启
- **Python 后端**: 实现输入法逻辑，通过 stdin/stdout 通信（JSON 格式）

## 2. 输入法注册机制

### 目录结构
```
C:\Program Files (x86)\PIME\python\input_methods\<输入法名>\
├── ime.json          # 元数据（必需）
├── <moduleName>.py   # 输入法实现（必需）
└── icon.ico          # 图标（可选）
```

### ime.json 格式
```json
{
    "name": "AI输入法",
    "version": "0.1.0",
    "guid": "{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}",
    "locale": "zh-CN",
    "fallbackLocale": "zh-CN",
    "icon": "icon.ico",
    "moduleName": "ai_ime_ime",
    "serviceName": "AIIMEService",
    "configTool": "",
    "configToolParams": "",
    "configToolDir": ""
}
```

- `guid`: 唯一标识符（TSF 注册用），必须全局唯一
- `moduleName`: Python 模块名（不含 .py），实际 import 路径为 `input_methods.<目录名>.<moduleName>`
- `serviceName`: 输入法类名（在 moduleName 模块中定义）

### 自动发现
`TextServiceManager` 在启动时扫描 `input_methods/` 下所有子目录，找到 `ime.json` 就自动注册。**无需手动注册 DLL 或写注册表**——PIME 安装时已注册 TSF 组件。

## 3. TextService 基类 API

源码位置: `python/textService.py`

### 核心回调方法（子类需实现）

| 方法 | 说明 | 返回值 |
|---|---|---|
| `filterKeyDown(keyEvent)` | 按键过滤，判断是否由输入法处理此键 | `True`=处理, `False`=透传 |
| `onKeyDown(keyEvent)` | 按键处理（仅在 filterKeyDown 返回 True 时调用） | `True`=已消费, `False`=透传 |
| `filterKeyUp(keyEvent)` | 按键释放过滤 | 同上 |
| `onKeyUp(keyEvent)` | 按键释放处理 | 同上 |
| `onActivate()` | 输入法被激活 | - |
| `onDeactivate()` | 输入法被停用 | - |
| `onCompositionTerminated(forced)` | 组合被终止（ESC 或外部取消） | - |
| `onKeyboardStatusChanged(opened)` | 键盘状态变化 | - |

### 输出方法（控制输入法行为）

| 方法 | 说明 |
|---|---|
| `setCompositionString(s)` | 设置预输入文本（组合串，显示在光标处带下划线） |
| `setCompositionCursor(pos)` | 设置组合串光标位置 |
| `setCommitString(s)` | 设置提交文本（上屏） |
| `setCandidateList(cand)` | 设置候选词列表（如 `["你好", "您好"]`） |
| `setCandidateCursor(pos)` | 设置候选光标位置 |
| `setShowCandidates(show)` | 显示/隐藏候选窗口 |
| `setSelKeys(keys)` | 设置选词键（如 `"123456789"`） |
| `setKeyboardOpen(opened)` | 打开/关闭软键盘 |
| `isComposing()` | 是否正在组合（组合串非空或候选窗打开） |
| `showMessage(msg, duration=3)` | 显示临时提示消息 |
| `customizeUI(**kwargs)` | 自定义候选窗外观（字体、每行候选数等） |

### 语言栏方法
- `addButton(id, **kwargs)`: 添加语言栏按钮
- `removeButton(id)`: 移除按钮
- `changeButton(id, **kwargs)`: 修改按钮

## 4. KeyEvent 对象

```python
class KeyEvent:
    charCode       # 字符码（Unicode，受 Shift 影响）
    keyCode        # 虚拟键码（VK_*，不受 Shift 影响）
    repeatCount    # 重复次数
    scanCode       # 扫描码
    isExtended     # 是否扩展键
    keyStates      # 键盘状态数组（256字节）
    
    def isKeyDown(code)      # 检查某键是否按下
    def isKeyToggled(code)   # 检查某键是否切换状态（如 CapsLock）
    def isChar()             # 是否字符键
    def isPrintableChar()    # 是否可打印字符
```

## 5. 常用虚拟键码 (keycodes.py)

```python
VK_RETURN  = 0x0D   # 回车
VK_BACK    = 0x08   # 退格
VK_ESCAPE  = 0x1B   # ESC
VK_SPACE   = 0x20   # 空格
VK_SHIFT   = 0x10
VK_CONTROL = 0x11
# VK_0-VK_9 = 0x30-0x39 (与 ASCII '0'-'9' 相同)
# VK_A-VK_Z = 0x41-0x5A (与 ASCII 'A'-'Z' 相同)
```

## 6. 最小输入法模板

```python
from textService import TextService

class MyIME(TextService):
    def __init__(self, client):
        super().__init__(client)
        self.composition = ""

    def filterKeyDown(self, keyEvent):
        # 只处理字母键
        return 0x41 <= keyEvent.keyCode <= 0x5A

    def onKeyDown(self, keyEvent):
        code = keyEvent.keyCode
        if 0x41 <= code <= 0x5A:  # A-Z
            char = chr(keyEvent.charCode).lower() if keyEvent.charCode else chr(code).lower()
            self.composition += char
            self.setCompositionString(self.composition)
            self.setCompositionCursor(len(self.composition))
            return True
        return False
```

## 7. 调试方法

- **控制台调试**: 运行 `PIMELauncher.exe /console` 打开调试控制台
- **日志位置**: `%LocalAppData%\PIME\Log\PIMELauncher.log`
- **Python print**: 在输入法代码里的 `print()` 输出到 PIMELauncher 的 stdout
- **崩溃恢复**: Python 后端崩溃会被 PIMELauncher 自动重启

## 8. 关键注意事项

1. **Python 版本**: PIME 1.3.0 内置 Python 3.8.10（32位），不使用系统 Python
2. **异步要求**: `onKeyDown` 必须快速返回，AI 推理等耗时操作需放独立线程
3. **状态管理**: `self.composition` 等状态在 `onCompositionTerminated` 时需清空
4. **导入路径**: `from textService import TextService` 和 `from keycodes import *` 可用（python/ 在 sys.path）
5. **IPC 协议**: 通信格式为 `<client_id>|<JSON>\n`，但开发者不需要关心——TextService 基类已封装

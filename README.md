# AI 输入法

基于 PIME 框架的智能拼音输入法，集成 AI 语义预测。

## 功能特点

- **智能拼音**：全拼/简拼/混合拼，36.8 万词库
- **AI 预测**：上屏后预测下一个词，按 1 直接选 AI 预测
- **三引擎 AI**：本地 LLM → 云端 API → Ollama，自动降级
- **符号输入**：拼音输入特殊符号（如 `sheshidu`→℃、`alpha`→α、`pingfang`→²）
- **标点全角化**：中文模式自动转换标点
- **引号配对**：左/右引号智能交替
- **造词记忆**：用户高频词自动提升优先级
- **词库扩充**：累积 1000 字后 AI 自动扩充词库

## 快速安装

### 前提条件

- Windows 10/11
- **PIME 框架**（安装脚本会自动下载，也可[手动安装](https://github.com/EasyIME/PIME/releases)）

### 安装步骤

1. 下载或 clone 本项目
2. 右键 PowerShell → **以管理员身份运行**
3. 执行安装脚本：

```powershell
cd <项目目录>
.\install.ps1
```

4. 安装完成后，在任意应用中按 `Win+空格` 切换到「AI输入法」

### 可选：云端 AI（推荐）

基础输入法无需任何 AI 即可使用。配置云端 API 可获得 AI 预测功能：

```powershell
# 创建配置目录
mkdir "$env:USERPROFILE\.ai_ime"

# 创建配置文件（替换为你的 API key）
@'
{
    "api_key": "sk-你的key",
    "api_base": "https://api.deepseek.com/v1",
    "model": "deepseek-v4-flash",
    "timeout": 5.0
}
'@ | Out-File -Encoding utf8 "$env:USERPROFILE\.ai_ime\api_config.json"
```

支持任何 OpenAI 兼容 API（DeepSeek、OpenAI、硅基流动等）。

### 可选：本地 AI

无需网络，但需要下载模型（约 400MB）：

```powershell
.\download_model.ps1
```

需要系统 Python 3.10+ 和 llama-cpp-python（安装脚本会自动安装）。

**模型要求：**

| 要求 | 说明 |
|------|------|
| 格式 | `.gguf` |
| 微调类型 | 必须是 **Instruct/Chat** 版（base 模型无法按 chat 格式回复） |
| 参数量 | 建议 **≤1B**（0.5B/0.6B 最佳，7B+ 推理太慢） |
| 语言 | 必须支持**中文** |
| 量化 | Q4_K_M 或 Q5_K_M（Q2 太差，Q8 没必要） |

**推荐模型：**
- `qwen2.5-0.5b-instruct-q4_k_m.gguf`（默认，400MB）
- `qwen3-0.6b-instruct-q4_k_m.gguf`
- `tinyllama-1.1b-chat-q4_k_m.gguf`

放到 `models/` 目录即可，多个模型时自动选择最佳。

## 使用方法

| 操作 | 说明 |
|------|------|
| 输入拼音 | 显示候选词 |
| 1-9 | 选择候选词 |
| 1（有✦标记时） | 选择 AI 预测词 |
| 空格 | 选择第一个候选 |
| = | 下一页 |
| - | 上一页 |
| 回车 | 上屏原始拼音 |
| ESC | 取消输入 |
| Shift | 切换中/英文 |
| Caps Lock | 临时英文模式 |

### 符号输入

输入拼音即可匹配特殊符号：

| 拼音 | 符号 | 拼音 | 符号 |
|------|------|------|------|
| sheshidu | ℃ | alpha/α尔法 | α |
| pingfang | ² | beta/贝塔 | β |
| cheng | × | dayu | ≥ |
| chu | ÷ | xiaoyu | ≤ |
| pai | π | wuxian | ∞ |
| jiantou | →←↑↓ | dui/cuo | ✓✗ |

支持 120+ 种符号：希腊字母、数学运算、上下标、罗马数字、货币等。

## 项目结构

```
ai_ime/
├── ai_ime_ime.py          # 输入法核心逻辑
├── config.py              # 配置（标点/符号/常量）
├── user_memory.py         # 用户词频记忆
├── ime.json               # PIME 输入法注册信息
├── ai/
│   ├── predictor.py       # AI 预测器（三引擎）
│   ├── cloud_client.py    # 云端 API 客户端
│   ├── local_llm_client.py# 本地 LLM 客户端
│   ├── ollama_client.py   # Ollama 客户端
│   └── lexicon_expander.py# 词库自动扩充
├── pinyin/
│   ├── candidates.py      # 候选词生成
│   ├── dict_loader.py     # 词库加载
│   ├── parser.py          # 拼音切分
│   └── syllables.py       # 音节表
└── data/
    └── base_dict.txt      # 基础词库（36.8万条）

local_llm_server.py        # 本地 LLM HTTP 服务
install.ps1                # 一键安装
deploy_v10.ps1             # 开发部署
download_model.ps1         # 下载 AI 模型
```

## 开发

修改代码后，在管理员 PowerShell 运行：

```powershell
.\deploy_v10.ps1
```

日志位置：`%LOCALAPPDATA%\PIME\Log\ai_ime_debug.log`

## 技术栈

- **PIME** v1.3.0 — Windows TSF 输入法框架
- **Python** — PIME 内置 3.8 32位 / 系统 Python 3.10+
- **llama-cpp-python** — 本地 LLM 推理
- **jieba** — 中文分词（词库来源）
- **DeepSeek V4 Flash** — 云端 AI（可选）

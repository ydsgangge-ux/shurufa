; AI IME - Inno Setup Installer Script (Standalone)
; 免安装集成版本：内嵌 PIME 核心运行时，无需用户单独安装 PIME
;
; 构建步骤：
;   1. 运行 .\extract_pime_runtime.ps1  （从已装 PIME 提取运行时到 pime_runtime/）
;   2. 运行 .\build_installer.ps1        （编译安装包）

#define MyAppName "AI IME"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "AI-IME"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/ai-ime/ai-ime
DefaultDirName={commonpf}\AI_IME
DefaultGroupName=AI IME
OutputBaseFilename=AI_IME_Setup_v1.2.0
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
PrivilegesRequired=admin
ArchitecturesAllowed=x86compatible
UninstallDisplayName=AI IME
WizardStyle=modern
; 安装/卸载后可能需要刷新输入法列表
; ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
InstallComplete=AI IME has been installed successfully.%n%nYou can now switch to "AI" in the Windows language bar (Win+Space).
CloudApiHint=Cloud AI Configuration%n%nTo enable AI prediction, configure a cloud API:%n1. Create directory: C:\Users\YourName\.ai_ime\%n2. Create file: api_config.json%n3. Add your DeepSeek/OpenAI API key%n%nSee README.md for details

[Tasks]
Name: "installmodel"; Description: "Install AI model (qwen2.5-0.5b, ~400MB)"; GroupDescription: "Optional:"; Flags: checkedonce

; ================================================================
; 文件：PIME 核心运行时（从 pime_runtime/ 目录打包）
; ================================================================
[Files]

; --- PIME Launcher ---
Source: "pime_runtime\PIMELauncher.exe"; DestDir: "{app}"; Flags: ignoreversion

; --- PIME TSF DLL (x86 + x64) ---
Source: "pime_runtime\x86\PIMETextService.dll"; DestDir: "{app}\x86"; Flags: ignoreversion
Source: "pime_runtime\x64\PIMETextService.dll"; DestDir: "{app}\x64"; Flags: ignoreversion

; --- PIME 配置 ---
Source: "pime_runtime\backends.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "pime_runtime\version.txt"; DestDir: "{app}"; Flags: ignoreversion

; --- PIME Python 服务端核心 ---
Source: "pime_runtime\python\server.py"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "pime_runtime\python\serviceManager.py"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "pime_runtime\python\textService.py"; DestDir: "{app}\python"; Flags: ignoreversion
Source: "pime_runtime\python\keycodes.py"; DestDir: "{app}\python"; Flags: ignoreversion

; --- PIME input_methods 目录 ---
Source: "pime_runtime\python\input_methods\__init__.py"; DestDir: "{app}\python\input_methods"; Flags: ignoreversion

; --- Python 3.8 运行时 (python/python3/) ---
Source: "pime_runtime\python\python3\python.exe"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\pythonw.exe"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\python3.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\python38.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\python38.zip"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\vcruntime140.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\PIME.pth"; DestDir: "{app}\python\python3"; Flags: ignoreversion
Source: "pime_runtime\python\python3\LICENSE.txt"; DestDir: "{app}\python\python3"; Flags: ignoreversion skipifsourcedoesntexist

; Python DLL 依赖
Source: "pime_runtime\python\python3\libcrypto-1_1.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion skipifsourcedoesntexist
Source: "pime_runtime\python\python3\libffi-7.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion skipifsourcedoesntexist
Source: "pime_runtime\python\python3\libssl-1_1.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion skipifsourcedoesntexist
Source: "pime_runtime\python\python3\sqlite3.dll"; DestDir: "{app}\python\python3"; Flags: ignoreversion skipifsourcedoesntexist

; Python .pyd 扩展模块
Source: "pime_runtime\python\python3\*.pyd"; DestDir: "{app}\python\python3"; Flags: ignoreversion

; Python tornado 库（PIME server 依赖）
Source: "pime_runtime\python\python3\tornado\*"; DestDir: "{app}\python\python3\tornado"; Flags: ignoreversion recursesubdirs

; Python 额外标准库包目录
Source: "pime_runtime\python\python3\pip\*"; DestDir: "{app}\python\python3\pip"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\setuptools\*"; DestDir: "{app}\python\python3\setuptools"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\distutils\*"; DestDir: "{app}\python\python3\distutils"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\wheel\*"; DestDir: "{app}\python\python3\wheel"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\importlib\*"; DestDir: "{app}\python\python3\importlib"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\encodings\*"; DestDir: "{app}\python\python3\encodings"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\collections\*"; DestDir: "{app}\python\python3\collections"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\asyncio\*"; DestDir: "{app}\python\python3\asyncio"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\concurrent\*"; DestDir: "{app}\python\python3\concurrent"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\urllib\*"; DestDir: "{app}\python\python3\urllib"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\http\*"; DestDir: "{app}\python\python3\http"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\email\*"; DestDir: "{app}\python\python3\email"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\html\*"; DestDir: "{app}\python\python3\html"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\xml\*"; DestDir: "{app}\python\python3\xml"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\logging\*"; DestDir: "{app}\python\python3\logging"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\unittest\*"; DestDir: "{app}\python\python3\unittest"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\lib2to3\*"; DestDir: "{app}\python\python3\lib2to3"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\json\*"; DestDir: "{app}\python\python3\json"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "pime_runtime\python\python3\zoneinfo\*"; DestDir: "{app}\python\python3\zoneinfo"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

; ================================================================
; 文件：AI 输入法（只放这一个输入法，不包含 PIME 自带的）
; ================================================================

; --- AI IME 输入法核心 ---
Source: "ai_ime\ai_ime_ime.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\config.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\user_memory.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\ime.json"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion

; --- AI 模块 ---
Source: "ai_ime\ai\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\cloud_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\local_llm_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\ollama_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\predictor.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\lexicon_expander.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion

; --- Pinyin 模块 ---
Source: "ai_ime\pinyin\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\candidates.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\dict_loader.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\parser.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\syllables.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion

; --- 数据 ---
Source: "ai_ime\data\base_dict.txt"; DestDir: "{app}\python\input_methods\ai_ime\data"; Flags: ignoreversion
Source: "ai_ime\data\api_config.example.json"; DestDir: "{app}\python\input_methods\ai_ime\data"; Flags: ignoreversion skipifsourcedoesntexist

; --- models 目录（存放 .gguf 模型文件） ---
Source: "ai_ime\models\*"; DestDir: "{app}\python\input_methods\ai_ime\models"; Flags: ignoreversion skipifsourcedoesntexist recursesubdirs

; --- 一键下载模型脚本 ---
Source: "download_model.ps1"; DestDir: "{app}"; Flags: ignoreversion

; --- 搜狗词库导入工具 ---
Source: "import_sogou_dict.py"; DestDir: "{app}"; Flags: ignoreversion

; --- AI 扩词库工具 ---
Source: "expand_lexicon.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "expand_lexicon_launcher.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "expand_lexicon_launcher.py"; DestDir: "{app}"; Flags: ignoreversion

; --- 重启输入法脚本 ---
Source: "restart_ime.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "restart_ime.ps1"; DestDir: "{app}"; Flags: ignoreversion

; --- 使用说明 ---
Source: "使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion

; --- Local LLM server ---
Source: "local_llm_server.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion

; ================================================================
; 注册表：TSF Language Profile（让输入法出现在系统语言栏）
; ================================================================
; Inno Setup 中 { 是特殊字符，GUID 的花括号必须转义为 {{ 和 }}
; PIME CLSID: {35F67E9D-A54D-4177-9697-8B0AB71A9E04}
; AI IME GUID: {1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}
; 简体中文 LCID: 0x00000804

[Registry]
; --- 注册 TIP (Text Input Processor) ---
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804"; Flags: uninsdeletekeyifempty

; Language Profile 条目（64-bit）
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: string; ValueName: "Description"; ValueData: "AI输入法"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: string; ValueName: "IconFile"; ValueData: "{app}\python\input_methods\ai_ime\ai_ime.ico"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: dword; ValueName: "IconIndex"; ValueData: "0"; Flags: uninsdeletevalue

; --- 同时注册到 WOW6432Node（32 位兼容） ---
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: string; ValueName: "Description"; ValueData: "AI输入法"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: string; ValueName: "IconFile"; ValueData: "{app}\python\input_methods\ai_ime\ai_ime.ico"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "SOFTWARE\WOW6432Node\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: dword; ValueName: "IconIndex"; ValueData: "0"; Flags: uninsdeletevalue

; --- Enable 注册（使输入法处于启用状态） ---
Root: HKCU; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\Microsoft\CTF\TIP\{{35F67E9D-A54D-4177-9697-8B0AB71A9E04}\LanguageProfile\0x00000804\{{1FC8E29E-09F2-4E3E-A414-8FF3D4EFE3DD}"; ValueType: dword; ValueName: "Enable"; ValueData: "1"; Flags: uninsdeletevalue

; --- 开机自启动 PIMELauncher（确保重启电脑后输入法可用） ---
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AI_IME_Launcher"; ValueData: """{app}\PIMELauncher.exe"""; Flags: uninsdeletevalue

; ================================================================
; 注册 TSF + 启动服务
; ================================================================
[Run]
; 静默注册 TSF DLL（x86：必须，系统是 32 位兼容）
Filename: "regsvr32.exe"; Parameters: "/s ""{app}\x86\PIMETextService.dll"""; Flags: runhidden; StatusMsg: "Registering input method (x86)..."
; 静默注册 TSF DLL（x64：64 位系统额外注册）
Filename: "regsvr32.exe"; Parameters: "/s ""{app}\x64\PIMETextService.dll"""; Flags: runhidden runascurrentuser; StatusMsg: "Registering input method (x64)..."
; 启动 PIMELauncher（后台运行，管理 Python 输入法服务）
Filename: "{app}\PIMELauncher.exe"; Flags: runhidden nowait; StatusMsg: "Starting input service..."
; 安装后刷新 TSF 缓存（让语言栏立即识别新输入法）
Filename: "powershell.exe"; Parameters: "-NoProfile -Command ""Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('')"""; Flags: runhidden nowait; StatusMsg: "Refreshing input methods..."
; 安装 Python 依赖（可选，llama-cpp-python 用于本地模型）
Filename: "cmd.exe"; Parameters: "/c ""{app}\python\python3\python.exe"" -m pip install llama-cpp-python --quiet 2>nul"; Flags: runhidden nowait; StatusMsg: "Installing Python dependencies..."

[UninstallRun]
; 停止 PIMELauncher
Filename: "cmd.exe"; Parameters: "/c taskkill /f /im PIMELauncher.exe 2>nul"; Flags: runhidden; RunOnceId: "StopPIMELauncher"
; 反注册 TSF DLL（x86）
Filename: "regsvr32.exe"; Parameters: "/s /u ""{app}\x86\PIMETextService.dll"""; Flags: runhidden; RunOnceId: "UnregPIME_x86"
; 反注册 TSF DLL（x64）
Filename: "regsvr32.exe"; Parameters: "/s /u ""{app}\x64\PIMETextService.dll"""; Flags: runhidden runascurrentuser; RunOnceId: "UnregPIME_x64"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  HomeDir: string;
  ConfigDir: string;
  ConfigFile: string;
begin
  if CurStep = ssPostInstall then
  begin
    // 自动创建 ~/.ai_ime/api_config.json（如果不存在）
    HomeDir := ExpandConstant('{%USERPROFILE}');
    ConfigDir := HomeDir + '\.ai_ime';
    ConfigFile := ConfigDir + '\api_config.json';
    if not DirExists(ConfigDir) then
      CreateDir(ConfigDir);
    if not FileExists(ConfigFile) then
    begin
      SaveStringToFile(ConfigFile,
        '{' + #13#10 +
        '    "api_key": "",' + #13#10 +
        '    "api_base": "https://api.deepseek.com/v1",' + #13#10 +
        '    "model": "deepseek-v4-flash",' + #13#10 +
        '    "timeout": 5.0' + #13#10 +
        '}', False);
    end;
    MsgBox(CustomMessage('InstallComplete'), mbInformation, MB_OK);
  end;
end;

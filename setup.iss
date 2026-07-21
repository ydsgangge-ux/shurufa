; AI 输入法 - Inno Setup 安装脚本
; 构建方式：运行 build_installer.ps1 或在 Inno Setup IDE 中编译
;
; 生成的 EXE 安装包包含：
; - PIME 框架（如未安装则自动下载安装）
; - 输入法全部文件
; - AI 模型（可选，压缩打包）
; - Python 依赖安装

[Setup]
AppName=AI输入法
AppVersion=1.0.0
AppPublisher=AI-IME
AppPublisherURL=https://github.com/你的用户名/ai-ime
DefaultDirName={pf}\PIME
DefaultGroupName=AI输入法
OutputBaseFilename=AI输入法_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
PrivilegesRequired=admin
ArchitecturesAllowed=x86
ArchitecturesInstallIn64BitMode=
SetupIconFile=ai_ime\icon.ico
UninstallDisplayName=AI输入法
WizardStyle=modern
; 安装包标题
[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[CustomMessages]
chinesesimplified:PimeNotFound=PIME 框架未安装。%n%n安装程序将自动下载并安装 PIME v1.3.0。%n%n是否继续？
chinesesimplified:PimeInstallFailed=PIME 安装失败。请手动安装 PIME 后重试。%n下载地址：https://github.com/EasyIME/PIME/releases
chinesesimplified:ModelOptional=AI 模型（本地推理，约 400MB）%n%n不安装模型也可使用基础输入法功能，%n或配置云端 API 替代。
chinesesimplified:PythonNotFound=未检测到系统 Python（3.10+）。%n%n本地 AI 需要系统 Python + llama-cpp-python。%n如不使用本地 AI，可跳过此步骤。%n%n是否继续安装（不安装 Python 依赖）？
chinesesimplified:CloudApiHint=云端 AI 配置%n%n如需 AI 预测功能，可配置云端 API：%n1. 创建目录 %USERPROFILE%\.ai_ime\%n2. 创建 api_config.json 文件%n3. 填入 DeepSeek/OpenAI 的 API key%n%n详细信息见 README.md

[Tasks]
Name: "installmodel"; Description: "安装 AI 模型（qwen2.5-0.5b，约 400MB）"; GroupDescription: "可选组件："; Flags: checkedonce

[Files]
; ===== 输入法核心文件 =====
Source: "ai_ime\ai_ime_ime.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\config.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\user_memory.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\ime.json"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion

; AI 模块
Source: "ai_ime\ai\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\cloud_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\local_llm_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\ollama_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\predictor.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\lexicon_expander.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion

; 拼音模块
Source: "ai_ime\pinyin\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\candidates.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\dict_loader.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\parser.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\syllables.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion

; 数据
Source: "ai_ime\data\base_dict.txt"; DestDir: "{app}\python\input_methods\ai_ime\data"; Flags: ignoreversion
Source: "ai_ime\data\api_config.example.json"; DestDir: "{app}\python\input_methods\ai_ime\data"; Flags: ignoreversion

; 本地 LLM 服务
Source: "local_llm_server.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion

; ===== AI 模型（可选） =====
Source: "models\*.gguf"; DestDir: "{app}\python\input_methods\ai_ime\models"; Flags: ignoreversion skipifsourcedoesntexist; Tasks: installmodel

[Run]
; 安装 Python 依赖
Filename: "cmd.exe"; Parameters: "/c pip install llama-cpp-python --quiet 2>nul"; Flags: runhidden nowait skipifdoesntexist; StatusMsg: "安装 Python 依赖..."
; 重启 PIME
Filename: "cmd.exe"; Parameters: "/c taskkill /f /im PIMELauncher.exe 2>nul & timeout /t 2 /nobreak >nul & start "" ""{app}\PIMELauncher.exe"""; Flags: runhidden; StatusMsg: "重启输入法服务..."

[Code]
var
  PimeNeedsInstall: Boolean;

function InitializeSetup(): Boolean;
var
  PimeDir: string;
begin
  PimeDir := ExpandConstant('{pf}\PIME');
  PimeNeedsInstall := not FileExists(PimeDir + '\PIMELauncher.exe');

  if PimeNeedsInstall then
  begin
    if MsgBox(CustomMessage('PimeNotFound'), mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
      Exit;
    end;
  end;

  Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
  PimeInstaller: string;
  DownloadUrl: string;
begin
  Result := True;

  // 在准备安装页面之前，先安装 PIME
  if (CurPageID = wpReady) and PimeNeedsInstall then
  begin
    PimeInstaller := ExpandConstant('{tmp}\PIME-installer.exe');
    DownloadUrl := 'https://github.com/EasyIME/PIME/releases/download/v1.3.0-stable/PIME-1.3.0-stable-x86.exe';

    WizardForm.StatusLabel.Caption := '下载 PIME 框架...';
    try
      DownloadTemporaryFile(DownloadUrl, 'PIME-installer.exe', '', nil);
    except
      MsgBox(CustomMessage('PimeInstallFailed'), mbError, MB_OK);
      Result := False;
      Exit;
    end;

    WizardForm.StatusLabel.Caption := '安装 PIME 框架...';
    Exec(PimeInstaller, '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);

    if ResultCode <> 0 then
    begin
      MsgBox(CustomMessage('PimeInstallFailed'), mbError, MB_OK);
      Result := False;
      Exit;
    end;

    PimeNeedsInstall := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 显示云端 API 配置提示
    MsgBox(CustomMessage('CloudApiHint'), mbInformation, MB_OK);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python\input_methods\ai_ime"

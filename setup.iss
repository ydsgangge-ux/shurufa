; AI IME - Inno Setup Installer Script
; Build: run build_installer.ps1 or compile in Inno Setup IDE
;
; Package includes:
; - PIME framework (auto-download if not installed)
; - Input method files + dictionary
; - AI model (optional, compressed)
; - Python dependencies

#define MyAppName "AI IME"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AI-IME"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/ai-ime/ai-ime
DefaultDirName={pf}\PIME
DefaultGroupName=AI IME
OutputBaseFilename=AI_IME_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
PrivilegesRequired=admin
ArchitecturesAllowed=x86compatible
UninstallDisplayName=AI IME
WizardStyle=modern
; Disable icon (file doesn't exist yet)
; SetupIconFile=ai_ime\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
PimeNotFound=PIME framework is not installed.%n%nThe installer will download and install PIME v1.3.0 automatically.%n%nContinue?
PimeInstallFailed=PIME installation failed. Please install PIME manually:%nhttps://github.com/EasyIME/PIME/releases
CloudApiHint=Cloud AI Configuration%n%nTo enable AI prediction, configure a cloud API:%n1. Create directory: C:\Users\YourName\.ai_ime\%n2. Create file: api_config.json%n3. Add your DeepSeek/OpenAI API key%n%nSee README.md for details

[Tasks]
Name: "installmodel"; Description: "Install AI model (qwen2.5-0.5b, ~400MB)"; GroupDescription: "Optional:"; Flags: checkedonce

[Files]
; ===== Core input method files =====
Source: "ai_ime\ai_ime_ime.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\config.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\user_memory.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion
Source: "ai_ime\ime.json"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion

; AI module
Source: "ai_ime\ai\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\cloud_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\local_llm_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\ollama_client.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\predictor.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion
Source: "ai_ime\ai\lexicon_expander.py"; DestDir: "{app}\python\input_methods\ai_ime\ai"; Flags: ignoreversion

; Pinyin module
Source: "ai_ime\pinyin\__init__.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\candidates.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\dict_loader.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\parser.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion
Source: "ai_ime\pinyin\syllables.py"; DestDir: "{app}\python\input_methods\ai_ime\pinyin"; Flags: ignoreversion

; Data
Source: "ai_ime\data\base_dict.txt"; DestDir: "{app}\python\input_methods\ai_ime\data"; Flags: ignoreversion
Source: "ai_ime\data\api_config.example.json"; DestDir: "{app}\python\input_methods\ai_ime\data"; Flags: ignoreversion skipifsourcedoesntexist

; Local LLM server
Source: "local_llm_server.py"; DestDir: "{app}\python\input_methods\ai_ime"; Flags: ignoreversion

; ===== AI model (optional) =====
; Model files are large (~400MB), use separate download or external packaging
; Source: "models\*.gguf"; DestDir: "{app}\python\input_methods\ai_ime\models"; Flags: ignoreversion skipifsourcedoesntexist; Tasks: installmodel

[Run]
; Install Python dependencies
Filename: "cmd.exe"; Parameters: "/c pip install llama-cpp-python --quiet 2>nul"; Flags: runhidden nowait; StatusMsg: "Installing Python dependencies..."
; Restart PIME
Filename: "cmd.exe"; Parameters: "/c taskkill /f /im PIMELauncher.exe 2>nul & timeout /t 2 /nobreak >nul & start "" ""{app}\PIMELauncher.exe"""; Flags: runhidden; StatusMsg: "Restarting input service..."

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

  if (CurPageID = wpReady) and PimeNeedsInstall then
  begin
    PimeInstaller := ExpandConstant('{tmp}\PIME-installer.exe');
    DownloadUrl := 'https://github.com/EasyIME/PIME/releases/download/v1.3.0-stable/PIME-1.3.0-stable-x86.exe';

    WizardForm.StatusLabel.Caption := 'Downloading PIME framework...';
    try
      DownloadTemporaryFile(DownloadUrl, 'PIME-installer.exe', '', nil);
    except
      MsgBox(CustomMessage('PimeInstallFailed'), mbError, MB_OK);
      Result := False;
      Exit;
    end;

    WizardForm.StatusLabel.Caption := 'Installing PIME framework...';
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
    MsgBox(CustomMessage('CloudApiHint'), mbInformation, MB_OK);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python\input_methods\ai_ime"

; Zamak_Valsadae Windows installer (Inno Setup).
;
; Produces a small setup .exe that copies the app's source files and creates
; Start Menu / Desktop shortcuts. It does NOT bundle Python/Node.js/ffmpeg or
; any AI models - those are still downloaded on first launch by run.bat
; (same portable-runtime flow as install.bat/install.ps1), so first launch
; needs internet access and can take a while. This keeps the installer small
; and matches how the app already manages its runtime and model downloads.
;
; Build: install Inno Setup (https://jrsoftware.org/isinfo.php), then either
; open this file in the Inno Setup Compiler and click Compile, or run:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\installer.iss
; Output goes to installer\dist\Zamak_Valsadae_Setup.exe
;
; This build is NOT code-signed. Windows SmartScreen will warn first-time
; users ("Windows protected your PC") - they need to click "More info" ->
; "Run anyway". A code-signing certificate removes this warning but is a
; separate, paid step not covered here.
;
; run.bat launches the app in a native window via pywebview (WebView2), not
; a browser tab. WebView2 Runtime ships with Windows 10/11 by default; only
; very old/unpatched systems would need to install it separately from
; Microsoft.
;
; Shortcuts point at ZamakValsadae.exe (built from launcher.py via
; build_launcher.bat - run that FIRST so launcher_dist\ZamakValsadae.exe
; exists before compiling this script). It's a small PyInstaller-built
; native launcher that does exactly what run.bat does, but with no visible
; window at all - including on first launch, when the runtime install runs
; hidden with output captured to install.log next to the exe. run.bat/
; install.bat are still bundled as a manual/troubleshooting fallback.

#define MyAppName "Zamak_Valsadae (자막발사대)"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Zamak_Valsadae"

[Setup]
AppId={{6F9C7B3E-6E2C-4B7A-9B7B-9B7C6F5C1A2D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Zamak_Valsadae
DefaultGroupName=Zamak_Valsadae
DisableProgramGroupPage=yes
; Per-user install under %LOCALAPPDATA% - no admin rights required, and the
; app's own runtime/data downloads land in the same writable folder tree.
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Zamak_Valsadae_Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 아이콘:"

[Files]
Source: "..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,.pytest_cache,.omc"
Source: "..\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "node_modules,dist,.omc"
Source: "..\install.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\run.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\env.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\kill-servers.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "launcher_dist\ZamakValsadae.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Zamak_Valsadae"; Filename: "{app}\ZamakValsadae.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\제거"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Zamak_Valsadae"; Filename: "{app}\ZamakValsadae.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\ZamakValsadae.exe"; Description: "설치 마치고 바로 실행 (최초 실행 시 런타임 다운로드로 인터넷 필요, 수 분~수십 분 소요)"; Flags: postinstall skipifsilent nowait

; S-Q Creator Studio — Inno Setup script
; Per-user install (no admin), bundles ffmpeg.exe for merging.
; Version is injected from src/__init__.py at build time via /DMyAppVersion.
;
; The installer is built from release\portable\ and release\staging\,
; which release\build.bat fills in.

#ifndef MyAppVersion
  #define MyAppVersion "2.6.0"
#endif

; The folder the build was copied into. It is "portable", unless the old
; one was in use and the build went into "portable-new" instead.
#ifndef MyAppSource
  #define MyAppSource "portable"
#endif

#define MyAppName "S-Q Creator Studio"
#define MyAppPublisher "S-Q-Ali"
#define MyAppURL "https://github.com/S-Q-Ali/S-Q-Creator-Studio"
#define MyAppExeName "S-Q Creator Studio.exe"

[Setup]
AppId={{03d871b7-5dd8-4e41-849b-47a0b7c08c87}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\S-Q Creator Studio
DefaultGroupName=S-Q Creator Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=.
OutputBaseFilename=S-Q-Creator-Studio-Setup-{#MyAppVersion}
SetupIconFile=..\src\s_q_ali_media_downloader\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoCopyright={#MyAppPublisher}
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppSource}\S-Q Creator Studio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppSource}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyAppSource}\browsers\*"; DestDir: "{app}\browsers"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "staging\bin\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

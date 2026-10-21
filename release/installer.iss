; S-Q Creator Studio — Inno Setup script
; Per-user install (no admin), bundles ffmpeg.exe for merging.
; Version is injected from src/__init__.py at build time via /DMyAppVersion.

#ifndef MyAppVersion
  #define MyAppVersion "2.5.1"
#endif

#define MyAppName "S-Q Creator Studio"
#define MyAppPublisher "S-Q-Ali"
#define MyAppURL "https://github.com/S-Q-Ali/Bulk-Video-Downloader"
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
Source: "portable\S-Q Creator Studio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "portable\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "portable\browsers\*"; DestDir: "{app}\browsers"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "staging\bin\ffmpeg.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

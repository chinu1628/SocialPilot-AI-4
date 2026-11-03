#define MyAppName "SocialPilot AI"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "SocialPilot AI"
#define MyAppExeName "SocialPilotAI.exe"

[Setup]
AppId={{A6A4A6B2-88A4-4E75-9A5B-1D14D81E2D40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SocialPilot AI
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=SocialPilotAI-Setup-4.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Files]
Source: "dist\SocialPilotAI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\SocialPilot AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\SocialPilot AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SocialPilot AI"; Flags: postinstall nowait skipifsilent

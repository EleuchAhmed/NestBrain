#define MyAppName "Nestbrain Research Pipeline"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Nestbrain"
#define MyAppExeName "Nestbrain.exe"
#define MyAppOutputName "NestbrainSetup"

[Setup]
AppId={{D0A2E2A9-7A3E-4F99-BD8A-0E5E6C4C4F71}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
SourceDir=scripts\dist\Nestbrain
DefaultDirName={autopf}\Nestbrain
DefaultGroupName=Nestbrain Research Pipeline
DisableProgramGroupPage=yes
LicenseFile=..\..\..\installer_assets\license.txt
OutputDir=..\..\..\dist\installer
OutputBaseFilename={#MyAppOutputName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile=..\..\..\nestbrain\assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Nestbrain Research Pipeline"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Nestbrain Research Pipeline"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent; StatusMsg: "{cm:StatusFinalizing}"

[CustomMessages]
english.StatusInstallingFiles=Installing Nestbrain application files...
english.StatusCreatingShortcuts=Creating Start Menu and desktop shortcuts...
english.StatusFinalizing=Finalizing installation...
english.LaunchAfterInstall=Launch Nestbrain Research Pipeline
english.CreateDesktopIcon=Create a desktop shortcut

[Dirs]
Name: "{app}"; Permissions: users-modify

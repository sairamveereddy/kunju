#define MyAppName "Privacy Alarm"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Sairam"
#define MyAppExeName "PrivacyAlarm.exe"

[Setup]
AppId={{7A7EC8B9-856B-495F-AE6D-BDF1634F8D62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Privacy Alarm
DefaultGroupName={#MyAppName}
OutputDir=dist\installer
OutputBaseFilename=PrivacyAlarmSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "..\dist\PrivacyAlarm\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Tasks]
Name: "startup"; Description: "Start Privacy Alarm when Windows starts"; GroupDescription: "Startup options:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

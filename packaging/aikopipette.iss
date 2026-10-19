; Installateur Windows d'AikoPipette (Inno Setup 6)
#define AppVersion GetEnv("AIKOPIPETTE_VERSION")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{BC89CFAB-BBE2-40A9-BBCD-D051B294565B}
AppName=AikoPipette
AppVersion={#AppVersion}
AppPublisher=Aikographic
DefaultDirName={localappdata}\Programs\AikoPipette
DefaultGroupName=AikoPipette
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AikoPipette-Windows-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\AikoPipette.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "startup"; Description: "Lancer AikoPipette au démarrage de Windows"; GroupDescription: "Options :"
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Options :"; Flags: unchecked

[Files]
Source: "..\desktop\dist\AikoPipette\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AikoPipette"; Filename: "{app}\AikoPipette.exe"
Name: "{group}\Désinstaller AikoPipette"; Filename: "{uninstallexe}"
Name: "{userdesktop}\AikoPipette"; Filename: "{app}\AikoPipette.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AikoPipette"; ValueData: """{app}\AikoPipette.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\AikoPipette.exe"; Description: "Lancer AikoPipette"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM AikoPipette.exe"; Flags: runhidden; RunOnceId: "KillAikoPipette"

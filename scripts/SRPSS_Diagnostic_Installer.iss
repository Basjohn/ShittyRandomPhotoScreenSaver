; Installer for the separate SRPSS diagnostic runtime.
;
; This product does not register itself as the Windows screensaver, replace
; SRPSS.scr, install the Media Center payload, or provision shared helpers.

[Setup]
AppId={{9E730AA6-0FF0-4EF5-AE55-7D88956F32DE}
AppName=SRPSS Diagnostic
AppVersion=4.7.2
AppPublisher=Jayde Ver Elst
DefaultDirName={localappdata}\SRPSS Diagnostic
DefaultGroupName=SRPSS Diagnostic
PrivilegesRequired=lowest
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\release\installers
OutputBaseFilename=Setup_SRPSS_Diagnostic
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
SetupIconFile=..\SRPSS.ico
UninstallDisplayIcon={app}\SRPSS_Diagnostic.exe
WizardSmallImageFile=..\images\LogoBMP.bmp
VersionInfoVersion=4.7.2

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktop"; Description: "Create a Desktop shortcut"; GroupDescription: "Additional options:"; Flags: unchecked
Name: "runafter"; Description: "Run the diagnostic runtime after install"; GroupDescription: "Post-install option:"; Flags: unchecked

[Files]
Source: "..\release\diagnostic\SRPSS_Diagnostic.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SRPSS.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Run SRPSS Diagnostic"; Filename: "{app}\SRPSS_Diagnostic.exe"; Parameters: "/s"; IconFilename: "{app}\SRPSS.ico"
Name: "{group}\Open SRPSS Diagnostic Settings"; Filename: "{app}\SRPSS_Diagnostic.exe"; Parameters: "/c"; IconFilename: "{app}\SRPSS.ico"
Name: "{group}\Open Diagnostic Logs"; Filename: "{sys}\explorer.exe"; Parameters: """{app}\logs"""; IconFilename: "{app}\SRPSS.ico"
Name: "{userdesktop}\SRPSS Diagnostic"; Filename: "{app}\SRPSS_Diagnostic.exe"; Parameters: "/s"; IconFilename: "{app}\SRPSS.ico"; Tasks: desktop

[Run]
Filename: "{app}\SRPSS_Diagnostic.exe"; Parameters: "/s"; Description: "Run SRPSS Diagnostic"; Flags: nowait postinstall skipifsilent; Tasks: runafter

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

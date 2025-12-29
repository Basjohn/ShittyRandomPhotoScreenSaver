; Inno Setup script for SRPSS - Media Center (MC onedir build)
; Builds an installer that packages the entire onedir payload (Nuitka
; --standalone output) and offers optional shortcuts + run-after option.
;
; Usage:
;   1) Run scripts/build_nuitka_mc_onedir.ps1 to produce:
;        release\main_mc.dist\SRPSS_Media_Center.exe
;        release\main_mc.dist\*
;   2) Compile this ISS script in Inno Setup. Output installer will copy
;      every file under SRPSS_Media_Center.dist into {app}.
;

[Setup]
AppId={{31A3E38F-0A6C-46CF-8934-9EB8A42F0463}
AppName=SRPSS - Media Center
AppVersion=1.5.8.0
AppPublisher=Jayde Ver Elst
AppPublisherURL=https://github.com/Basjohn/ShittyRandomPhotoScreenSaver
AppSupportURL=https://github.com/Basjohn/ShittyRandomPhotoScreenSaver
AppUpdatesURL=https://github.com/Basjohn/ShittyRandomPhotoScreenSaver
DefaultDirName={localappdata}\SRPSS Media Center
DefaultGroupName=SRPSS - Media Center
PrivilegesRequired=lowest
DisableDirPage=no
DisableProgramGroupPage=yes
OutputBaseFilename=Setup_SRPSS_Media_Center
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
SetupIconFile=..\SRPSS.ico
UninstallDisplayIcon={app}\SRPSS.ico
VersionInfoVersion=1.5.8.0
AllowUNCPath=False

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startmenu"; Description: "Create Start Menu Shortcuts"; GroupDescription: "Additional options:"
Name: "desktop"; Description: "Create Desktop Shortcuts"; GroupDescription: "Additional options:"
Name: "runafter"; Description: "Run After Install"; GroupDescription: "Post-install option:"; Flags: unchecked

[Files]
; Copy everything inside the Nuitka onedir output into {app}
Source: "..\release\main_mc.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Include the EXE itself (for convenience when browsing install dir)
Source: "..\release\main_mc.dist\SRPSS_Media_Center.exe"; DestDir: "{app}"; Flags: ignoreversion
; Installer icon for shortcuts / ARP entry
Source: "..\SRPSS.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SRPSS - Media Center"; Filename: "{app}\SRPSS_Media_Center.exe"; Tasks: startmenu
Name: "{commondesktop}\SRPSS - Media Center"; Filename: "{app}\SRPSS_Media_Center.exe"; Tasks: desktop

[Run]
Filename: "{app}\SRPSS_Media_Center.exe"; Description: "Launch SRPSS - Media Center"; Flags: nowait postinstall skipifsilent; Tasks: runafter

[UninstallDelete]
; Ensure the install directory is removed on uninstall (default behavior), but
; explicitly clean any residual dist folders if structure changes in future.
Type: filesandordirs; Name: "{app}"

[InstallDelete]
; No legacy files to remove for MC yet, keep placeholder section for parity.

; Inno Setup script for ShittyRandomPhotoScreenSaver (SRPSS)
; Builds an installer that:
; - Copies SRPSS.scr into %SystemRoot%\System32
; - Sets SCRNSAVE.EXE for the current user to SRPSS.scr
;
; Usage (dev side):
; 1) Build SRPSS.exe via the PyInstaller script:
;    - scripts/build.ps1       -> ..\release\SRPSS.exe
; 2) Rename SRPSS.exe to SRPSS.scr and leave it under ..\release\.
; 3) Open this .iss file in Inno Setup and Compile.
; 4) Distribute the generated Setup_SRPSS.exe to end users.

[Setup]
AppId={{D8A5B7C8-9F9B-4F0D-9C5A-0F2F6A1E7C11}
AppName=ShittyRandomPhotoScreenSaver
AppVersion=1.5.5.0.0
AppPublisher=Jayde Ver Elst
DefaultDirName={commonpf}\SRPSS
DefaultGroupName=ShittyRandomPhotoScreenSaver
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=Setup_SRPSS
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
SetupIconFile=..\SRPSS.ico
UninstallDisplayIcon={app}\SRPSS.ico
VersionInfoVersion=1.5.5.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main screensaver: build via scripts/build.ps1, then rename SRPSS.exe -> SRPSS.scr
Source: "..\release\SRPSS.scr"; DestDir: "{sys}"; Flags: ignoreversion

; Application icon used for shortcuts and ARP entry
Source: "..\SRPSS.ico"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; Remove any legacy SRPSS screen saver binaries that can cause duplicate
; entries in the Windows Screen Saver dropdown before installing the
; current SRPSS.scr.
Type: files; Name: "{sys}\\Sprss.scr"
Type: files; Name: "{sys}\\PSrpss.scr"
Type: files; Name: "{sys}\\ShittyRandomPhotoScreenSaver.scr"

[Registry]
; Set SRPSS.scr as the current user's active screensaver
Root: HKCU; Subkey: "Control Panel\\Desktop"; ValueType: string; ValueName: "SCRNSAVE.EXE"; ValueData: "{sys}\\SRPSS.scr"; Flags: uninsdeletevalue

[Icons]
; Desktop shortcut to open Screen Saver Settings (with SRPSS selected).
; Using control.exe desk.cpl,,1 is the supported way on modern Windows.
Name: "{commondesktop}\\Configure ShittyRandomPhotoScreenSaver"; Filename: "{sys}\\control.exe"; Parameters: "desk.cpl,,1"; WorkingDir: "{sys}"; IconFilename: "{app}\\SRPSS.ico"

; Start menu shortcut to the same Screen Saver Settings dialog
Name: "{group}\\Configure ShittyRandomPhotoScreenSaver"; Filename: "{sys}\\control.exe"; Parameters: "desk.cpl,,1"; WorkingDir: "{sys}"; IconFilename: "{app}\\SRPSS.ico"

[Run]
; No post-install run step by default. The user can open Screen Saver
; Settings via the standard control panel entry.

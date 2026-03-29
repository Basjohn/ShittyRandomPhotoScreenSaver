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
AppVersion=3.2.0
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
WizardSmallImageFile=..\images\LogoBMP.bmp
VersionInfoVersion=3.2.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main screensaver: build via scripts/build.ps1, then rename SRPSS.exe -> SRPSS.scr
Source: ".\..\release\SRPSS.scr"; DestDir: "{sys}"; Flags: ignoreversion

; Application icon used for shortcuts and ARP entry
Source: ".\..\SRPSS.ico"; DestDir: "{app}"; Flags: ignoreversion

; Media provider logos (Spotify is bundled via images dir; MusicBee icon)
Source: ".\..\images\icons8-musicbee-96.png"; DestDir: "{app}\images"; Flags: ignoreversion

; Reddit helper watcher (placed at install time, not runtime-extracted)
Source: ".\..\release\helpers\SRPSS_RedditHelper.exe"; DestDir: "{commonappdata}\SRPSS\helper"; Flags: ignoreversion

; Authoritative curated visualizer presets shipped directly from the repository tree.
; Delivered to a stable ProgramData path so upgrades always clean-replace them.
Source: ".\..\presets\visualizer_modes\*"; DestDir: "{commonappdata}\SRPSS\presets\visualizer_modes"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; Remove any legacy SRPSS screen saver binaries that can cause duplicate
; entries in the Windows Screen Saver dropdown before installing the
; current SRPSS.scr.
Type: files; Name: "{sys}\\Sprss.scr"
Type: files; Name: "{sys}\\PSrpss.scr"
Type: files; Name: "{sys}\\ShittyRandomPhotoScreenSaver.scr"
; Wipe old shipped curated presets before the new ones land so stale/renamed
; files are never left behind alongside the authoritative replacement set.
Type: filesandordirs; Name: "{commonappdata}\SRPSS\presets\visualizer_modes"

[Registry]
; Set SRPSS.scr as the current user's active screensaver
Root: HKCU; Subkey: "Control Panel\Desktop"; ValueType: string; ValueName: "SCRNSAVE.EXE"; ValueData: "{sys}\SRPSS.scr"; Flags: uninsdeletevalue

; Start the Reddit helper watcher on user login.
; --idle-exit-seconds 300: helper exits automatically 5 minutes after the queue
; is empty, preventing indefinite lingering between screensaver sessions.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "SRPSS_RedditHelper"; ValueType: string; ValueData: """{commonappdata}\SRPSS\helper\SRPSS_RedditHelper.exe"" --watch --queue ""{commonappdata}\SRPSS\url_queue"" --idle-exit-seconds 300"; Flags: uninsdeletevalue

[Icons]
; Desktop shortcut to open Screen Saver Settings (with SRPSS selected).
; Using control.exe desk.cpl,,1 is the supported way on modern Windows.
Name: "{commondesktop}\Configure SRPSS"; Filename: "{sys}\control.exe"; Parameters: "desk.cpl,,1"; WorkingDir: "{sys}"; IconFilename: "{app}\SRPSS.ico"

; Start menu shortcut to the same Screen Saver Settings dialog
Name: "{group}\Configure SRPSS"; Filename: "{sys}\control.exe"; Parameters: "desk.cpl,,1"; WorkingDir: "{sys}"; IconFilename: "{app}\SRPSS.ico"

[UninstallRun]
; Kill watcher before uninstall
Filename: "taskkill"; Parameters: "/F /IM SRPSS_RedditHelper.exe"; Flags: runhidden nowait; RunOnceId: "KillHelper"

[UninstallDelete]
; Clean up Reddit helper and queue
Type: files; Name: "{commonappdata}\SRPSS\helper\SRPSS_RedditHelper.exe"
Type: dirifempty; Name: "{commonappdata}\SRPSS\helper"
Type: filesandordirs; Name: "{commonappdata}\SRPSS\url_queue"
; Remove shipped curated presets that were installed to ProgramData
Type: filesandordirs; Name: "{commonappdata}\SRPSS\presets\visualizer_modes"
Type: dirifempty; Name: "{commonappdata}\SRPSS\presets"

[Run]
; No post-install run step by default. The user can open Screen Saver
; Settings via the standard control panel entry.
Filename: "{sys}\control.exe"; Parameters: "desk.cpl,,1"; Description: "Open Screen Saver Settings now"; Flags: postinstall nowait skipifsilent

; Inno Setup script for SRPSS - Media Center (MC onedir build)
; Builds an installer that packages the entire onedir payload (Nuitka
; --standalone output) and offers optional shortcuts + run-after option.
;
; Usage:
;   1) Run scripts/build_nuitka_mc_onedir.ps1 to produce:
;        release\media_center\SRPSS_Media_Center.exe
;        release\media_center\*
;   2) Compile this ISS script in Inno Setup. Output installer will copy
;      every file under release\media_center into {app}.
;

; Remove yesterday's installer before compiler-version/style validation.
; A failed compile must never leave stale Setup_*.exe looking current.
#expr DeleteFileNow(AddBackslash(SourcePath) + '..\release\installers\Setup_SRPSS_Media_Center.exe')

; Installer styling/background directives require Inno Setup 6.7.2+; 7.x remains supported.
#if Ver < EncodeVer(6, 7, 2)
#error SRPSS installers require Inno Setup 6.7.2 or newer (Inno Setup 7.x is supported).
#endif

[Setup]
AppId={{31A3E38F-0A6C-46CF-8934-9EB8A42F0463}
AppName=SRPSS - Media Center
AppVersion=5.0.7
AppPublisher=Jayde Ver Elst
AppPublisherURL=https://github.com/Basjohn/ShittyRandomPhotoScreenSaver
AppSupportURL=https://github.com/Basjohn/ShittyRandomPhotoScreenSaver
AppUpdatesURL=https://github.com/Basjohn/ShittyRandomPhotoScreenSaver
DefaultDirName={localappdata}\SRPSS Media Center
DefaultGroupName=SRPSS - Media Center
PrivilegesRequired=admin
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=..\release\installers
OutputBaseFilename=Setup_SRPSS_Media_Center
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.scr
RestartApplications=no
SetupIconFile=..\SRPSS.ico
UninstallDisplayIcon={app}\SRPSS.ico
VersionInfoVersion=5.0.7
WizardStyle=modern dark includetitlebar hidebevels
WizardBackColor=#0d181e
WizardImageFile=
WizardSmallImageFile=..\ui\assets\installer\SRPSSWizard.png
WizardSmallImageBackColor=none
AllowUNCPath=False

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; 5.0.0 migration reset remains available manually, but defaults OFF.
Name: "resetsettings"; Description: "Revert Settings To Defaults"; GroupDescription: "Settings:"; Flags: unchecked
Name: "startmenu"; Description: "Create Start Menu Shortcuts"; GroupDescription: "Additional options:"
Name: "desktop"; Description: "Create Desktop Shortcuts"; GroupDescription: "Additional options:"
Name: "runafter"; Description: "Run After Install"; GroupDescription: "Post-install option:"; Flags: unchecked

[Files]
; Installed shortcut/ARP icon. Wizard branding uses the transparent PNG above.
Source: "..\SRPSS.ico"; DestDir: "{app}"; Flags: ignoreversion

; Copy everything inside the Nuitka onedir output into {app}. This wildcard
; already includes SRPSS_Media_Center.exe; do not duplicate the EXE below.
Source: "..\release\media_center\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "presets\visualizer_modes\*"
; Keep one packaged copy inside the MC install so visualizer imports can
; still restore from bundled assets even though runtime loading now uses the
; shared ProgramData tree.
Source: "..\release\media_center\presets\visualizer_modes\*"; DestDir: "{app}\presets\visualizer_modes"; Flags: recursesubdirs createallsubdirs ignoreversion
; Active curated preset tree shared with SCR/NORMAL builds.
Source: "..\release\media_center\presets\visualizer_modes\*"; DestDir: "{commonappdata}\SRPSS\presets\visualizer_modes"; Flags: recursesubdirs createallsubdirs ignoreversion
; Active curated Settings + Widget theme tree shared with SCR/NORMAL builds.
Source: "..\release\media_center\themes\*"; DestDir: "{commonappdata}\SRPSS\themes"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\release\media_center\resources\tutuogg.ogg"; DestDir: "{commonappdata}\SRPSS\sounds"; Flags: ignoreversion
Source: "..\release\media_center\resources\jedimodeyall.mp3"; DestDir: "{commonappdata}\SRPSS\sounds"; Flags: ignoreversion

[Registry]
; When the 5.0.0 migration-reset task is selected, delete the pre-JSON MC QSettings tree too.
; Deleting only settings_v2.json would otherwise let first launch re-import these legacy values.
Root: HKCU; Subkey: "Software\ShittyRandomPhotoScreenSaver\Screensaver_MC"; Flags: deletekey; Tasks: resetsettings

[Icons]
Name: "{group}\SRPSS - Media Center"; Filename: "{app}\SRPSS_Media_Center.exe"; Tasks: startmenu
Name: "{userdesktop}\SRPSS - Media Center"; Filename: "{app}\SRPSS_Media_Center.exe"; Tasks: desktop

[Run]
Filename: "{app}\SRPSS_Media_Center.exe"; Description: "Launch SRPSS - Media Center"; Flags: nowait postinstall skipifsilent; Tasks: runafter

[UninstallDelete]
; Ensure the install directory is removed on uninstall (default behavior), but
; explicitly clean any residual dist folders if structure changes in future.
Type: filesandordirs; Name: "{app}"

[InstallDelete]
; 5.0.0 migration-reset task for the Media Center profile only.
Type: files; Name: "{userappdata}\SRPSS_MC\settings_v2.json"; Tasks: resetsettings

; CurStepChanged clean-replaces the entire installer-owned {app} payload while
; preserving only Inno's unins* bookkeeping files. Keep shared mutable/catalogue
; trees below clean-replaced independently.
Type: filesandordirs; Name: "{commonappdata}\SRPSS\presets\visualizer_modes"
Type: filesandordirs; Name: "{commonappdata}\SRPSS\themes"
Type: files; Name: "{commonappdata}\SRPSS\sounds\tutuogg.ogg"
Type: files; Name: "{commonappdata}\SRPSS\sounds\jedimodeyall.mp3"

[Code]
function IsInstallerBookkeepingFile(const Name: String): Boolean;
var
  LowerName: String;
begin
  LowerName := Lowercase(Name);
  Result := Pos('unins', LowerName) = 1;
end;

procedure CleanInstallerOwnedAppPayload();
var
  AppDir: String;
  EntryPath: String;
  FindRec: TFindRec;
  DeleteOK: Boolean;
  Failed: Boolean;
begin
  AppDir := ExpandConstant('{app}');
  if not DirExists(AppDir) then
    Exit;

  Failed := False;
  Log('SRPSS: clean-replacing installer-owned application payload: ' + AppDir);
  if FindFirst(AddBackslash(AppDir) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
           (not IsInstallerBookkeepingFile(FindRec.Name)) then
        begin
          EntryPath := AddBackslash(AppDir) + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            DeleteOK := DelTree(EntryPath, True, True, True)
          else
            DeleteOK := DelTree(EntryPath, False, True, False);

          if not DeleteOK then
          begin
            Log('SRPSS: failed to remove stale installer-owned payload: ' + EntryPath);
            Failed := True;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;

  if Failed then
    RaiseException(
      'SRPSS could not clean-replace its application directory. ' +
      'Close any running SRPSS process and retry the installer.'
    );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    CleanInstallerOwnedAppPayload();
end;

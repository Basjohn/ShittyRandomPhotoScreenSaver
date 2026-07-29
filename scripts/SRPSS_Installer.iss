; Inno Setup script for ShittyRandomPhotoScreenSaver (SRPSS)
; Builds an installer that:
; - Copies SRPSS.scr into %SystemRoot%\System32
; - Sets SCRNSAVE.EXE for the current user to SRPSS.scr
;
; Usage (dev side):
; 1) Run tools/build_runner.py and build Standard Screensaver.
; 2) Compile this .iss file in Inno Setup (or select Standard Installer).
; 3) Distribute release\installers\Setup_SRPSS.exe to end users.

[Setup]
AppId={{D8A5B7C8-9F9B-4F0D-9C5A-0F2F6A1E7C11}
AppName=ShittyRandomPhotoScreenSaver
AppVersion=4.6.9c
AppPublisher=Jayde Ver Elst
DefaultDirName={commonpf}\SRPSS
DefaultGroupName=ShittyRandomPhotoScreenSaver
PrivilegesRequired=admin
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\release\installers
OutputBaseFilename=Setup_SRPSS
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64os
SetupIconFile=..\SRPSS.ico
UninstallDisplayIcon={app}\SRPSS.ico
WizardSmallImageFile=..\images\LogoBMP.bmp
VersionInfoVersion=4.6.9c

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main screensaver from the canonical release payload.
Source: ".\..\release\screensaver\SRPSS.scr"; DestDir: "{sys}"; Flags: ignoreversion

; Application icon used for shortcuts and ARP entry.
Source: ".\..\SRPSS.ico"; DestDir: "{app}"; Flags: ignoreversion

; Media provider logos.
Source: ".\..\images\icons8-musicbee-96.png"; DestDir: "{app}\images"; Flags: ignoreversion

; Reddit helper watcher bundle.
Source: ".\..\release\reddit_helper\*"; DestDir: "{commonappdata}\SRPSS\helper"; Flags: recursesubdirs createallsubdirs ignoreversion

; Shared scheduled-task template.
Source: ".\reddit_helper_task_template.xml"; Flags: dontcopy

; Curated visualizer presets and sounds.
Source: ".\..\presets\visualizer_modes\*"; DestDir: "{commonappdata}\SRPSS\presets\visualizer_modes"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: ".\..\resources\tutuogg.ogg"; DestDir: "{commonappdata}\SRPSS\sounds"; Flags: ignoreversion

[Dirs]
; Keep normal inherited ProgramData ACLs. Add only the ordinary rights each
; user-session helper directory actually needs.
Name: "{commonappdata}\SRPSS"
Name: "{commonappdata}\SRPSS\helper"; Permissions: users-readexec
Name: "{commonappdata}\SRPSS\presets"
Name: "{commonappdata}\SRPSS\sounds"
Name: "{commonappdata}\SRPSS\url_queue"; Permissions: users-modify
Name: "{commonappdata}\SRPSS\logs"; Permissions: users-modify
Name: "{commonappdata}\SRPSS\helper_signals"; Permissions: users-modify

[InstallDelete]
; Remove legacy screen saver binaries.
Type: files; Name: "{sys}\\Sprss.scr"
Type: files; Name: "{sys}\\PSrpss.scr"
Type: files; Name: "{sys}\\ShittyRandomPhotoScreenSaver.scr"

; Clean-replace shipped data and helper bundle.
Type: filesandordirs; Name: "{commonappdata}\SRPSS\presets\visualizer_modes"
Type: filesandordirs; Name: "{commonappdata}\SRPSS\helper"
Type: files; Name: "{commonappdata}\SRPSS\sounds\tutuogg.ogg"

[Registry]
; Set SRPSS.scr as the current user's active screensaver.
Root: HKCU; Subkey: "Control Panel\Desktop"; ValueType: string; ValueName: "SCRNSAVE.EXE"; ValueData: "{sys}\SRPSS.scr"; Flags: uninsdeletevalue

; Remove the legacy login-start helper entry.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "SRPSS_RedditHelper"; Flags: deletevalue

[Icons]
Name: "{commondesktop}\Configure SRPSS"; Filename: "{sys}\control.exe"; Parameters: "desk.cpl,,1"; WorkingDir: "{sys}"; IconFilename: "{app}\SRPSS.ico"
Name: "{group}\Configure SRPSS"; Filename: "{sys}\control.exe"; Parameters: "desk.cpl,,1"; WorkingDir: "{sys}"; IconFilename: "{app}\SRPSS.ico"

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM SRPSS_RedditHelper.exe"; Flags: runhidden nowait; RunOnceId: "KillHelper"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""SRPSS_RedditHelper"" /F"; Flags: runhidden waituntilterminated; RunOnceId: "DeleteHelperTask"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""\SRPSS\RedditHelper"" /F"; Flags: runhidden waituntilterminated; RunOnceId: "DeleteLegacyHelperTask"

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\SRPSS\helper"
Type: filesandordirs; Name: "{commonappdata}\SRPSS\url_queue"

[Run]
Filename: "{sys}\control.exe"; Parameters: "desk.cpl,,1"; Description: "Open Screen Saver Settings now"; Flags: postinstall nowait skipifsilent

[Code]
function XmlEscape(const Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '&', '&amp;', True);
  StringChangeEx(Result, '<', '&lt;', True);
  StringChangeEx(Result, '>', '&gt;', True);
  StringChangeEx(Result, '"', '&quot;', True);
  StringChangeEx(Result, #39, '&apos;', True);
end;

function BuildCurrentUserId(): String;
var
  DomainName: String;
  UserName: String;
begin
  DomainName := Trim(GetEnv('USERDOMAIN'));
  UserName := Trim(ExpandConstant('{username}'));
  if (DomainName <> '') and (UserName <> '') then
    Result := DomainName + '\' + UserName
  else
    Result := UserName;
end;

procedure TryDeleteTaskByName(const TaskName: String);
var
  ResultCode: Integer;
  SchtasksPath: String;
begin
  SchtasksPath := ExpandConstant('{sys}\schtasks.exe');
  if Exec(
      SchtasksPath,
      '/Delete /TN "' + TaskName + '" /F',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
     ) then
    Log(Format('SRPSS: delete task "%s" rc=%d', [TaskName, ResultCode]))
  else
    Log('SRPSS: delete task launch failed for "' + TaskName + '"');
end;

function BuildHelperArguments(
  const QueueDir, LogDir, SignalDir, SessionTicket: String;
  const IdleExitSeconds: Integer
): String;
begin
  Result :=
    '--watch ' +
    '--queue "' + QueueDir + '" ' +
    '--log-dir "' + LogDir + '" ' +
    '--signal-dir "' + SignalDir + '" ' +
    '--session-ticket "' + SessionTicket + '" ' +
    '--idle-exit-seconds ' + IntToStr(IdleExitSeconds);
end;

function RenderRedditHelperTaskXml(
  const TemplateText: String;
  const TaskName, TaskUserId, HelperExe, HelperArgs: String
): String;
begin
  Result := TemplateText;
  StringChangeEx(Result, '__AUTHOR__', XmlEscape('SRPSS Installer'), True);
  StringChangeEx(Result, '__TASK_NAME__', XmlEscape(TaskName), True);
  StringChangeEx(Result, '__USER_ID__', XmlEscape(TaskUserId), True);
  StringChangeEx(Result, '__COMMAND__', XmlEscape(HelperExe), True);
  StringChangeEx(Result, '__ARGUMENTS__', XmlEscape(HelperArgs), True);
end;

procedure RegisterRedditHelperTask();
var
  TemplatePath: String;
  TemplateTextAnsi: AnsiString;
  TemplateText: String;
  RenderedXml: String;
  TaskService: Variant;
  RootFolder: Variant;
  RegisteredTask: Variant;
  HelperExe: String;
  QueueDir: String;
  LogDir: String;
  SignalDir: String;
  SessionTicket: String;
  TaskName: String;
  TaskUserId: String;
  HelperArgs: String;
begin
  HelperExe := ExpandConstant('{commonappdata}\SRPSS\helper\SRPSS_RedditHelper.exe');
  QueueDir := ExpandConstant('{commonappdata}\SRPSS\url_queue');
  LogDir := ExpandConstant('{commonappdata}\SRPSS\logs');
  SignalDir := ExpandConstant('{commonappdata}\SRPSS\helper_signals');
  SessionTicket := ExpandConstant('{commonappdata}\SRPSS\helper_signals\reddit_helper_session.json');
  TaskName := 'SRPSS_RedditHelper';
  TaskUserId := BuildCurrentUserId();
  TemplatePath := ExpandConstant('{tmp}\reddit_helper_task_template.xml');

  ExtractTemporaryFile('reddit_helper_task_template.xml');

  if not LoadStringFromFile(TemplatePath, TemplateTextAnsi) then
  begin
    MsgBox(
      'SRPSS installed, but the Reddit helper task template could not be loaded.' + #13#10 + #13#10 +
      'Reddit link handoff will not work until this is fixed.',
      mbError,
      MB_OK
    );
    Log('SRPSS: failed to load task template: ' + TemplatePath);
    exit;
  end;
  TemplateText := TemplateTextAnsi;

  HelperArgs := BuildHelperArguments(
    QueueDir,
    LogDir,
    SignalDir,
    SessionTicket,
    20
  );
  RenderedXml := RenderRedditHelperTaskXml(
    TemplateText,
    TaskName,
    TaskUserId,
    HelperExe,
    HelperArgs
  );

  TryDeleteTaskByName(TaskName);
  TryDeleteTaskByName('\SRPSS\RedditHelper');

  Log('SRPSS: registering Reddit helper task via Task Scheduler COM XML import');
  Log('SRPSS: task user id=' + TaskUserId);
  Log('SRPSS: task command=' + HelperExe);
  Log('SRPSS: task args=' + HelperArgs);

  try
    TaskService := CreateOleObject('Schedule.Service');
    TaskService.Connect(Unassigned, Unassigned, Unassigned, Unassigned);
    RootFolder := TaskService.GetFolder('\');
    RegisteredTask := RootFolder.RegisterTask(
      TaskName,
      RenderedXml,
      6,
      Unassigned,
      Unassigned,
      3
    );
    Log(
      'SRPSS: Reddit helper task registered successfully: ' +
      RegisteredTask.Name
    );
    exit;
  except
    Log(
      'SRPSS: Task Scheduler COM XML registration failed for task: ' +
      TaskName
    );
    MsgBox(
      'SRPSS installed, but the Reddit helper scheduled task could not be registered.' + #13#10 + #13#10 +
      'Reddit link handoff will not work until this is fixed.' + #13#10 +
      'Task user: ' + TaskUserId + #13#10 +
      'Task name: ' + TaskName,
      mbError,
      MB_OK
    );
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegisterRedditHelperTask();
end;

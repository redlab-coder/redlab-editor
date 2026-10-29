#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif
[Setup]
AppId={{D75F765B-4424-4C77-B57B-E5B0C574E19D}
AppName=Bottons Editor
AppVersion={#AppVersion}
AppPublisher=RedLab
AppPublisherURL=https://github.com/redlab-coder/redlab-editor
AppSupportURL=https://github.com/redlab-coder/redlab-editor/issues
AppUpdatesURL=https://github.com/redlab-coder/redlab-editor/releases
DefaultDirName={localappdata}\Programs\Bottons Editor
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=..\assets\bottons-editor.ico
UninstallDisplayIcon={app}\BottonsEditor.exe
OutputDir=..\dist
OutputBaseFilename=BottonsEditor-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\BottonsEditor.Installed.Running,Local\Moldura.Installed.Running
SetupMutex=Local\BottonsEditor.Setup.Running
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\BottonsEditor-Portable.exe"; DestDir: "{app}"; DestName: "BottonsEditor.exe"; Flags: ignoreversion
Source: "..\assets\installed.marker"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{app}\Moldura.exe"
Type: files; Name: "{userprograms}\Moldura.lnk"
Type: files; Name: "{userdesktop}\Moldura.lnk"

[Icons]
Name: "{userprograms}\Bottons Editor"; Filename: "{app}\BottonsEditor.exe"
Name: "{userdesktop}\Bottons Editor"; Filename: "{app}\BottonsEditor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BottonsEditor.exe"; Description: "Abrir o Bottons Editor"; Flags: nowait postinstall skipifsilent

Filename: "{app}\BottonsEditor.exe"; Parameters: "{code:RestartEditorParameters}"; Flags: nowait; Check: RestartEditorRequested

[Code]
function RestartEditorParameters(Param: String): String;
begin
  Result := '';
  if ExpandConstant('{param:RESTARTNOBROWSER|0}') = '1' then
    Result := '--no-browser';
end;

function RestartEditorRequested(): Boolean;
begin
  Result := ExpandConstant('{param:RESTARTEDITOR|0}') = '1';
end;

function OpenProcess(Access: LongWord; InheritHandle: Boolean; ProcessId: LongWord): THandle;
external 'OpenProcess@kernel32.dll stdcall';
function WaitForSingleObject(Handle: THandle; Milliseconds: LongWord): LongWord;
external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean;
external 'CloseHandle@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
var
  ProcessId: Integer;
  Handle: THandle;
begin
  Result := True;
  ProcessId := StrToIntDef(ExpandConstant('{param:WAITPID|0}'), 0);
  if ProcessId > 0 then
  begin
    Handle := OpenProcess($00100000, False, ProcessId);
    if Handle <> 0 then
    begin
      Result := WaitForSingleObject(Handle, 120000) = 0;
      CloseHandle(Handle);
      Sleep(1000);
    end;
  end;
end;

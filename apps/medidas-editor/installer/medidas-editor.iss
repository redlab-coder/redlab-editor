#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{5C989A6A-14CF-42F7-B187-3C1BF92EA9AA}
AppName=Medidas Editor
AppVersion={#AppVersion}
AppPublisher=RedLab
AppPublisherURL=https://github.com/redlab-coder/redlab-editor
AppSupportURL=https://github.com/redlab-coder/redlab-editor/issues
AppUpdatesURL=https://github.com/redlab-coder/redlab-editor/releases
DefaultDirName={localappdata}\Programs\Medidas Editor
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=..\assets\medidas-editor.ico
UninstallDisplayIcon={app}\MedidasEditor.exe
OutputDir=..\dist
OutputBaseFilename=MedidasEditor-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\MedidasEditor.Installed.Running
SetupMutex=Local\MedidasEditor.Setup.Running
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\MedidasEditor-Portable.exe"; DestDir: "{app}"; DestName: "MedidasEditor.exe"; Flags: ignoreversion
Source: "..\assets\installed.marker"; DestDir: "{app}"; Flags: ignoreversion

Source: "..\THIRD-PARTY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Medidas Editor"; Filename: "{app}\MedidasEditor.exe"
Name: "{userdesktop}\Medidas Editor"; Filename: "{app}\MedidasEditor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MedidasEditor.exe"; Description: "Abrir o Medidas Editor"; Flags: nowait postinstall skipifsilent

[Code]
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

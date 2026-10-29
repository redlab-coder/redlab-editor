; Offline distributor. Each child owns its files, updater and uninstaller.
#include "build\definitions.iss"

[Setup]
AppId=RedLabEditor.Bundle
AppName=RedLab Editor
AppVersion={#BundleVersion}
AppPublisher=RedLab
AppPublisherURL=https://github.com/redlab-coder/redlab-editor
AppSupportURL=https://github.com/redlab-coder/redlab-editor/issues
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableWelcomePage=no
WizardStyle=modern
WizardSizePercent=115,110
WizardImageFile=assets\welcome.bmp
WizardSmallImageFile=assets\small.bmp
SetupIconFile=assets\redlab-editor.ico
OutputDir=dist
OutputBaseFilename=RedlabEditor-Setup-{#BundleVersion}
Compression=lzma2/fast
SolidCompression=yes
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupMutex=Local\RedLabEditor.Bundle.Setup.Running
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
WelcomeLabel1=RedLab Editor
WelcomeLabel2=Suas ferramentas de impressão, em um só pacote.%n%nInstale Bottons Editor, Polaroid Editor e Medidas Editor. Você também pode escolher apenas os que precisa.%n%nDepois de baixar, a instalação funciona sem internet.
SelectComponentsDesc=Escolha seus editores
FinishedHeadingLabel=RedLab Editor

[Types]
Name: "full"; Description: "Pacote completo"
Name: "custom"; Description: "Escolher editores"; Flags: iscustom

[Tasks]
Name: "desktopicon"; Description: "Criar atalhos na área de trabalho"; Flags: unchecked

[Code]
type
  TProduct = record
    Id, Component, Name, Version, Installer, Hash, Executable, BinaryHash: String;
    RegistryKey, Mutexes, ExistingVersion, Directory, State, Detail: String;
    Selected, PreserveNewer: Boolean;
  end;
var
  Products: array[0..2] of TProduct;
  LogDirectory, Summary: String;
  HasFailures, Installing, RestartNeeded: Boolean;

#include "build\products.iss"

[Code]
function ReadInstalled(Index: Integer; var Version, Directory: String): Boolean;
begin
  Result := RegKeyExists(HKCU64, Products[Index].RegistryKey);
  if Result then
  begin
    RegQueryStringValue(HKCU64, Products[Index].RegistryKey, 'DisplayVersion', Version);
    RegQueryStringValue(HKCU64, Products[Index].RegistryKey, 'InstallLocation', Directory);
  end
  else if RegKeyExists(HKCU32, Products[Index].RegistryKey) then
  begin
    Result := True;
    RegQueryStringValue(HKCU32, Products[Index].RegistryKey, 'DisplayVersion', Version);
    RegQueryStringValue(HKCU32, Products[Index].RegistryKey, 'InstallLocation', Directory);
  end;
end;

procedure SaveResult(Index: Integer);
var
  Filename: String;
begin
  Filename := AddBackslash(LogDirectory) + 'result.ini';
  SetIniString(Products[Index].Id, 'version', Products[Index].Version, Filename);
  SetIniString(Products[Index].Id, 'state', Products[Index].State, Filename);
  SetIniString(Products[Index].Id, 'detail', Products[Index].Detail, Filename);
end;

procedure InitializeWizard;
begin
  LoadProducts;
  WizardForm.ComponentsDiskSpaceLabel.Visible := False;
  WizardForm.WelcomeLabel1.Font.Name := 'Segoe UI';
  LogDirectory := ExpandConstant('{param:LOGDIR|}');
  if LogDirectory = '' then
    LogDirectory := ExpandConstant('{localappdata}\RedLab Editor\Setup\') +
      GetDateTimeString('yyyymmdd-hhnnss', '-', '-') + '-' +
      ExtractFileName(ExpandConstant('{tmp}'));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Index: Integer;
begin
  Result := True;
  if CurPageID = wpSelectComponents then
  begin
    Result := False;
    for Index := 0 to 2 do
      if WizardIsComponentSelected(Products[Index].Component) then Result := True;
    if not Result then
      SuppressibleMsgBox('Selecione pelo menos um editor para continuar.', mbInformation, MB_OK, IDOK);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Index: Integer;
  Existing, Candidate: Int64;
  Root: String;
begin
  Result := '';
  if not ForceDirectories(LogDirectory) then
  begin
    Result := 'Não foi possível criar o registro da instalação. Verifique as permissões do usuário.';
    Exit;
  end;
  { Preflight every selection before changing any editor. }
  for Index := 0 to 2 do
  begin
    Products[Index].Selected := WizardIsComponentSelected(Products[Index].Component);
    Products[Index].PreserveNewer := False;
    Products[Index].ExistingVersion := '';
    Products[Index].Directory := '';
    Products[Index].State := 'not-selected';
    Products[Index].Detail := 'Não selecionado';
    if Products[Index].Selected then
    begin
      if ReadInstalled(Index, Products[Index].ExistingVersion, Products[Index].Directory) then
      begin
        if not StrToVersion(Products[Index].ExistingVersion, Existing) then
        begin
          Result := 'Não foi possível identificar a versão instalada do ' + Products[Index].Name +
            '. Repare a instalação pelo instalador individual antes de continuar.';
          Exit;
        end;
        StrToVersion(Products[Index].Version, Candidate);
        Products[Index].PreserveNewer := ComparePackedVersion(Existing, Candidate) > 0;
        if (Products[Index].Directory = '') and not Products[Index].PreserveNewer then
        begin
          Result := 'Não foi possível identificar a pasta do ' + Products[Index].Name +
            '. Repare a instalação pelo instalador individual antes de continuar.';
          Exit;
        end;
      end;
      if not Products[Index].PreserveNewer then
      begin
        if CheckForMutexes(Products[Index].Mutexes) then
        begin
          Result := 'Salve seu trabalho e encerre o ' + Products[Index].Name + ' antes de instalar o pacote.';
          Exit;
        end;
        if Products[Index].Directory = '' then
        begin
          Root := ExpandConstant('{param:INSTALLROOT|}');
          if Root = '' then Root := ExpandConstant('{localappdata}\Programs');
          Products[Index].Directory := AddBackslash(Root) + Products[Index].Name;
        end;
        try
          ExtractTemporaryFile(Products[Index].Installer);
          if CompareText(GetSHA256OfFile(ExpandConstant('{tmp}\') + Products[Index].Installer), Products[Index].Hash) <> 0 then
            RaiseException('O instalador não corresponde ao SHA-256 aprovado.');
        except
          Result := 'Não foi possível validar o ' + Products[Index].Name + '. Baixe o pacote novamente.';
          Log(GetExceptionMessage);
          Exit;
        end;
      end;
    end;
    SaveResult(Index);
  end;
end;

procedure InstallProduct(Index: Integer);
var
  Parameters, InstalledVersion, InstalledDirectory: String;
  Code: Integer;
begin
  if Products[Index].PreserveNewer then
  begin
    Products[Index].State := 'newer-preserved';
    Products[Index].Detail := 'Versão ' + Products[Index].ExistingVersion + ' preservada (mais recente)';
    Exit;
  end;
  Parameters := '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /TASKS=';
  if WizardIsTaskSelected('desktopicon') then Parameters := Parameters + 'desktopicon';
  Parameters := Parameters + ' /DIR="' + RemoveBackslash(Products[Index].Directory) +
    '" /LOG="' + AddBackslash(LogDirectory) + Products[Index].Id + '.log"';
  if not Exec(ExpandConstant('{tmp}\') + Products[Index].Installer,
      Parameters, '', SW_HIDE, ewWaitUntilTerminated, Code) then
    RaiseException('Não foi possível iniciar o instalador. Código ' + IntToStr(Code) + '.');
  if (Code <> 0) and (Code <> 3010) then
    RaiseException('O instalador retornou o código ' + IntToStr(Code) + '.');
  if Code = 3010 then RestartNeeded := True;
  if not ReadInstalled(Index, InstalledVersion, InstalledDirectory) then
    RaiseException('A instalação não foi registrada.');
  if InstalledVersion <> Products[Index].Version then
    RaiseException('A versão registrada difere da versão do pacote.');
  if CompareText(GetSHA256OfFile(AddBackslash(InstalledDirectory) + Products[Index].Executable),
      Products[Index].BinaryHash) <> 0 then
    RaiseException('O executável instalado difere do executável aprovado.');
  Products[Index].State := 'installed';
  Products[Index].Detail := 'Instalado · ' + Products[Index].Version;
  if Products[Index].ExistingVersion = Products[Index].Version then
  begin
    Products[Index].State := 'repaired';
    Products[Index].Detail := 'Reinstalado · ' + Products[Index].Version;
  end
  else if Products[Index].ExistingVersion <> '' then
  begin
    Products[Index].State := 'updated';
    Products[Index].Detail := 'Atualizado · ' + Products[Index].Version;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Index, Count, Position: Integer;
begin
  if CurStep <> ssPostInstall then Exit;
  Installing := True;
  HasFailures := False;
  Summary := '';
  Count := 0;
  Position := 0;
  for Index := 0 to 2 do if Products[Index].Selected then Count := Count + 1;
  WizardForm.ProgressGauge.Max := Count;
  WizardForm.ProgressGauge.Position := 0;
  for Index := 0 to 2 do
  begin
    if Products[Index].Selected then
    begin
      WizardForm.StatusLabel.Caption := Products[Index].Name;
      try
        InstallProduct(Index);
      except
        HasFailures := True;
        Products[Index].State := 'failed';
        Products[Index].Detail := 'Falha na instalação';
        Log(Products[Index].Name + ': ' + GetExceptionMessage);
      end;
      SaveResult(Index);
      Summary := Summary + Products[Index].Name + ': ' + Products[Index].Detail + #13#10;
      Position := Position + 1;
      WizardForm.ProgressGauge.Position := Position;
    end;
  end;
  Installing := False;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID <> wpFinished then Exit;
  WizardForm.FinishedLabel.AutoSize := False;
  WizardForm.FinishedLabel.Height := WizardForm.InnerPage.ClientHeight - WizardForm.FinishedLabel.Top - ScaleY(12);
  if HasFailures then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Instalação parcial';
    WizardForm.FinishedLabel.Caption := Summary + #13#10 +
      'Os demais editores foram preservados. Você pode tentar novamente ou usar o instalador individual.'
      + #13#10#13#10 + 'Detalhes: ' + LogDirectory;
  end
  else
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Tudo pronto';
    WizardForm.FinishedLabel.Caption := Summary + #13#10 +
      'Abra suas ferramentas pela pasta RedLab Editor no menu Iniciar.' + #13#10 +
      'Cada editor continuará recebendo suas próprias atualizações.';
  end;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if Installing then Cancel := False;
end;

function NeedRestart: Boolean;
begin
  Result := RestartNeeded;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := 0;
  if HasFailures then Result := 1;
end;

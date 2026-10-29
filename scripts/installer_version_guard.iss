{ Run under the individual installer's SetupMutex, closing the race between
  the suite preflight and another installer updating this product. }
[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RegistryKey, InstalledVersion: String;
  Installed, Candidate: Int64;
  RootKey: Integer;
begin
  Result := '';
  RegistryKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
    ExpandConstant('{#SetupSetting("AppId")}') + '_is1';
  RootKey := HKCU64;
  if not RegKeyExists(RootKey, RegistryKey) then RootKey := HKCU32;
  if not RegKeyExists(RootKey, RegistryKey) then Exit;
  if not RegQueryStringValue(RootKey, RegistryKey, 'DisplayVersion', InstalledVersion) or
      not StrToVersion(InstalledVersion, Installed) then
  begin
    Result := 'Não foi possível identificar a versão instalada. Repare a instalação com o instalador atual.';
    Exit;
  end;
  StrToVersion('{#AppVersion}', Candidate);
  if ComparePackedVersion(Installed, Candidate) > 0 then
    Result := 'Uma versão mais recente já está instalada. Este instalador não substituirá essa versão.';
end;

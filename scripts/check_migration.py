"""Build the preserved Moldura and test its real deferred upgrade to Bottons.

Only for an isolated Windows test account without either product installed.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
LEGACY_COMMIT='21dde5bc2322aa14bf07fc257f87ccc462517691'


def main():
    if sys.platform!='win32':raise SystemExit('Esta verificação exige Windows isolado.')
    import winreg
    key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{D75F765B-4424-4C77-B57B-E5B0C574E19D}_is1'
    for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|view):
                raise SystemExit('Teste cancelado: há uma instalação existente de Moldura/Bottons Editor.')
        except FileNotFoundError:pass
    programs=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'
    if any((programs/(name+'.lnk')).exists() for name in ('Moldura','Bottons Editor')) or (programs/'RedLab Editor/Bottons Editor.lnk').exists():
        raise SystemExit('Teste cancelado: há atalhos existentes do usuário.')
    app=ROOT/'apps/bottons-editor';space=ROOT/'artifacts/migration';space.mkdir(parents=True,exist_ok=True)
    legacy=space/'source';legacy.mkdir(exist_ok=True)
    archive=space/'legacy.tar'
    subprocess.run(['git','archive','--format=tar',f'--output={archive}',LEGACY_COMMIT],cwd=ROOT,check=True)
    with tarfile.open(archive) as source:source.extractall(legacy,filter='data')
    env=dict(os.environ,ISCC=str(app/'.tools/inno/ISCC.exe'))
    subprocess.run([sys.executable,'scripts/build_windows.py'],cwd=legacy,env=env,check=True)
    config={};exec((app/'version.py').read_text(encoding='utf-8'),config)
    new_setup=app/'dist'/f'BottonsEditor-Setup-{config["VERSION"]}.exe'
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    with tempfile.TemporaryDirectory(prefix='install-',dir=space) as temporary:
        sandbox=Path(temporary);directory=sandbox/'Aplicativo';local=sandbox/'Local'
        env=dict(os.environ,LOCALAPPDATA=str(local));current=None;state=None;brand='Moldura'
        def start(executable,namespace,updates=False):
            args=[str(directory/executable),'--no-browser']
            if not updates:args.append('--no-updates')
            process=subprocess.Popen(args,env=env,creationflags=flags)
            metadata=local/namespace/'runtime.json';deadline=time.monotonic()+50
            while time.monotonic()<deadline:
                try:
                    value=json.loads(metadata.read_text(encoding='utf-8'))
                    with urllib.request.urlopen(value['url']+'/health',timeout=1) as response:health=json.load(response)
                    if health['instance']==value['instance']:return process,value,health
                except (OSError,ValueError,KeyError):pass
                if process.poll() is not None:raise AssertionError('O aplicativo encerrou antes de iniciar.')
                time.sleep(.1)
            raise AssertionError('O aplicativo não iniciou.')
        def api(path,data):
            with urllib.request.urlopen(state['url']) as response:html=response.read().decode()
            token=re.search('name="(?:moldura|bottons-editor)-token" content="([^"]+)',html).group(1)
            request=urllib.request.Request(state['url']+'/api/'+path,data=json.dumps(data).encode(),headers={f'X-{brand}-Token':token,'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:return response.read()
        try:
            subprocess.run([str(legacy/'dist/Moldura-Setup-1.0.1.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=',f'/DIR={directory}'],check=True,timeout=100,creationflags=flags)
            updates=local/'Moldura/updates';updates.mkdir(parents=True)
            staged=updates/'Moldura-Setup-9999.0.0.exe';staged.write_bytes(new_setup.read_bytes())
            manifest={'version':'9999.0.0','url':'https://github.com/redlab-coder/moldura/releases/download/v9999.0.0/'+staged.name,
                      'sha256':hashlib.sha256(staged.read_bytes()).hexdigest(),'size':staged.stat().st_size}
            (updates/'pending.json').write_text(json.dumps(manifest),encoding='utf-8')
            current,state,health=start('Moldura.exe','Moldura-Installed',updates=True)
            assert health['product']=='Moldura'
            assert not (updates/'install.log').exists(),'A atualização não deve ocorrer durante a edição.'
            api('quit',{});assert current.wait(timeout=30)==0;current=None
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                log=(updates/'install.log').read_text(encoding='utf-8-sig',errors='replace') if (updates/'install.log').exists() else ''
                if 'Installation process succeeded.' in log:break
                time.sleep(.2)
            else:raise AssertionError('Migração não concluiu: '+log[-2000:])
            assert not (directory/'Moldura.exe').exists()
            assert not (programs/'Moldura.lnk').exists()
            assert not (programs/'Bottons Editor.lnk').exists()
            assert (programs/'RedLab Editor/Bottons Editor.lnk').exists()
            brand='BottonsEditor';current,state,health=start('BottonsEditor.exe','BottonsEditor-Installed')
            assert health['product']=='Bottons Editor' and health['version']==config['VERSION']
            assert (directory/'installed.marker').read_text(encoding='utf-8').strip()=='BottonsEditor'
            api('quit',{});assert current.wait(timeout=30)==0;current=None
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as entry:
                assert winreg.QueryValueEx(entry,'DisplayName')[0].startswith('Bottons Editor')
            print(json.dumps({'legacy_deferred_upgrade':'OK','renamed_executable_and_shortcut':'OK','same_install_identity':'OK','new_application_starts':'OK'}))
        finally:
            if current and current.poll() is None:
                api('quit',{});current.wait(timeout=30)
            uninstaller=directory/'unins000.exe'
            if uninstaller.exists():
                subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=90,creationflags=flags)
                deadline=time.monotonic()+30
                while uninstaller.exists() and time.monotonic()<deadline:time.sleep(.1)
                assert not uninstaller.exists(),'O desinstalador ainda está removendo a pasta de teste.'


if __name__=='__main__':main()

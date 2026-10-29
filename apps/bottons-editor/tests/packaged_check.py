"""Exercise the actual portable executable, tray, reuse and browser flows."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
(ROOT/'tests/artifacts').mkdir(parents=True,exist_ok=True)
from version import PORTABLE_NAMESPACE
from desktop import SingleInstance

probe=SingleInstance(PORTABLE_NAMESPACE)
try:
    if not probe.owner:raise SystemExit('Teste cancelado: BottonsEditor portátil já está em execução.')
finally:probe.close()

executable=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'dist/BottonsEditor-Portable.exe').resolve()
flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
with tempfile.TemporaryDirectory(prefix='BottonsEditor-packaged-test-') as temporary:
    env=dict(os.environ,LOCALAPPDATA=str(Path(temporary)/'Local'),BOTTONS_EDITOR_TEST_TRACE=str(ROOT/'tests/artifacts/shutdown.txt'))
    state_path=Path(env['LOCALAPPDATA'])/PORTABLE_NAMESPACE/'runtime.json'
    process=subprocess.Popen([str(executable),'--no-browser','--no-updates'],env=env,creationflags=flags)
    state=None
    try:
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            try:
                state=json.loads(state_path.read_text())
                health=json.load(urllib.request.urlopen(state['url']+'/health',timeout=1))
                if health['instance']==state['instance']:break
            except (OSError,ValueError,KeyError):pass
            if process.poll() is not None:raise AssertionError(f'Executável encerrou com código {process.returncode}')
            time.sleep(.1)
        else:raise AssertionError('Executável não abriu o serviço local')
        second=subprocess.Popen([str(executable),'--no-browser','--no-updates'],env=env,creationflags=flags)
        assert second.wait(timeout=25)==0
        assert json.loads(state_path.read_text())['instance']==state['instance']
        for script in ('browser_check.py','round_browser_check.py','refinement_browser_check.py','sheet_navigation_browser_check.py','header_status_browser_check.py','general_browser_check.py','mixed_browser_check.py'):
            subprocess.run([sys.executable,str(ROOT/'tests'/script),state['url']],check=True)
        print(json.dumps({'portable':'OK','tray_lifecycle':'OK','single_instance':'OK'}))
    finally:
        if state and process.poll() is None:
            html=urllib.request.urlopen(state['url']).read().decode()
            token=re.search('name="bottons-editor-token" content="([^"]+)',html).group(1)
            urllib.request.urlopen(urllib.request.Request(state['url']+'/api/quit',data=b'{}',headers={'X-BottonsEditor-Token':token,'Content-Type':'application/json'})).close()
            try:
                assert process.wait(timeout=25)==0
            except subprocess.TimeoutExpired:
                trace = ROOT/'tests/artifacts/shutdown.txt'
                if trace.exists():
                    print(trace.read_text(encoding='utf-8', errors='replace'))
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                raise
        elif process.poll() is None:
            process.terminate();process.wait(timeout=10)

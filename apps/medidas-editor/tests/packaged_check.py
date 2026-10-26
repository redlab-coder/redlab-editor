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
from browser_check import run
from refinement_browser_check import run as run_refinements
from gallery_browser_check import run as run_gallery

probe=SingleInstance(PORTABLE_NAMESPACE)
try:
    if not probe.owner:raise SystemExit('Teste cancelado: MedidasEditor portátil já está em execução.')
finally:probe.close()

executable=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'dist/MedidasEditor-Portable.exe').resolve()
flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
with tempfile.TemporaryDirectory(prefix='MedidasEditor-packaged-test-') as temporary:
    env=dict(os.environ,LOCALAPPDATA=str(Path(temporary)/'Local'),MEDIDAS_EDITOR_TEST_TRACE=str(ROOT/'tests/artifacts/shutdown.txt'))
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
        run(state['url'])
        run_refinements(state['url'])
        run_gallery(state['url'])
        print(json.dumps({'portable':'OK','tray_lifecycle':'OK','single_instance':'OK'}))
    finally:
        if state and process.poll() is None:
            html=urllib.request.urlopen(state['url']).read().decode()
            token=re.search('name="medidas-editor-token" content="([^"]+)',html).group(1)
            urllib.request.urlopen(urllib.request.Request(state['url']+'/api/quit',data=b'{}',headers={'X-MedidasEditor-Token':token,'Content-Type':'application/json'})).close()
            try:
                assert process.wait(timeout=25)==0
            except subprocess.TimeoutExpired:
                print((ROOT/'tests/artifacts/shutdown.txt').read_text(errors='replace'))
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                raise
        elif process.poll() is None:
            process.terminate();process.wait(timeout=10)

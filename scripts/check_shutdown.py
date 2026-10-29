"""Isolated Windows processes: real tray callback, browser close and busy cache.

Never attaches to or closes the operator's running editors.
"""
import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def worker(product, ready):
    sys.path.insert(0,str(ROOT/'apps'/product))
    import app
    original=app.run_tray
    def tray(*args,**kwargs):
        icon=original(*args,**kwargs)
        def close(wparam,lparam):
            list(icon.menu.items)[2](icon)
        def busy(wparam,lparam):
            def hold():
                with app.CACHE.lock:
                    ready.with_suffix('.busy').write_text('locked')
                    threading.Event().wait()
            threading.Thread(target=hold,daemon=True).start()
        icon._message_handlers[0x8000+77]=close
        icon._message_handlers[0x8000+78]=busy
        def publish():
            deadline=time.monotonic()+15
            while not getattr(icon,'_hwnd',None):
                if time.monotonic()>deadline:return
                time.sleep(.02)
            temporary=ready.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(url=args[0],token=app.TOKEN,hwnd=int(icon._hwnd))),encoding='utf-8')
            temporary.replace(ready)
        threading.Thread(target=publish,daemon=True).start()
        return icon
    app.run_tray=tray
    sys.argv=['app.py','--isolated','--no-browser','--no-updates']
    app.main()


def run(product):
    from playwright.sync_api import sync_playwright
    from ctypes import wintypes
    ctypes.windll.user32.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
    ctypes.windll.user32.PostMessageW.restype=wintypes.BOOL
    cases=[('tray',False),('web',False),('tray',True),('web',True)]
    if product=='medidas-editor':cases += [('tray_export',False),('web_export',False)]
    for route,busy in cases:
        with tempfile.TemporaryDirectory(prefix='RedLab-shutdown-',ignore_cleanup_errors=True) as directory:
            ready=Path(directory)/'ready.json'
            env=dict(os.environ,LOCALAPPDATA=str(Path(directory)/'Local'))
            log=(Path(directory)/'process.log').open('w',encoding='utf-8')
            proc=subprocess.Popen([sys.executable,__file__,'--worker',product,str(ready)],env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                deadline=time.monotonic()+25
                while not ready.exists():
                    if proc.poll() is not None:raise AssertionError('Child exited during startup')
                    if time.monotonic()>deadline:raise AssertionError('Tray startup timed out')
                    time.sleep(.05)
                state=json.loads(ready.read_text(encoding='utf-8'))
                header='X-'+''.join(part.title() for part in product.split('-'))+'-Token'
                def api(path,data):
                    with urllib.request.urlopen(urllib.request.Request(state['url']+'/api/'+path,data=data,headers={header:state['token'],'Content-Type':'application/octet-stream'}),timeout=5) as response:return response.read()
                image=io.BytesIO();Image.new('RGB',(800,600),'#708090').save(image,'PNG')
                if route.startswith('tray'):photo=json.loads(api('upload',image.getvalue()))
                with sync_playwright() as play:
                    browser=play.chromium.launch(channel='msedge',headless=True)
                    page=browser.new_page();errors=[];dialogs=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.on('dialog',lambda dialog:(dialogs.append(dialog.message),dialog.dismiss()))
                    if route.startswith('web'):
                        page.goto(state['url']);page.wait_for_function("!document.querySelector('#add').disabled")
                        page.locator('#files').set_input_files(dict(name='Foto.png',mimeType='image/png',buffer=image.getvalue()))
                        page.wait_for_function("document.querySelector('#count').textContent==='1'&&!document.querySelector('#add').disabled")
                    if route.endswith('_export'):
                        if route.startswith('web'):photo=page.evaluate('({id:current().id})')
                        api('export/start',json.dumps(dict(items=[dict(id=photo['id'],name='Teste.png',settings=dict(width_cm='61',height_cm='250',mode='contain'))])).encode())
                    if busy:
                        ctypes.windll.user32.PostMessageW(state['hwnd'],0x8000+78,0,0)
                        deadline=time.monotonic()+5
                        while not ready.with_suffix('.busy').exists():
                            assert time.monotonic()<deadline
                            time.sleep(.02)
                    started=time.monotonic()
                    if route.startswith('tray'):ctypes.windll.user32.PostMessageW(state['hwnd'],0x8000+77,0,0)
                    else:
                        # Previously this prevented even submitting the exit command.
                        page.evaluate('exporting=true;importing=true')
                        page.locator('#quit').click()
                        page.wait_for_function("document.body.innerText.includes('foi encerrado')")
                    assert proc.wait(timeout=9)==0
                    elapsed=time.monotonic()-started
                    if route.startswith('web'):page.wait_for_timeout(250)
                    assert not errors,errors
                    assert not dialogs,dialogs
                    browser.close()
                # The process and its listening socket must both be gone.
                try:urllib.request.urlopen(state['url']+'/health',timeout=1)
                except OSError:pass
                else:raise AssertionError('Service still alive')
                print(json.dumps(dict(product=product,route=route,busy_cache=busy,seconds=round(elapsed,2),result='OK')),flush=True)
            except Exception:
                log.flush();print((Path(directory)/'process.log').read_text(encoding='utf-8',errors='replace'))
                raise
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
                log.close()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(sys.argv[2],Path(sys.argv[3]))
    else:
        for product in sys.argv[1:] or ('bottons-editor','polaroid-editor','medidas-editor'):run(product)

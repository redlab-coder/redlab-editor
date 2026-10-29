"""Local HTTP/browser integration; fixture bytes are never executed."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from unittest.mock import Mock,patch
from playwright.sync_api import sync_playwright
from update_test_helpers import prepare,state

ROOT=Path(__file__).resolve().parents[1]
product=sys.argv[1]
sys.path.insert(0,str(ROOT/'apps'/product))
import app
from recovery import UpdateSession,CheckpointStore
from projects import write_project,read_project
from photo_store import PhotoRecord


def server(store,updater):
    service=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);service.daemon_threads=True
    service.updater=updater;service.update_session=UpdateSession(updater,store);service.request_shutdown=Mock()
    thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
    return service

with tempfile.TemporaryDirectory(prefix='RedLab-update-flow-') as temporary:
    store=CheckpointStore(Path(temporary)/'recovery',write_project,read_project,PhotoRecord)
    updater=Mock(lock=threading.Lock(),pending=dict(version='9999.0.0'),valid_download=Mock(return_value=True),stopped=threading.Event())
    updater.snapshot.return_value=dict(state='ready',version='9999.0.0');updater.restart_requested=False
    old=server(store,updater);fresh=None
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            url=f'http://127.0.0.1:{old.server_port}';page.goto(url);files=prepare(page,product);expected=state(page,product)
            other=context.new_page();other.goto(url);other.wait_for_function('!bootRecovery&&!restoring')
            assert other.locator('#update-status').is_disabled();other.close()
            # Disk errors do not close or mutate the loaded session.
            with patch.object(store,'writer',side_effect=OSError('simulated disk failure')):
                page.locator('#update-status').click()
                page.wait_for_function("!updateApplying&&document.querySelector('#toast').textContent.includes('cópia do lote')")
                assert state(page,product)==expected;old.request_shutdown.assert_not_called()
            # A ready update can be queued while an export is active.
            page.evaluate('exporting=true');page.locator('#update-status').click()
            page.wait_for_function("document.querySelector('#update-label').textContent==='Aguardando operação…'")
            assert not store.marker.exists();page.evaluate('exporting=false')
            page.wait_for_function('closed',timeout=15000)
            assert updater.restart_requested and store.marker.exists()
            deadline=time.monotonic()+2
            while not old.request_shutdown.called and time.monotonic()<deadline:time.sleep(.01)
            old.request_shutdown.assert_called_once()
            old.shutdown();old.server_close();app.IMAGES.clear();app.CACHE.clear()
            fresh=server(store,None)
            page.add_init_script("window.blockCheckpointStorage=sessionStorage.getItem('allow-recovery-storage')!=='1';const save=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(window.blockCheckpointStorage&&key.endsWith('-session'))throw new DOMException('simulated quota','QuotaExceededError');return save.call(this,key,value);};")
            page.goto(f'http://127.0.0.1:{fresh.server_port}')
            page.wait_for_function('!bootRecovery&&!restoring&&photos.length===2')
            actual=state(page,product);assert actual==expected,(expected,actual)
            page.wait_for_function("document.querySelector('#toast').textContent.includes('cópia de segurança foi mantida')")
            assert store.marker.exists(),'Failed browser storage must retain the disk checkpoint'
            # A fresh document retries the recovery; allow browser storage on the retry.
            page.evaluate("sessionStorage.setItem('allow-recovery-storage','1')");page.reload()
            page.wait_for_function('!bootRecovery&&!restoring&&photos.length===2')
            actual=state(page,product);assert actual==expected,(expected,actual)
            deadline=time.monotonic()+10
            while store.marker.exists() and time.monotonic()<deadline:time.sleep(.05)
            assert not store.marker.exists()
            assert not errors,errors
            browser.close()
        print(json.dumps(dict(product=product,disk_failure_keeps_session='OK',owner_only='OK',queued_update='OK',browser_storage_failure_preserves_checkpoint='OK',new_session_restored='OK',errors=errors)),flush=True)
    finally:
        if fresh:fresh.shutdown();fresh.server_close()
        else:old.shutdown();old.server_close()
        app.IMAGES.clear();app.CACHE.clear()

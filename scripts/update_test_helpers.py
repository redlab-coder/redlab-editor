"""Synthetic state shared by source and genuine Windows installer update checks."""
import ctypes
from ctypes import wintypes
import io
import json
from pathlib import Path
import subprocess
import time
from PIL import Image


def prepare(page,product):
    page.wait_for_function('editingAllowed&&!bootRecovery&&!restoring')
    files=[]
    for index,color in enumerate(('red','blue')):
        data=io.BytesIO();Image.new('RGB',(300,400),color).save(data,'PNG')
        files.append(dict(name=f'Retomar-{index}.png',mimeType='image/png',buffer=data.getvalue()))
    page.locator('#files').set_input_files(files)
    page.wait_for_function('photos.length===2&&!importing')
    if product=='bottons-editor':
        page.evaluate("()=>{photos[0].template='round_p';photos[0].edits.zoom=1.25;photos[0].edits.brightness=1.1;selected=photos[1].id;activeTemplate='round_m';$('guides').setAttribute('aria-pressed','false');renderLibrary();}")
    elif product=='polaroid-editor':
        page.evaluate("()=>{photos[0].edits.zoom=1.25;photos[0].edits.mode='cover';photos[0].manual=true;photos[0].reviewed=true;selected=photos[1].id;filterReview=true;renderLibrary();}")
    else:
        page.evaluate("()=>{Object.assign(photos[0].settings,{width_cm:'30',height_cm:'36',mode:'cover',zoom:1.25});photos[0].reviewed=true;selected=photos[1].id;checked=new Set([photos[0].id]);renderSettings();$('width-cm').value='30,8';$('height-cm').value='';draftDirty=true;renderLibrary();}")
    page.evaluate('saveSession()')
    return files


def state(page,product):
    expression="({photos:photos.map(p=>({name:p.name,template:p.template,edits:p.edits,settings:p.settings,reviewed:p.reviewed,manual:p.manual})),selected_index:photos.findIndex(p=>p.id===selected)})"
    result=page.evaluate(expression)
    # Serialization fills optional defaults; compare fields that carry operator intent.
    for photo in result['photos']:
        if product=='polaroid-editor':photo['manual']=bool(photo.get('manual'));photo['reviewed']=bool(photo.get('reviewed'))
    if product=='bottons-editor':result.update(page.evaluate("({template:activeTemplate,guides:$('guides').getAttribute('aria-pressed')==='true'})"))
    elif product=='polaroid-editor':result.update(page.evaluate('({filter_review:filterReview})'))
    else:result.update(page.evaluate("({filter_review:filterReview,draft_width:$('width-cm').value,draft_height:$('height-cm').value,draft_dirty:draftDirty,checked:photos.map((p,i)=>checked.has(p.id)?i:-1).filter(i=>i>=0)})"))
    return result


class AttachedProcess:
    def __init__(self,pid):
        self.pid=pid;self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);self.kernel.OpenProcess.restype=wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD);self.kernel.WaitForSingleObject.restype=wintypes.DWORD
        self.kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
        self.handle=self.kernel.OpenProcess(0x100000,False,pid)
    def poll(self):return None if self.handle and self.kernel.WaitForSingleObject(self.handle,0)==258 else 0
    def wait(self,timeout=20):
        if self.handle and self.kernel.WaitForSingleObject(self.handle,int(timeout*1000))==258:raise subprocess.TimeoutExpired('restarted editor',timeout)
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
        return 0


def installed_restart(product,current,old_state,metadata,updates,staged,api):
    """Called only by the account-isolated installer check, using its own setup."""
    from playwright.sync_api import sync_playwright
    restarted=None;new_state=None
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(old_state['url']);prepare(page,product);expected=state(page,product)
            page.wait_for_function("!document.querySelector('#update-status').hidden&&!document.querySelector('#update-status').disabled")
            page.locator('#update-status').click();assert current.wait(timeout=25)==0
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                try:
                    candidate=json.loads(metadata.read_text(encoding='utf-8'))
                    if candidate['instance']!=old_state['instance']:
                        api(candidate,'heartbeat',{});new_state=candidate;break
                except (OSError,ValueError,KeyError):pass
                time.sleep(.1)
            else:raise AssertionError('The genuine installer did not restart the editor')
            restarted=AttachedProcess(new_state['pid'])
            assert (updates/'recovery'/'current.json').exists(),'Checkpoint must survive until the UI confirms recovery'
            # The fixture advertises a future version but installs the current test binary.
            # Remove that fixture before exiting again to avoid a second test installation.
            (updates/'pending.json').unlink(missing_ok=True);staged.unlink(missing_ok=True)
            page.goto(new_state['url']);page.wait_for_function('!bootRecovery&&!restoring&&photos.length===2',timeout=60000)
            actual=state(page,product);assert actual==expected,(expected,actual)
            deadline=time.monotonic()+10
            while (updates/'recovery'/'current.json').exists() and time.monotonic()<deadline:time.sleep(.05)
            assert not (updates/'recovery'/'current.json').exists(),'Recovery was not acknowledged'
            assert not errors,errors
            browser.close()
        print(json.dumps(dict(verified_update_restart='OK',checkpoint_restore='OK',product=product)),flush=True)
        return restarted,new_state
    except Exception:
        if new_state:
            try:api(new_state,'quit',{})
            except OSError:pass
            if restarted:restarted.wait(timeout=25)
        raise

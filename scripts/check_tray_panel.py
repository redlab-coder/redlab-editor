"""Exercise only a disposable tray instance; never finds the operator's apps."""
import argparse
import json
import os
import queue
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]


def worker(product,directory,preview=False):
    directory=Path(directory);sys.path.insert(0,str(ROOT/'apps'/product))
    import tray_panel,desktop
    geometry=tray_panel.monitor_geometry
    stopped=threading.Event();events=[];layout_scale=None;commands=queue.SimpleQueue()
    def read_commands():
        for line in sys.stdin:
            try:commands.put(json.loads(line))
            except ValueError:pass
    threading.Thread(target=read_commands,daemon=True).start()
    class TestPanel(tray_panel.TrayPanel):
        def _build(self,scale):
            super()._build(scale)
            if preview:
                def capture():
                    # Test-owned foreground window only, never a desktop-wide capture.
                    from PIL import ImageGrab
                    import ctypes
                    from ctypes import wintypes
                    user=ctypes.WinDLL('user32');user.GetAncestor.argtypes=(wintypes.HWND,wintypes.UINT);user.GetAncestor.restype=wintypes.HWND
                    user.GetForegroundWindow.restype=wintypes.HWND
                    if user.GetForegroundWindow()==user.GetAncestor(self.root.winfo_id(),2):
                        x,y=self.root.winfo_rootx(),self.root.winfo_rooty()
                        ImageGrab.grab(bbox=(x,y,x+self.root.winfo_width(),y+self.root.winfo_height()),all_screens=True).save(directory/'panel.png')
                    stopped.set()
                self.root.after(500,capture)
        def _tick(self):
            nonlocal layout_scale
            if not commands.empty():
                data=commands.get_nowait()
                action=data['action']
                if action=='scale':layout_scale=data['scale'];self.commands.put('show')
                elif action=='escape':self.root.event_generate('<Escape>')
                elif action=='tab':self.root.event_generate('<Tab>')
                elif action=='open':self.buttons[0].invoke()
                elif action=='quit':self.buttons[1].invoke()
            if self.root and self.buttons:
                focus=self.root.focus_get()
                data=dict(visible=self.root.state()!='withdrawn',scale=self.scale,events=list(events),
                    bounds=[self.root.winfo_rootx(),self.root.winfo_rooty(),self.root.winfo_width(),self.root.winfo_height()],
                    buttons=[dict(text=b.cget('text'),x=b.winfo_rootx(),y=b.winfo_rooty(),width=b.winfo_width(),height=b.winfo_height(),requested=b.winfo_reqwidth(),focused=b==focus) for b in self.buttons])
                print(json.dumps(dict(kind='state',**data)),flush=True)
            super()._tick()
    tray_panel.TrayPanel=TestPanel
    def monitor(point):
        work,scale=geometry(point);return work,layout_scale or scale
    tray_panel.monitor_geometry=monitor
    desktop.webbrowser.open=lambda url:events.append('opened')
    def shutdown():events.append('quit');stopped.set()
    icon=desktop.run_tray('http://127.0.0.1:1',shutdown,lambda:True)
    icon.run_detached()
    deadline=time.monotonic()+10
    while not icon._hwnd:
        if time.monotonic()>deadline:raise RuntimeError('Tray startup timed out')
        time.sleep(.02)
    print(json.dumps(dict(kind='ready',hwnd=int(icon._hwnd),title=desktop.THEME['name']+' · RedLab Editor')),flush=True)
    if preview:icon.panel.show()
    while not stopped.wait(.05):
        if (directory/'stop').exists():break
    icon.stop()
    if icon.panel.thread:
        icon.panel.thread.join(timeout=3);assert not icon.panel.thread.is_alive(),'Panel thread did not exit'
    assert icon.panel.root is None


def check(product):
    import ctypes
    from ctypes import wintypes
    user=ctypes.WinDLL('user32');user.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
    with tempfile.TemporaryDirectory(prefix='RedLab-tray-check-') as temporary:
        directory=Path(temporary);log=(directory/'process.log').open('w',encoding='utf-8')
        process=subprocess.Popen([sys.executable,__file__,'--worker',product,str(directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',env=dict(os.environ,PYTHONIOENCODING='utf-8'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        latest={}
        def receive():
            for line in process.stdout:
                try:
                    state=json.loads(line);latest[state['kind']]=state
                except (ValueError,KeyError):pass
        receiver=threading.Thread(target=receive,daemon=True);receiver.start()
        def wait(predicate,file='state.json',timeout=12):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                if process.poll() is not None:raise AssertionError('Worker exited: '+(directory/'process.log').read_text(encoding='utf-8',errors='replace'))
                try:
                    state=latest.get(file.split('.')[0])
                    if state and predicate(state):return state
                except (OSError,ValueError):pass
                time.sleep(.03)
            raise AssertionError('Tray panel state timed out: '+(directory/'process.log').read_text(encoding='utf-8',errors='replace'))
        def command(action,**data):
            process.stdin.write(json.dumps(dict(action=action,**data))+'\n');process.stdin.flush()
        try:
            ready=wait(lambda state:True,'ready.json')
            # Genuine pystray notification message and Windows callback.
            from pystray._util import win32
            user.PostMessageW(ready['hwnd'],win32.WM_NOTIFY,0,win32.WM_RBUTTONUP)
            first=wait(lambda state:state['visible'])
            assert [b['text'] for b in first['buttons']]==['Abrir editor','Encerrar editor']
            command('tab');wait(lambda state:state['buttons'][1]['focused'])
            for scale in (1,1.25,1.5,2,2.5):
                command('scale',scale=scale);state=wait(lambda state:state['visible'] and state['scale']==scale)
                x,y,width,height=state['bounds']
                for button in state['buttons']:
                    assert x<=button['x'] and button['x']+button['width']<=x+width
                    assert y<=button['y'] and button['y']+button['height']<=y+height
                    assert button['width']>=button['requested'],(product,scale,button)
                command('escape');wait(lambda state:not state['visible'])
            user.PostMessageW(ready['hwnd'],win32.WM_NOTIFY,0,win32.WM_RBUTTONUP)
            wait(lambda state:state['visible']);command('open');wait(lambda state:not state['visible'] and state['events']==['opened'])
            user.PostMessageW(ready['hwnd'],win32.WM_NOTIFY,0,win32.WM_RBUTTONUP)
            wait(lambda state:state['visible']);command('quit');assert process.wait(timeout=8)==0
            log.close();assert 'Traceback' not in (directory/'process.log').read_text(encoding='utf-8',errors='replace')
            print(json.dumps(dict(product=product,native_panel='OK',keyboard='Tab/Escape',scales=[100,125,150,200,250],open_and_direct_exit='OK')),flush=True)
        finally:
            (directory/'stop').touch()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            log.close()


if __name__=='__main__':
    if sys.argv[1:2] in (['--worker'],['--preview']):worker(sys.argv[2],sys.argv[3],sys.argv[1]=='--preview')
    else:
        for product in sys.argv[1:] or ['bottons-editor','polaroid-editor','medidas-editor']:check(product)

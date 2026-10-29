"""Small on-demand tray panel; every Tk operation stays on its owning thread."""
import ctypes
from ctypes import wintypes
import gc
import logging
import os
import queue
import threading

LOG=logging.getLogger(__name__)


def popup_position(point,size,work,padding=10):
    left,top,right,bottom=work;width,height=size;x,y=point
    return (max(left+padding,min(x-width,right-width-padding)),
            max(top+padding,min(y-height,bottom-height-padding)))


def monitor_geometry(point):
    class MonitorInfo(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.MonitorFromPoint.argtypes=(wintypes.POINT,wintypes.DWORD);user.MonitorFromPoint.restype=wintypes.HANDLE
    user.GetMonitorInfoW.argtypes=(wintypes.HANDLE,ctypes.POINTER(MonitorInfo))
    monitor=user.MonitorFromPoint(wintypes.POINT(*point),2)
    info=MonitorInfo();info.size=ctypes.sizeof(info)
    if not user.GetMonitorInfoW(monitor,ctypes.byref(info)):raise ctypes.WinError(ctypes.get_last_error())
    scale=1.0
    try:
        shcore=ctypes.WinDLL('shcore');shcore.GetDpiForMonitor.argtypes=(wintypes.HANDLE,ctypes.c_int,ctypes.POINTER(wintypes.UINT),ctypes.POINTER(wintypes.UINT))
        x=wintypes.UINT();y=wintypes.UINT()
        if shcore.GetDpiForMonitor(monitor,0,ctypes.byref(x),ctypes.byref(y))==0:scale=max(1,x.value/96)
    except (OSError,AttributeError):pass
    area=info.work
    return (area.left,area.top,area.right,area.bottom),scale


class TrayPanel:
    def __init__(self,theme,image,version,on_open,on_quit):
        self.theme=theme;self.image=image;self.version=version;self.on_open=on_open;self.on_quit=on_quit
        self.commands=queue.SimpleQueue();self.stopped=threading.Event();self.ready=threading.Event()
        self.thread=None;self.lock=threading.Lock();self.failed=False;self.root=None;self.images=[];self.buttons=[]
        self.scale=None

    def show(self):
        if self.failed:raise RuntimeError('Painel indisponível')
        with self.lock:
            if self.stopped.is_set():return
            if self.thread is None:
                self.thread=threading.Thread(target=self._run,name='RedLab-tray-panel',daemon=True);self.thread.start()
        self.commands.put('show')

    def stop(self):
        self.stopped.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=1)

    def _run(self):
        root=None
        try:
            # Tk and its images are created and destroyed on this thread only.
            if os.name=='nt':
                try:
                    user=ctypes.WinDLL('user32');user.SetThreadDpiAwarenessContext.argtypes=(ctypes.c_void_p,);user.SetThreadDpiAwarenessContext.restype=ctypes.c_void_p
                    user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
                except (OSError,AttributeError):pass
            import tkinter as tk
            if self.stopped.is_set():return
            root=tk.Tk(className='RedLabEditorPanel');self.root=root;root.withdraw()
            root.title(self.theme['name']+' · RedLab Editor');root.overrideredirect(True);root.attributes('-topmost',True)
            root.configure(background=self.theme['line']);root.bind('<Escape>',lambda event:root.withdraw())
            root.bind('<FocusOut>',lambda event:root.after(100,self._dismiss_unfocused))
            root.after(30,self._tick);self.ready.set();root.mainloop()
        except Exception:
            self.failed=True;self.ready.set();LOG.exception('Não foi possível abrir o painel da bandeja')
        finally:
            self.images.clear();self.buttons.clear()
            if root:
                try:root.destroy()
                except Exception:pass
            self.root=None;root=None;gc.collect()

    def _dismiss_unfocused(self):
        if self.root and self.root.state()!='withdrawn' and self.root.focus_displayof() is None:self.root.withdraw()

    def _tick(self):
        if self.stopped.is_set():self.root.quit();return
        show=False
        while not self.commands.empty():
            if self.commands.get_nowait()=='show':show=True
        if show:
            try:self._show()
            except Exception:
                self.failed=True;LOG.exception('Painel indisponível; menu de compatibilidade preservado');self.root.quit();return
        self.root.after(40,self._tick)

    def _choose(self,callback):
        self.root.withdraw()
        threading.Thread(target=callback,daemon=True,name='RedLab-tray-action').start()

    def _build(self,scale):
        import tkinter as tk
        from PIL import ImageTk,Image,ImageDraw
        from branding import icon_image
        root=self.root;t=self.theme;px=lambda value:round(value*scale)
        for child in root.winfo_children():child.destroy()
        self.images.clear();self.buttons.clear();self.scale=scale
        body=tk.Frame(root,bg=t['header'],padx=px(20),pady=px(18));body.pack(fill='both',expand=True,padx=1,pady=1)
        head=tk.Frame(body,bg=t['header']);head.pack(fill='x')
        image=ImageTk.PhotoImage(icon_image(px(42)),master=root);self.images.append(image)
        tk.Label(head,image=image,bg=t['header'],borderwidth=0).pack(side='left',padx=(0,px(12)))
        copy=tk.Frame(head,bg=t['header']);copy.pack(side='left',fill='x',expand=True)
        tk.Label(copy,text='REDLAB EDITOR',font=('Segoe UI',-px(10),'bold'),fg=t['muted'],bg=t['header'],anchor='w').pack(fill='x')
        tk.Label(copy,text=t['name'],font=('Segoe UI',-px(18),'bold'),fg=t['ink'],bg=t['header'],anchor='w').pack(fill='x')
        status=tk.Frame(body,bg=t['header']);status.pack(fill='x',pady=(px(16),px(16)))
        tk.Label(status,text='●  Em execução',font=('Segoe UI',-px(11)),fg=t['accent'],bg=t['header']).pack(side='left')
        tk.Label(status,text='v'+self.version,font=('Segoe UI',-px(11)),fg=t['muted'],bg=t['header']).pack(side='right')
        for text,callback,primary in (('Abrir editor',self.on_open,True),('Encerrar editor',self.on_quit,False)):
            color=t['accent'] if primary else t['soft'];hover=t['accent-hover'] if primary else t['line']
            pictures=[]
            for fill in (color,hover):
                width=px(300)-2-2*px(20)-2*px(2);height=px(40)
                art=Image.new('RGB',(width*3,height*3),t['header'])
                ImageDraw.Draw(art).rounded_rectangle((0,0,width*3-1,height*3-1),radius=px(9)*3,fill=fill)
                pictures.append(ImageTk.PhotoImage(art.resize((width,height),Image.Resampling.LANCZOS),master=root))
            self.images.extend(pictures)
            button=tk.Button(body,image=pictures[0],compound='center',text=text,command=lambda cb=callback:self._choose(cb),font=('Segoe UI',-px(13),'bold' if primary else 'normal'),
                bg=t['header'],fg='white' if primary else t['ink'],activebackground=t['header'],activeforeground='white' if primary else t['ink'],
                relief='flat',borderwidth=0,highlightthickness=px(2),highlightbackground=t['header'],highlightcolor=t['focus'],
                cursor='hand2',takefocus=True,padx=0,pady=0)
            button.pack(fill='x',pady=(0,px(5)))
            button.bind('<Enter>',lambda event,b=button,p=pictures[1]:b.configure(image=p))
            button.bind('<Leave>',lambda event,b=button,p=pictures[0]:b.configure(image=p))
            button.bind('<Return>',lambda event,b=button:b.invoke());self.buttons.append(button)

    def _show(self):
        root=self.root
        point=root.winfo_pointerxy();work,scale=monitor_geometry(point)
        if self.scale!=scale:self._build(scale)
        root.update_idletasks();width=max(round(300*scale),root.winfo_reqwidth());height=root.winfo_reqheight()
        # A popup must stay entirely within the monitor, including small work areas.
        width=min(width,work[2]-work[0]-20);height=min(height,work[3]-work[1]-20)
        x,y=popup_position(point,(width,height),work)
        root.geometry(f'{width}x{height}+0+0');root.deiconify();root.update_idletasks()
        user=ctypes.WinDLL('user32');user.GetAncestor.argtypes=(wintypes.HWND,wintypes.UINT);user.GetAncestor.restype=wintypes.HWND
        hwnd=user.GetAncestor(root.winfo_id(),2)
        user.SetWindowPos.argtypes=(wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT)
        user.SetWindowPos(hwnd,None,x,y,width,height,0x14)
        try:
            preference=ctypes.c_int(2);dwm=ctypes.WinDLL('dwmapi');dwm.DwmSetWindowAttribute.argtypes=(wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD)
            dwm.DwmSetWindowAttribute(hwnd,33,ctypes.byref(preference),ctypes.sizeof(preference))
        except (OSError,AttributeError):pass
        root.lift();root.focus_force();self.buttons[0].focus_set()


def create_tray(name,image,title,menu,theme,version,on_open,on_quit):
    import pystray
    if os.name!='nt':return pystray.Icon(name,image,title,menu=menu)
    from pystray._util import win32
    class FamilyIcon(pystray.Icon):
        def _on_notify(self,wparam,lparam):
            if lparam==win32.WM_RBUTTONUP:
                try:self.panel.show();return
                except Exception:LOG.exception('Usando o menu de compatibilidade')
            super()._on_notify(wparam,lparam)
        def _on_stop(self,wparam,lparam):
            self.panel.stop();super()._on_stop(wparam,lparam)
    icon=FamilyIcon(name,image,title,menu=menu)
    icon.panel=TrayPanel(theme,image,version,on_open,on_quit)
    return icon

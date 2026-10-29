"""Open only the tray belonging to the PID of the disposable packaged test."""
import ctypes
from ctypes import wintypes
import time


def check(pid,product):
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=(callback_type,wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
    user.GetClassNameW.argtypes=(wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    user.GetWindowTextW.argtypes=(wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    user.IsWindowVisible.argtypes=(wintypes.HWND,);user.IsWindowVisible.restype=wintypes.BOOL
    user.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
    user.GetWindowRect.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.RECT))
    def windows():
        result=[]
        @callback_type
        def collect(hwnd,lparam):
            actual=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(actual))
            if actual.value==pid:
                name=ctypes.create_unicode_buffer(256);title=ctypes.create_unicode_buffer(256)
                user.GetClassNameW(hwnd,name,256);user.GetWindowTextW(hwnd,title,256)
                result.append((hwnd,name.value,title.value,bool(user.IsWindowVisible(hwnd))))
            return True
        user.EnumWindows(collect,0);return result
    deadline=time.monotonic()+10;tray=None
    while time.monotonic()<deadline:
        candidates=[item for item in windows() if item[1].endswith('SystemTrayIcon')]
        if candidates:tray=[item[0] for item in candidates];break
        time.sleep(.05)
    assert tray,'The packaged test PID has no tray window'
    from pystray._util import win32
    for hwnd in tray:user.PostMessageW(hwnd,win32.WM_NOTIFY,0,win32.WM_RBUTTONUP)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        candidates=[item for item in windows() if item[3] and 'RedLab Editor' in item[2]]
        if candidates:
            bounds=wintypes.RECT();assert user.GetWindowRect(candidates[0][0],ctypes.byref(bounds))
            assert bounds.right-bounds.left>=300 and bounds.bottom-bounds.top>=200
            print({'product':product,'packaged_native_panel':'OK','bundled_tk':'OK'},flush=True)
            return
        time.sleep(.05)
    raise AssertionError('The bundled native panel did not open: '+repr(windows()))

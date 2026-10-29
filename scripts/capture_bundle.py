"""Capture only the installer created by this test, before installing anything.

Runs solely on a disposable CI Windows desktop. No other window is controlled.
"""
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import tempfile
import time
from PIL import ImageGrab

from bundle import BUNDLE, package


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('Capture somente no runner Windows isolado.')
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback_type, w.LPARAM]
    user.EnumChildWindows.argtypes = [w.HWND, callback_type, w.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    user.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [w.HWND]
    user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user.SendMessageW.restype = w.LPARAM
    user.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
    user.SetForegroundWindow.argtypes = [w.HWND]
    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ProcessID', w.DWORD),
            ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', w.DWORD),
            ('cntThreads', w.DWORD), ('th32ParentProcessID', w.DWORD),
            ('pcPriClassBase', w.LONG), ('dwFlags', w.DWORD), ('szExeFile', w.WCHAR*260)]
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    def descendants(pid):
        handle = kernel.CreateToolhelp32Snapshot(2, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise OSError('Snapshot de processos falhou')
        entries = []
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            more = kernel.Process32FirstW(handle, ctypes.byref(entry))
            while more:
                entries.append((entry.th32ProcessID, entry.th32ParentProcessID))
                more = kernel.Process32NextW(handle, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(handle)
        owned = {pid}
        for _ in range(8):
            previous = len(owned)
            owned.update(child for child, parent in entries if parent in owned)
            if len(owned) == previous:
                break
        return owned
    def text(hwnd):
        value = ctypes.create_unicode_buffer(4096)
        user.GetWindowTextW(hwnd, value, len(value))
        return value.value.replace('&', '')
    def children(hwnd):
        result = []
        @callback_type
        def callback(child, _):
            if user.IsWindowVisible(child):
                result.append((child, text(child)))
            return True
        user.EnumChildWindows(hwnd, callback, 0)
        return result
    destination = BUNDLE/'build/screenshots'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='RedLab-installer-preview-') as temporary:
        setup = BUNDLE/'dist'/f'RedlabEditor-Setup-{package()["version"]}.exe'
        process = subprocess.Popen([str(setup), '/SP-', f'/LOGDIR={temporary}'])
        hwnd = None
        try:
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                found = []
                owned = descendants(process.pid)
                @callback_type
                def find(window, _):
                    pid = w.DWORD()
                    user.GetWindowThreadProcessId(window, ctypes.byref(pid))
                    if pid.value in owned and user.IsWindowVisible(window) and 'RedLab Editor' in text(window):
                        found.append(window)
                    return True
                user.EnumWindows(find, 0)
                if found:
                    hwnd = found[0]
                    break
                time.sleep(.15)
            assert hwnd, 'O instalador não mostrou sua janela'
            user.SetWindowPos(hwnd, 0, 80, 60, 0, 0, 1)
            user.SetForegroundWindow(hwnd)
            time.sleep(.5)
            ImageGrab.grab(window=hwnd).save(destination/'welcome.png')
            buttons = [child for child, label in children(hwnd) if label.startswith('Avançar')]
            assert len(buttons) == 1
            user.PostMessageW(buttons[0], 0xF5, 0, 0)
            time.sleep(.5)
            labels = '\n'.join(label for _, label in children(hwnd))
            assert 'Escolha seus editores' in labels, labels
            ImageGrab.grab(window=hwnd).save(destination/'components.png')
            # Resize the test-owned installer and verify the native layout still fits.
            user.SetWindowPos(hwnd, 0, 80, 60, 900, 650, 0)
            time.sleep(.3)
            ImageGrab.grab(window=hwnd).save(destination/'components-wide.png')
            print('Installer UI: welcome, components and resize OK.')
        finally:
            # End only the test-owned preview process tree; no installation started.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=False)
            process.wait(timeout=15)


if __name__ == '__main__':
    main()

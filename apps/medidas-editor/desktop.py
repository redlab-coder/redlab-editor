"""Windows tray lifecycle and per-user single instance."""
import ctypes
import hashlib
import json
import os
import time
import urllib.request
import webbrowser
from pathlib import Path
from branding import icon_image, THEME
from tray_panel import create_tray
from version import VERSION




class SingleInstance:
    def __init__(self, namespace='MedidasEditor', mutex_name=None):
        self.handle = None
        self.owner = False
        root = Path(os.environ.get('LOCALAPPDATA', Path.home())) / namespace
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / 'runtime.json'
        if os.name == 'nt':
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
            kernel.CreateMutexW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel.CloseHandle.restype = ctypes.c_int
            self.kernel = kernel
            name = mutex_name or 'Local\\' + namespace + '-' + hashlib.sha256(str(Path.home()).encode()).hexdigest()[:20]
            ctypes.set_last_error(0)
            self.handle = kernel.CreateMutexW(None, False, name)
            if not self.handle:
                raise OSError(ctypes.get_last_error(), 'Não foi possível iniciar o Medidas Editor.')
            self.owner = ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
        else:
            self.owner = True

    def publish(self, url, instance):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'url': url, 'instance': instance, 'pid': os.getpid()}), encoding='utf-8')
        temporary.replace(self.path)

    def existing_url(self, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                state = json.loads(self.path.read_text(encoding='utf-8'))
                url = state['url']
                # Only contact a genuine loopback URL, even if stale metadata was changed.
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port or parsed.path:
                    raise ValueError('URL inválida')
                with urllib.request.urlopen(url + '/health', timeout=1) as response:
                    health = json.load(response)
                if health.get('product') == 'Medidas Editor' and health.get('instance') == state['instance']:
                    return url
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(.15)
        return None

    def close(self):
        if self.owner:
            try:
                state = json.loads(self.path.read_text(encoding='utf-8'))
                if state.get('pid') == os.getpid():
                    self.path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def clear_session(images, lock, cache, timeout=1):
    """Do not wait indefinitely for an in-flight daemon image operation.

    Busy buffers remain owned by their worker and are reclaimed on process exit.
    Never close a Pillow image while another thread is using it.
    """
    if lock.acquire(timeout=timeout):
        try:
            images.clear()
        finally:
            lock.release()
    if cache.lock.acquire(timeout=timeout):
        try:
            cache.clear()
        finally:
            cache.lock.release()


def run_tray(url, request_shutdown, has_photos, updater=None):
    import pystray
    def open_app(icon, item):
        webbrowser.open(url)
    def quit_app(icon, item):
        request_shutdown()
    items = [
        pystray.MenuItem('Abrir Medidas Editor', open_app, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Encerrar Medidas Editor', quit_app),
    ]
    icon = create_tray('MedidasEditor', icon_image(256), f'Medidas Editor {VERSION} · RedLab Editor', pystray.Menu(*items), THEME, VERSION, lambda:open_app(None,None), lambda:quit_app(None,None))
    return icon

"""Native file selection and direct JPEG output for the local desktop service."""
from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import secrets
import tempfile
import threading
from uuid import UUID

from PIL import Image


NATIVE_FILES = os.name == 'nt'
PHOTO_TYPES = '*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.tif;*.tiff'
PHOTO_SUFFIXES = {pattern[1:] for pattern in PHOTO_TYPES.split(';')}
PICKER_LOCK = threading.Lock()
FOLDER_LOCK = threading.Lock()
RECENT_FOLDERS = {}


def _com_method(instance, slot, result, *arguments):
    table = ctypes.cast(instance, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(table[slot])


@contextmanager
def _release(instance):
    try:
        yield instance
    finally:
        _com_method(instance, 2, ctypes.c_ulong)(instance)


def _check_hresult(result):
    if result < 0:
        raise ValueError('Não foi possível abrir ou concluir a seleção de arquivos do Windows.')


def _shell_path(item, ole):
    path = ctypes.c_void_p()
    _check_hresult(_com_method(item, 5, ctypes.c_long, ctypes.c_uint, ctypes.c_void_p)(
        item, 0x80058000, ctypes.byref(path)))  # SIGDN_FILESYSPATH
    try:
        return Path(ctypes.wstring_at(path))
    finally:
        ole.CoTaskMemFree(path)


def _windows_picker(folder):
    from ctypes import wintypes

    class Filter(ctypes.Structure):
        _fields_ = [('label', wintypes.LPCWSTR), ('pattern', wintypes.LPCWSTR)]

    ole = ctypes.OleDLL('ole32')
    ole.CoInitializeEx.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    ole.CoCreateInstance.argtypes = (ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.c_void_p, ctypes.c_void_p)
    ole.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
    ole.CoTaskMemFree.restype = None
    user = ctypes.WinDLL('user32')
    user.GetForegroundWindow.restype = wintypes.HWND
    dialog = ctypes.c_void_p()
    clsid = ctypes.create_string_buffer(UUID('dc1c5a9c-e88a-4dde-a5a1-60f82a20aef7').bytes_le)
    iid = ctypes.create_string_buffer(UUID('d57c7288-d4ad-4768-be02-9d969532d960').bytes_le)
    ole.CoInitializeEx(None, 2)  # Apartment-threaded, on the request thread.
    try:
        ole.CoCreateInstance(clsid, None, 1, iid, ctypes.byref(dialog))
        with _release(dialog):
            options = wintypes.DWORD()
            _check_hresult(_com_method(dialog, 10, ctypes.c_long, ctypes.c_void_p)(dialog, ctypes.byref(options)))
            # FORCEFILESYSTEM, NOCHANGEDIR and either PICKFOLDERS or ALLOWMULTISELECT.
            flags = options.value | 0x40 | 0x08 | (0x20 if folder else 0x200)
            _check_hresult(_com_method(dialog, 9, ctypes.c_long, wintypes.DWORD)(dialog, flags))
            title = 'Escolher pasta para salvar os JPEGs' if folder else 'Adicionar fotos'
            _check_hresult(_com_method(dialog, 17, ctypes.c_long, wintypes.LPCWSTR)(dialog, title))
            if not folder:
                filters = (Filter * 1)(Filter('Imagens', PHOTO_TYPES))
                _check_hresult(_com_method(dialog, 4, ctypes.c_long, ctypes.c_uint, ctypes.POINTER(Filter))(
                    dialog, len(filters), filters))
            result = _com_method(dialog, 3, ctypes.c_long, wintypes.HWND)(dialog, user.GetForegroundWindow())
            if result & 0xffffffff == 0x800704c7:  # ERROR_CANCELLED
                return []
            _check_hresult(result)
            selection = ctypes.c_void_p()
            if folder:
                _check_hresult(_com_method(dialog, 20, ctypes.c_long, ctypes.c_void_p)(dialog, ctypes.byref(selection)))
                with _release(selection):
                    return [_shell_path(selection, ole)]
            _check_hresult(_com_method(dialog, 27, ctypes.c_long, ctypes.c_void_p)(dialog, ctypes.byref(selection)))
            with _release(selection):
                count = wintypes.DWORD()
                _check_hresult(_com_method(selection, 7, ctypes.c_long, ctypes.c_void_p)(
                    selection, ctypes.byref(count)))
                paths = []
                for index in range(count.value):
                    item = ctypes.c_void_p()
                    _check_hresult(_com_method(selection, 8, ctypes.c_long, wintypes.DWORD, ctypes.c_void_p)(
                        selection, index, ctypes.byref(item)))
                    with _release(item):
                        paths.append(_shell_path(item, ole))
                return paths
    except OSError as error:
        raise ValueError('O seletor de arquivos do Windows não pôde ser aberto.') from error
    finally:
        ole.CoUninitialize()


def choose_paths(*, folder=False):
    if not NATIVE_FILES:
        raise ValueError('A seleção de arquivos e pastas está disponível no aplicativo para Windows.')
    if not PICKER_LOCK.acquire(blocking=False):
        raise ValueError('Conclua a seleção que já está aberta.')
    try:
        return _windows_picker(folder)
    finally:
        PICKER_LOCK.release()


def import_selected(add_photo, limit, closing, max_photos=100):
    selected = choose_paths()
    photos, errors = [], []
    for path in selected[:max_photos]:
        if closing is not None and closing.is_set():
            break
        try:
            if path.suffix.lower() not in PHOTO_SUFFIXES:
                raise ValueError('Formato não aceito.')
            with path.open('rb') as stream:
                data = stream.read(limit + 1)
            if len(data) > limit:
                raise ValueError(f'O arquivo excede {limit // 1024**2} MB.')
            photos.append(add_photo(data, path.name[:512], path.parent.resolve()))
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            message = str(error) if isinstance(error, ValueError) else 'Não foi possível ler esta imagem.'
            errors.append(f'{path.name}: {message}')
    if len(selected) > max_photos:
        errors.append(f'Selecione até {max_photos} fotos por vez.')
    return dict(photos=photos, errors=errors, cancelled=not selected)


def destination_for(records):
    origins = {getattr(record, 'source_folder', None) for record, _ in records}
    if len(origins) == 1:
        origin = next(iter(origins))
        if origin is not None and origin.is_dir():
            return FolderOutput(origin)
    selected = choose_paths(folder=True)
    return FolderOutput(selected[0]) if selected else None


def open_saved_folder(token):
    with FOLDER_LOCK:
        path = RECENT_FOLDERS.get(token)
    if path is None or not path.is_dir():
        raise ValueError('A pasta de saída não está mais disponível.')
    try:
        os.startfile(path)
    except OSError as error:
        raise ValueError('Não foi possível abrir a pasta de saída.') from error


class FolderOutput:
    def __init__(self, root):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError('A pasta de destino não está disponível. Escolha outra pasta.')
        self.folders = set()

    @contextmanager
    def file(self, folder, name):
        if not folder or not name or any(char in folder + name for char in '/\\:') or folder in ('.', '..'):
            raise ValueError('Nome de saída inválido.')
        directory = self.root / folder
        temporary = None
        created = False
        try:
            if directory.resolve() != directory:
                raise ValueError('A subpasta de saída aponta para outro local. Escolha outra pasta.')
            try:
                directory.mkdir()
                created = True
            except FileExistsError:
                if not directory.is_dir():
                    raise
            fd, filename = tempfile.mkstemp(prefix='.redlab-', suffix='.part', dir=directory)
            temporary = Path(filename)
            os.close(fd)
            yield temporary
            stem, suffix = os.path.splitext(name)
            for index in range(1, 10001):
                target = directory / (name if index == 1 else f'{stem} ({index}){suffix}')
                try:
                    if os.name == 'nt':
                        temporary.rename(target)  # Windows rename refuses an existing target.
                    else:
                        os.link(temporary, target)
                    self.folders.add(directory)
                    break
                except FileExistsError:
                    continue
            else:
                raise ValueError('Há muitos arquivos com o mesmo nome na pasta de saída.')
        except OSError as error:
            raise ValueError(f'Não foi possível gravar em {folder}. Confira o espaço e as permissões da pasta.') from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if created and directory not in self.folders:
                try:
                    directory.rmdir()
                except OSError:
                    pass

    def result(self):
        if not self.folders:
            return None
        path = next(iter(self.folders)) if len(self.folders) == 1 else self.root
        token = secrets.token_urlsafe(18)
        with FOLDER_LOCK:
            if len(RECENT_FOLDERS) >= 20:
                del RECENT_FOLDERS[next(iter(RECENT_FOLDERS))]
            RECENT_FOLDERS[token] = path
        return dict(token=token, name=path.name or str(path))

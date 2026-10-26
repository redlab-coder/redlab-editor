"""Immutable uploaded bytes and reduced proxies; one full original per export."""
from collections import OrderedDict
from pathlib import Path
import tempfile
import threading
import weakref
from PIL import Image
from engine import load_image

MAX_PHOTOS = 100
MAX_FILE = 50 * 1024**2
MAX_TOTAL = 4 * 1024**3


class PhotoRecord:
    def __init__(self, data):
        self.directory = tempfile.TemporaryDirectory(prefix='MedidasEditor-foto-')
        self._cleanup = weakref.finalize(self, self.directory.cleanup)
        self.original = Path(self.directory.name) / 'original'
        self.proxy = Path(self.directory.name) / 'editor.png'
        self.bytes = len(data)
        try:
            image, self.metadata = load_image(data)
            self.width, self.height = image.size
            try:
                self.original.write_bytes(data)
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                image.save(self.proxy, 'PNG', compress_level=1)
            finally:
                image.close()
        except Exception:
            self._cleanup()
            raise


class PhotoCache:
    def __init__(self):
        self.lock = threading.RLock()
        self.entries = OrderedDict()

    def get(self, record):
        with self.lock:
            key = record.directory.name
            if key not in self.entries:
                while len(self.entries) >= 3:
                    _, image = self.entries.popitem(last=False)
                    image.close()
                with Image.open(record.proxy) as source:
                    self.entries[key] = source.convert('RGB')
            self.entries.move_to_end(key)
            return self.entries[key]

    def discard(self, record):
        with self.lock:
            image = self.entries.pop(record.directory.name, None)
            if image is not None:
                image.close()

    def clear(self):
        with self.lock:
            for image in self.entries.values():
                image.close()
            self.entries.clear()

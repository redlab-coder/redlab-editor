import io
import threading
import unittest
from unittest.mock import patch
from PIL import Image
import app
from photo_store import PhotoRecord


class ShutdownTests(unittest.TestCase):
    def test_exit_during_encoding_never_publishes_partial_output(self):
        data=io.BytesIO();Image.new('RGB',(100,100),'red').save(data,'PNG')
        record=PhotoRecord(data.getvalue())
        entered=threading.Event();leave=threading.Event()
        def encode(image):
            entered.set();leave.wait(5);return b'partial output'
        identifier=None
        try:
            with patch('app.jpeg_bytes',side_effect=encode):
                identifier=app.start_export([(record,dict(name='Foto.jpg',edits={},reviewed=True))])
                self.assertTrue(entered.wait(5))
                app.CLOSING.set();leave.set()
                app.JOBS[identifier]['thread'].join(timeout=5)
            job=app.JOBS[identifier]
            self.assertFalse(job['thread'].is_alive())
            self.assertEqual(job['state'],'cancelled')
            self.assertFalse(job['path'].exists())
        finally:
            leave.set();app.CLOSING.clear()
            if identifier:
                job=app.JOBS.pop(identifier);job['thread'].join(timeout=5);job['directory'].cleanup()
            record._cleanup()

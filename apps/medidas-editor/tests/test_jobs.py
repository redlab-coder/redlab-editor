import io
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image
from jobs import ExportManager, output_name
from photo_store import PhotoRecord


class JobTests(unittest.TestCase):
    def setUp(self):
        data=io.BytesIO();Image.new('RGB',(200,100),'red').save(data,'PNG')
        self.record=PhotoRecord(data.getvalue());self.manager=ExportManager()

    def tearDown(self):
        self.manager.close();self.record._cleanup()

    def test_invalid_item_does_not_stop_other_files_and_repeated_names_are_unique(self):
        records=[(self.record,dict(name='foto.png',settings=dict(width_cm='30',height_cm='36'),reviewed=False)),
                 (self.record,dict(name='foto.png',settings=dict(width_cm='3',height_cm='3',mode='contain'))),
                 (None,dict(name='sumiu.png',settings={})),
                 (self.record,dict(name='foto.png',settings=dict(width_cm='3',height_cm='3',mode='contain')))]
        identifier=self.manager.start(records)
        self.manager.jobs[identifier]['thread'].join(timeout=30)
        status=self.manager.status(identifier)
        self.assertEqual([item['state'] for item in status['items']],['failed','ready','failed','ready'])
        self.assertEqual(status['success'],2)
        with zipfile.ZipFile(self.manager.jobs[identifier]['path']) as archive:
            self.assertEqual(len(archive.namelist()),3)
            self.assertIn('LEIA-ME-falhas.txt',archive.namelist())

    def test_cancel_has_no_download_and_worker_is_single(self):
        entered=threading.Event();leave=threading.Event()
        def slow(original,settings,path,**kwargs):
            entered.set();leave.wait(5)
            from engine import ExportCancelled
            raise ExportCancelled()
        with patch('jobs.export_jpeg',slow):
            records=[(self.record,dict(name='foto.png',settings=dict(width_cm='3',height_cm='3',mode='contain')))]
            identifier=self.manager.start(records);self.assertTrue(entered.wait(5))
            with self.assertRaises(ValueError):self.manager.start(records)
            self.manager.cancel(identifier);leave.set();self.manager.jobs[identifier]['thread'].join(timeout=10)
        self.assertEqual(self.manager.status(identifier)['state'],'cancelled')
        self.assertIsNone(self.manager.jobs[identifier]['path'])

    def test_safe_output_names(self):
        self.assertEqual(output_name('CON.jpg',0),'001-CON.jpg')
        self.assertNotIn('/',output_name('../../f:oto.png',0))

    def test_cancel_during_final_zip_write_cannot_publish_a_download(self):
        original_write=zipfile.ZipFile.write
        writes=0
        def cancel_on_last_write(archive,*args,**kwargs):
            nonlocal writes
            result=original_write(archive,*args,**kwargs);writes+=1
            if writes==2:
                next(iter(self.manager.jobs.values()))['cancel'].set()
            return result
        records=[(self.record,dict(name='foto.png',settings=dict(width_cm='3',height_cm='3',mode='contain'))) for _ in range(2)]
        with patch('jobs.zipfile.ZipFile.write',cancel_on_last_write):
            identifier=self.manager.start(records)
            self.manager.jobs[identifier]['thread'].join(timeout=30)
        self.assertEqual(self.manager.status(identifier)['state'],'cancelled')
        self.assertIsNone(self.manager.status(identifier)['download_url'])
        self.assertIsNone(self.manager.jobs[identifier]['path'])

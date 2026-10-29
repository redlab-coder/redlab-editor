import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from PIL import Image
from photo_store import PhotoRecord
from projects import write_project,read_project
from recovery import CheckpointStore,UpdateSession,UpdateBusy
from version import PRODUCT_ID


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        data=io.BytesIO();Image.new('RGB',(300,400),'red').save(data,'PNG')
        self.record=PhotoRecord(data.getvalue());self.addCleanup(self.record._cleanup)
        edits=dict(rotation=90,zoom=1.5)
        if PRODUCT_ID=='medidas-editor':edits=dict(width_cm='30',height_cm='36',mode='cover',zoom=1.5)
        self.records=[(self.record,dict(name='Foto.png',edits=edits,template='round_p',reviewed=True,manual=True))]
        self.store=CheckpointStore(self.root/'recovery',write_project,read_project,PhotoRecord)
    def test_roundtrip_ack_and_ui_drafts_survive_until_acknowledgement(self):
        state=dict(selected_index=0,draft_width='30,7',draft_height='',draft_dirty=True,checked_indices=[0])
        generation=self.store.write(self.records,state)
        result=self.store.load()
        try:
            self.assertEqual(result['ui'],state);self.assertEqual(result['generation'],generation)
            self.assertEqual(result['records'][0][0].original.read_bytes(),self.record.original.read_bytes())
            self.assertTrue(self.store.marker.exists())
            with self.assertRaises(ValueError):self.store.acknowledge('wrong-session')
            self.assertTrue(self.store.marker.exists())
            self.store.acknowledge(generation);self.assertIsNone(self.store.load())
        finally:
            for record,_ in result['records']:record._cleanup()
    def test_disk_failure_keeps_previous_checkpoint_and_does_not_arm_restart(self):
        self.store.write(self.records,{})
        before=self.store.marker.read_bytes()
        updater=Mock(lock=threading.Lock(),pending={'version':'2.0.0'},valid_download=Mock(return_value=True),stopped=threading.Event())
        updater.restart_requested=False;session=UpdateSession(updater,self.store)
        with patch.object(self.store,'writer',side_effect=OSError('disk full')):
            with self.assertRaises(ValueError):session.apply(lambda:self.records,{})
        self.assertFalse(session.applying);self.assertFalse(updater.restart_requested);self.assertFalse(updater.stopped.is_set())
        self.assertEqual(before,self.store.marker.read_bytes());self.assertEqual(len(list(self.store.root.glob('*.project'))),1)
    def test_busy_or_unverified_update_does_not_close_and_verified_update_arms_restart(self):
        updater=Mock(lock=threading.Lock(),pending={'version':'2.0.0'},valid_download=Mock(return_value=False),stopped=threading.Event())
        updater.restart_requested=False;session=UpdateSession(updater,self.store)
        session.enter('/api/preview')
        with self.assertRaises(UpdateBusy):session.apply(lambda:self.records,{})
        session.leave()
        with self.assertRaises(UpdateBusy):session.apply(lambda:self.records,{},busy=lambda:True)
        with self.assertRaises(ValueError):session.apply(lambda:self.records,{})
        self.assertFalse(self.store.marker.exists());self.assertFalse(updater.restart_requested)
        updater.valid_download.return_value=True
        session.apply(lambda:self.records,{})
        self.assertTrue(updater.restart_requested);self.assertTrue(updater.stopped.is_set());self.assertTrue(self.store.marker.exists())
        with self.assertRaises(UpdateBusy):session.enter('/api/upload')
    def test_tamper_invalid_paths_and_invalid_ui_preserve_backup(self):
        generation=self.store.write(self.records,{})
        path=self.store.root/(generation+'.project');path.write_bytes(b'altered')
        with self.assertRaises(ValueError):self.store.load()
        self.assertTrue(path.exists())
        self.store.marker.write_text(json.dumps(dict(generation='../outside')),encoding='utf-8')
        with self.assertRaises(ValueError):self.store.load()
        with self.assertRaises(ValueError):self.store.write(self.records,dict(selected_index=1000))
    def test_empty_session_is_recoverable(self):
        self.store.write([],dict(selected_index=-1))
        self.assertEqual(self.store.load()['records'],[])

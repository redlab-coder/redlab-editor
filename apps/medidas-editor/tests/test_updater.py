import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from updater import Updater, installed_directory, validate_manifest, version_tuple
from version import REPOSITORY, PRODUCT_ID, RELEASE_PREFIX


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = b'fixture installer bytes; never executed'
        self.manifest = {'product':PRODUCT_ID,'version':'1.1.0','url':f'https://github.com/{REPOSITORY}/releases/download/{RELEASE_PREFIX}1.1.0/MedidasEditor-Setup-1.1.0.exe','sha256':hashlib.sha256(self.data).hexdigest(),'size':len(self.data)}

    def opener(self, request, timeout):
        return io.BytesIO(json.dumps(self.manifest).encode() if request.full_url.endswith(PRODUCT_ID+'.json') else self.data)

    def manager(self, opener=None, current='1.0.0'):
        return Updater(self.root/'app', self.root/'updates', current=current, opener=opener or self.opener)

    def test_versions_and_strict_manifest_origin(self):
        self.assertGreater(version_tuple('1.0.10'), version_tuple('1.0.2'))
        for version in ('1.0', '../1.2.3', '1.2.3-beta', '١.٢.٣', None):
            with self.assertRaises(ValueError): version_tuple(version)
        for changes in ({'product':'outro-editor'},{'url':'https://example.com/setup.exe'},{'sha256':12},{'size':True},{'size':200*1024**2},{'sha256':'z'*64}):
            with self.assertRaises(ValueError):validate_manifest(dict(self.manifest,**changes))

    def test_download_is_verified_and_only_runs_on_exit(self):
        manager=self.manager()
        with patch('updater.subprocess.Popen') as launch:
            manager.check()
            launch.assert_not_called()
            self.assertEqual(manager.destination(self.manifest).read_bytes(),self.data)
            self.assertTrue(manager.install_on_exit())
            args=launch.call_args.args[0]
            self.assertIn('/VERYSILENT',args)
            self.assertTrue(any(arg.startswith('/WAITPID=') for arg in args))
            self.assertIn('/DIR='+str((self.root/'app').resolve()),args)

    def test_corrupted_or_incomplete_download_is_never_staged(self):
        self.data=b'corrupt'
        manager=self.manager()
        with patch('updater.subprocess.Popen') as launch:
            manager.check()
            self.assertIsNone(manager.pending)
            self.assertFalse((manager.root/'pending.json').exists())
            self.assertFalse(list(manager.root.glob('*.part')))
            self.assertFalse(manager.install_on_exit())
            launch.assert_not_called()

    def test_pending_update_survives_offline_and_is_reverified(self):
        self.manager().check()
        manager=self.manager(opener=Mock(side_effect=OSError('offline')))
        self.assertIsNotNone(manager.pending)
        manager.check()
        self.assertIsNotNone(manager.pending)
        manager.destination(self.manifest).write_bytes(b'tampered')
        with patch('updater.subprocess.Popen') as launch:
            self.assertFalse(manager.install_on_exit())
            launch.assert_not_called()

    def test_current_version_never_downgrades_and_cleans_consumed_update(self):
        self.manager().check()
        manager=self.manager(current='1.1.0')
        self.assertIsNone(manager.pending)
        self.assertFalse((manager.root/'pending.json').exists())
        self.assertFalse(manager.destination(self.manifest).exists())
        manager.check()
        self.assertIsNone(manager.pending)

    def test_portable_never_enables_auto_installation(self):
        executable=self.root/'MedidasEditor.exe'
        with patch('updater.sys.executable',str(executable)),patch('updater.sys.frozen',True,create=True):
            self.assertIsNone(installed_directory())
            (self.root/'installed.marker').write_text('MedidasEditor\n',encoding='utf-8')
            self.assertEqual(installed_directory(),self.root.resolve())
            with patch('updater.sys.executable',str(self.root/'MedidasEditor-Portable.exe')):
                self.assertIsNone(installed_directory())

    def test_ui_status_is_readable_while_downloading_and_restored_when_ready(self):
        entered, release = threading.Event(), threading.Event()
        def opener(request, timeout):
            if not request.full_url.endswith(PRODUCT_ID+'.json'):
                entered.set()
                release.wait(3)
            return self.opener(request, timeout)
        manager=self.manager(opener=opener)
        thread=threading.Thread(target=manager.check)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(manager.snapshot(),{'state':'downloading','version':'1.1.0'})
        finally:
            release.set();thread.join(timeout=3)
        self.assertEqual(manager.snapshot(),{'state':'ready','version':'1.1.0'})
        self.assertEqual(self.manager().snapshot(),{'state':'ready','version':'1.1.0'})


class RestartUpdateTests(unittest.TestCase):
    setUp=UpdateTests.setUp
    opener=UpdateTests.opener
    manager=UpdateTests.manager
    def test_restart_parameter_is_added_only_after_explicit_request(self):
        manager=self.manager();manager.check()
        with patch('updater.subprocess.Popen') as launch:
            manager.restart_requested=True
            self.assertTrue(manager.install_on_exit())
            self.assertIn('/RESTARTEDITOR=1',launch.call_args.args[0])
    def test_failed_installer_launch_keeps_verified_download_and_checkpoint(self):
        manager=self.manager();manager.check();manager.restart_requested=True
        recovery=manager.root/'recovery';recovery.mkdir();marker=recovery/'current.json';marker.write_text('checkpoint')
        with patch('updater.subprocess.Popen',side_effect=OSError('installation blocked')):
            self.assertFalse(manager.install_on_exit())
        self.assertEqual(marker.read_text(),'checkpoint');self.assertTrue(manager.valid_download(manager.pending))
    def test_no_browser_restart_is_explicit_and_separate_from_normal_updates(self):
        manager=self.manager();manager.check();manager.restart_requested=True;manager.restart_no_browser=True
        with patch('updater.subprocess.Popen') as launch:
            self.assertTrue(manager.install_on_exit());self.assertIn('/RESTARTNOBROWSER=1',launch.call_args.args[0])
    def test_cached_newer_update_survives_a_stale_feed(self):
        manager=self.manager();manager.check()
        older=dict(self.manifest,version='1.0.0')
        older['url']=older['url'].replace('1.1.0','1.0.0')
        manager.opener=lambda request,timeout:io.BytesIO(json.dumps(older).encode())
        manager.check()
        self.assertEqual(manager.snapshot(),{'state':'ready','version':'1.1.0'})
    def test_periodic_checks_use_half_hour_and_retry_in_five_minutes(self):
        for failed,interval in [(False,1800),(True,300)]:
            manager=self.manager();manager.stopped=Mock(wait=Mock(side_effect=[False,False,True]),is_set=Mock(return_value=False))
            def check():manager._check_failed=failed
            manager.check=check
            with patch('updater.threading.Thread') as thread:
                manager.start();thread.call_args.kwargs['target']()
            self.assertEqual([call.args[0] for call in manager.stopped.wait.call_args_list],[1,interval,interval])

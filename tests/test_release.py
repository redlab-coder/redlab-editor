import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publish', ROOT/'scripts/publish.py')
publish = importlib.util.module_from_spec(spec);spec.loader.exec_module(publish)


class ReleaseTests(unittest.TestCase):
    def test_medidas_has_a_separate_release_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            installer=root/'MedidasEditor-Setup-1.0.0.exe';installer.write_bytes(b'new product fixture')
            portable=root/'MedidasEditor-Portable.exe';portable.write_bytes(b'portable fixture')
            manifest=dict(product='medidas-editor',version='1.0.0',
                url='https://github.com/redlab-coder/redlab-editor/releases/download/medidas-v1.0.0/'+installer.name,
                sha256=hashlib.sha256(installer.read_bytes()).hexdigest(),size=installer.stat().st_size)
            (root/'update.json').write_text(json.dumps(manifest),encoding='utf-8')
            (root/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n'
                for path in (installer,portable,root/'update.json')),encoding='utf-8')
            self.assertEqual(publish.validate_artifacts('medidas-editor','medidas-v1.0.0',root)[0],manifest)
            for other in ('bottons-editor','polaroid-editor'):
                with self.assertRaises(ValueError):publish.validate_artifacts(other,'medidas-v1.0.0',root)

    def test_channels_are_independent_and_cannot_downgrade_or_replace_version(self):
        first = {'product':'bottons-editor','version':'1.1.0','sha256':'a'}
        self.assertTrue(publish.should_advance(None, first))
        self.assertTrue(publish.should_advance(first, dict(first, version='1.2.0')))
        self.assertFalse(publish.should_advance(first, dict(first, version='1.0.0')))
        self.assertFalse(publish.should_advance(first, first.copy()))
        with self.assertRaises(ValueError):publish.should_advance(first, dict(first, product='polaroid-editor'))
        with self.assertRaises(ValueError):publish.should_advance(first, dict(first, sha256='changed'))

    def test_artifact_contract_checks_product_tag_and_actual_binary_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);installer=root/'BottonsEditor-Setup-1.1.0.exe'
            installer.write_bytes(b'fixture, never executed')
            (root/'BottonsEditor-Portable.exe').write_bytes(b'portable fixture')
            manifest={'product':'bottons-editor','version':'1.1.0',
                      'url':'https://github.com/redlab-coder/redlab-editor/releases/download/bottons-v1.1.0/'+installer.name,
                      'sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),'size':installer.stat().st_size}
            (root/'update.json').write_text(json.dumps(manifest))
            (root/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n'
                for path in (installer, root/'BottonsEditor-Portable.exe', root/'update.json')))
            self.assertEqual(publish.validate_artifacts('bottons-editor','bottons-v1.1.0',root)[0],manifest)
            with self.assertRaises(ValueError):publish.validate_artifacts('bottons-editor','polaroid-v1.1.0',root)
            with self.assertRaises(ValueError):publish.validate_artifacts('polaroid-editor','polaroid-v1.1.0',root)
            installer.write_bytes(b'altered')
            with self.assertRaises(ValueError):publish.validate_artifacts('bottons-editor','bottons-v1.1.0',root)

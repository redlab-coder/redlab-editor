"""Release preparation, artifact trust boundaries and CI dependency contracts."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import bundle
import release
import release_artifacts as artifacts
from publish import PRODUCTS, REPOSITORY


class PreparationTests(unittest.TestCase):
    def copy_catalog(self, destination):
        paths = ['README.md', 'CHANGELOG.md', 'docs/maintenance.md', 'docs/package.md',
                 'bundle/package.json', 'bundle/RELEASE_NOTES.md']
        for product in PRODUCTS:
            paths += [f'apps/{product}/{name}' for name in ('version.py', 'README.md', 'CHANGELOG.md', 'RELEASE_NOTES.md', f'installer/{product}.iss')]
        for relative in paths:
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, target)

    def test_product_preparation_keeps_other_apps_and_bundle_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_catalog(root)
            before = (root/'README.md').read_bytes()
            changes = release.prepare(root, 'bottons-editor', '1.2.4', '- Melhora o alinhamento.', date='30/10/2026')
            self.assertEqual(before, (root/'README.md').read_bytes())
            self.assertNotIn(Path('bundle/package.json'), changes)
            self.assertFalse(any('polaroid-editor' in str(path) or 'medidas-editor' in str(path) for path in changes))
            self.assertIn('Bottons 1.2.3', changes[Path('README.md')])
            self.assertIn('bottons-v1.2.4/BottonsEditor-Setup-1.2.4.exe', changes[Path('README.md')])
            self.assertIn('Versão 1.2.4', changes[Path('apps/bottons-editor/README.md')])
            self.assertIn('#define AppVersion "1.2.4"', changes[Path('apps/bottons-editor/installer/bottons-editor.iss')])
            self.assertTrue(changes[Path('apps/bottons-editor/RELEASE_NOTES.md')].startswith('# Bottons Editor 1.2.4\n'))
            self.assertIn('Bottons Editor 1.2.4 — 30/10/2026', changes[Path('CHANGELOG.md')])
            self.assertIn('## Bottons Editor 1.2.3 e pacote 1.0.2', changes[Path('CHANGELOG.md')])

    def test_bundle_preparation_changes_only_pins_requested_and_preserves_individual_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_catalog(root)
            changes = release.prepare(root, 'bundle', '1.0.3', 'Atualiza o conjunto.', included={'bottons-editor': '1.2.4'})
            config = json.loads(changes[Path('bundle/package.json')])
            self.assertEqual(config['products'], dict(bundle.package()['products'], **{'bottons-editor': '1.2.4'}))
            self.assertIn('Bottons 1.2.4', changes[Path('README.md')])
            # An individual download is not moved to an unpublished product by a bundle edit.
            self.assertIn('bottons-v1.2.3/BottonsEditor-Setup-1.2.3.exe', changes[Path('README.md')])
            self.assertIn('RedlabEditor-Setup-1.0.3.exe', changes[Path('docs/package.md')])
            self.assertIn('Bottons Editor 1.2.4', changes[Path('bundle/RELEASE_NOTES.md')])
            self.assertFalse(any(str(path).startswith('apps/') for path in changes))

    def test_invalid_versions_notes_and_pins_do_not_produce_a_plan(self):
        for version, notes in [('1.2.3', 'Ajusta.'), ('1.2.2', 'Ajusta.'), ('1.2.4', ''), ('1.2.4', 'TODO')]:
            with self.assertRaises(ValueError):
                release.prepare(ROOT, 'bottons-editor', version, notes)
        with self.assertRaises(ValueError):
            release.prepare(ROOT, 'bundle', '1.0.3', 'Melhora.', included={'bottons-editor': '1.0.0'})


class ArtifactTests(unittest.TestCase):
    def approved_run(self):
        return dict(id=12, head_sha='a'*40, event='push', path='.github/workflows/bottons.yml',
                    repository={'full_name': REPOSITORY}, head_repository={'full_name': REPOSITORY},
                    head_branch='main', status='completed', conclusion='success', run_attempt=1)

    def fixture(self, root):
        version = release.current_version(ROOT, 'bottons-editor')
        setup = root/f'BottonsEditor-Setup-{version}.exe'
        portable = root/'BottonsEditor-Portable.exe'
        setup.write_bytes(b'installer-fixture-never-executed')
        portable.write_bytes(b'portable-fixture-never-executed')
        manifest = dict(product='bottons-editor', version=version,
            url=f'https://github.com/{REPOSITORY}/releases/download/bottons-v{version}/{setup.name}',
            sha256=hashlib.sha256(setup.read_bytes()).hexdigest(), size=setup.stat().st_size)
        (root/'update.json').write_text(json.dumps(manifest))
        checks = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (setup, portable, root/'update.json')}
        (root/'SHA256SUMS.txt').write_text(''.join(digest+'  '+name+'\n' for name, digest in checks.items()))
        evidence = dict(schema=1, product='bottons-editor', source_sha='a'*40, version=version,
                        run_id=12, run_attempt=1, full_validation=True,
                        sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()})
        (root/'build.json').write_text(json.dumps(evidence))

    def test_rejects_forks_prs_failed_runs_different_commits_and_workflows(self):
        valid = self.approved_run()
        self.assertTrue(artifacts.trusted_run(valid, 'bottons-editor', 'a'*40))
        for field, value in [('event', 'pull_request'), ('conclusion', 'failure'), ('head_branch', 'codex/test'),
                             ('head_sha', 'b'*40), ('path', '.github/workflows/polaroid.yml'),
                             ('head_repository', {'full_name': 'somebody/fork'})]:
            with self.subTest(field=field):
                self.assertFalse(artifacts.trusted_run(dict(valid, **{field: value}), 'bottons-editor', 'a'*40))

    def test_evidence_detects_tampering_including_checksums_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            artifacts.verify_files('bottons-editor', root, 'a'*40, 12, 1)
            with self.assertRaises(ValueError):
                artifacts.verify_files('bottons-editor', root, 'b'*40, 12, 1)
            with self.assertRaises(ValueError):
                artifacts.verify_files('bottons-editor', root, 'a'*40, 12, 2)
            path = root/'SHA256SUMS.txt'
            path.write_text(path.read_text()+'\n')
            with self.assertRaises(ValueError):
                artifacts.verify_files('bottons-editor', root, 'a'*40, 12, 1)

    def test_restore_checks_github_archive_digest_and_refuses_extra_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root/'inputs'
            inputs.mkdir()
            self.fixture(inputs)
            def archive(extra=False):
                output = io.BytesIO()
                with zipfile.ZipFile(output, 'w') as stream:
                    for path in inputs.iterdir():
                        stream.writestr(path.name, path.read_bytes())
                    if extra:
                        stream.writestr('../escape.txt', 'invalid')
                return output.getvalue()
            data = archive()
            item = dict(id=22, name=artifacts.artifact_name('bottons-editor', 12), expired=False,
                        digest='sha256:'+hashlib.sha256(data).hexdigest(), workflow_run={'head_sha': 'a'*40})
            def fake_gh(*args):
                if args[-1].endswith('/jobs'):
                    return json.dumps({'jobs': [{'name': 'windows / validate', 'conclusion': 'success'}]})
                return json.dumps({'artifacts': [item]} if args[-1].endswith('/artifacts') else dict(self.approved_run(), run_attempt=2))
            with patch.object(artifacts, 'source_sha', return_value='a'*40), patch.object(artifacts, 'gh', side_effect=fake_gh), patch.object(artifacts.subprocess, 'check_output', return_value=data):
                artifacts.restore('bottons-editor', 12, root/'approved')
                self.assertEqual((root/'approved/update.json').read_bytes(), (inputs/'update.json').read_bytes())
                item['digest'] = 'sha256:'+'0'*64
                with self.assertRaises(ValueError):
                    artifacts.restore('bottons-editor', 12, root/'bad')
            data = archive(extra=True)
            item['digest'] = 'sha256:'+hashlib.sha256(data).hexdigest()
            with patch.object(artifacts, 'source_sha', return_value='a'*40), patch.object(artifacts, 'gh', side_effect=fake_gh), patch.object(artifacts.subprocess, 'check_output', return_value=data):
                with self.assertRaises(ValueError):
                    artifacts.restore('bottons-editor', 12, root/'bad')
            self.assertFalse((root/'escape.txt').exists())

    def test_absent_expired_or_failed_approval_falls_back_without_waiting(self):
        candidate = self.approved_run()
        responses = [json.dumps({'workflow_runs': []}), json.dumps({'workflow_runs': [dict(candidate, conclusion='failure')]})]
        for response in responses:
            with patch.object(artifacts, 'source_sha', return_value='a'*40), patch.object(artifacts, 'gh', return_value=response), patch.object(artifacts.time, 'sleep') as sleep:
                self.assertIsNone(artifacts.find('bottons-editor', 0))
                sleep.assert_not_called()
        with patch.object(artifacts, 'source_sha', return_value='a'*40), patch.object(artifacts, 'gh', side_effect=[json.dumps({'workflow_runs': [candidate]}), json.dumps({'artifacts': []})]):
            self.assertIsNone(artifacts.find('bottons-editor', 0))

    def test_manual_reuse_check_does_not_wait_for_itself(self):
        own_run = dict(self.approved_run(), conclusion=None, status='in_progress', event='workflow_dispatch')
        with patch.dict(artifacts.os.environ, {'GITHUB_RUN_ID': '12'}), patch.object(artifacts, 'source_sha', return_value='a'*40), patch.object(artifacts, 'gh', return_value=json.dumps({'workflow_runs': [own_run]})), patch.object(artifacts.time, 'sleep') as sleep:
            self.assertIsNone(artifacts.find('bottons-editor'))
            sleep.assert_not_called()


class BundleInputTests(unittest.TestCase):
    def test_published_pins_are_reused_and_only_unpublished_versions_are_built(self):
        def lookup(*args):
            if 'bottons-v' in args[-1]:
                raise subprocess.CalledProcessError(1, ['gh'], stderr=b'gh: Not Found (HTTP 404)')
            return json.dumps(dict(draft=False, prerelease=False))
        with patch.object(bundle, 'gh', side_effect=lookup):
            plan = bundle.input_plan()
            self.assertEqual(plan['build'], ['bottons-editor'])
            self.assertEqual(plan['published'], ['polaroid-editor', 'medidas-editor'])
            with self.assertRaises(ValueError):
                bundle.input_plan(require_public=True)

    def test_network_and_authorization_errors_cannot_become_missing_releases(self):
        error = subprocess.CalledProcessError(1, ['gh'], stderr=b'HTTP 403 rate limited')
        with patch.object(bundle, 'gh', side_effect=error), self.assertRaises(subprocess.CalledProcessError):
            bundle.input_plan()


class WorkflowTests(unittest.TestCase):
    def load(self, name):
        # BaseLoader preserves the YAML key 'on' instead of YAML 1.1 booleans.
        return yaml.load((ROOT/'.github/workflows'/name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)

    def test_all_products_share_the_full_validation_contract_and_safe_publication_dependencies(self):
        for product in PRODUCTS:
            data = self.load(Path(artifacts.workflow(product)).name)
            jobs = data['jobs']
            self.assertEqual(jobs['windows']['uses'], './.github/workflows/_editor-windows.yml')
            self.assertEqual(jobs['windows']['with']['product'], product)
            self.assertIn("github.event_name != 'pull_request'", jobs['windows']['with']['full'])
            self.assertEqual(jobs['publish']['needs'], ['reuse', 'windows'])
            self.assertIn('!cancelled()', jobs['publish']['if'])
            self.assertIn("github.event_name == 'pull_request'", data['concurrency']['cancel-in-progress'])
        shared = self.load('_editor-windows.yml')
        steps = shared['jobs']['validate']['steps']
        names = [step.get('name') for step in steps]
        self.assertLess(names.index('Validar instalação e atualização'), names.index('Registrar aprovação do executável exato'))
        self.assertLess(names.index('Validar migração do Moldura para Bottons Editor'), names.index('Registrar aprovação do executável exato'))
        for step in steps:
            if step.get('name') == 'Guardar instalador aprovado':
                self.assertEqual(step['with']['compression-level'], '0')
                self.assertIn('build.json', step['with']['path'])

    def test_bundle_handles_empty_build_matrix_and_keeps_real_installer_checks(self):
        jobs = self.load('bundle.yml')['jobs']
        self.assertIn("!= '[]'", jobs['build-editors']['if'])
        self.assertEqual(jobs['windows']['needs'], ['inputs', 'build-editors'])
        self.assertIn("== 'skipped'", jobs['windows']['if'])
        self.assertTrue(any(step.get('run') == 'python -u scripts/check_bundle.py' for step in jobs['windows']['steps']))


if __name__ == '__main__':
    unittest.main()

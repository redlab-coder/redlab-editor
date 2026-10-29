import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import bundle
from publish import PRODUCTS, REPOSITORY


def make_inputs(root):
    for product, version in bundle.package()['products'].items():
        executable, _, prefix = PRODUCTS[product]
        folder = root/product
        folder.mkdir(parents=True)
        installer = folder/f'{executable}-Setup-{version}.exe'
        installer.write_bytes(b'fixture-not-executable-'+product.encode())
        portable = folder/f'{executable}-Portable.exe'
        portable.write_bytes(b'portable-fixture-'+product.encode())
        manifest = dict(product=product, version=version,
            url=f'https://github.com/{REPOSITORY}/releases/download/{prefix}{version}/{installer.name}',
            sha256=bundle.digest(installer), size=installer.stat().st_size)
        update = folder/'update.json'
        update.write_text(json.dumps(manifest), encoding='utf-8')
        (folder/'SHA256SUMS.txt').write_text(''.join(bundle.digest(path)+'  '+path.name+'\n' for path in (installer, portable, update)), encoding='utf-8')


class BundleTests(unittest.TestCase):
    def test_package_pins_each_version_and_matches_documentation(self):
        config = bundle.package()
        version = config['version']
        url = f'https://github.com/{REPOSITORY}/releases/download/redlab-v{version}/RedlabEditor-Setup-{version}.exe'
        self.assertIn(url, (ROOT/'README.md').read_text(encoding='utf-8'))
        self.assertIn(version, (ROOT/'bundle/RELEASE_NOTES.md').read_text(encoding='utf-8').splitlines()[0])
        for product, product_version in config['products'].items():
            self.assertIn(PRODUCTS[product][1]+' '+product_version,
                (ROOT/'bundle/RELEASE_NOTES.md').read_text(encoding='utf-8'))

    def test_inputs_verify_all_three_products_and_render_owned_registry_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_inputs(root/'inputs')
            contents = bundle.generate_inputs(root/'inputs', root/'build')
            code = (root/'build/products.iss').read_text(encoding='utf-8-sig')
            self.assertEqual(len(contents['products']), 3)
            for item in contents['products']:
                key, mutexes = bundle.identities(item['id'])
                self.assertIn(key+'_is1', code)
                self.assertIn(mutexes, code)
                self.assertIn(item['sha256'], code)
                self.assertIn(item['version'], code)
            self.assertNotIn('update.json', code)

    def test_modified_installer_stops_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_inputs(root)
            path = next((root/'bottons-editor').glob('*Setup*'))
            path.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                bundle.verified_contents(root)

    def test_a_valid_but_different_product_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_inputs(root)
            path = root/'polaroid-editor/update.json'
            value = json.loads(path.read_text())
            value['product'] = 'bottons-editor'
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                bundle.verified_contents(root)

    def test_bundle_manifest_and_final_binary_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_inputs(root/'inputs')
            contents = bundle.verified_contents(root/'inputs')
            installer = root/f'RedlabEditor-Setup-{contents["version"]}.exe'
            installer.write_bytes(b'not-executed-suite-fixture')
            manifest = root/'contents.json'
            manifest.write_text(json.dumps(contents), encoding='utf-8')
            def checksums():
                (root/'SHA256SUMS.txt').write_text(''.join(bundle.digest(path)+'  '+path.name+'\n' for path in (installer, manifest)))
            checksums()
            tag = 'redlab-v'+contents['version']
            self.assertEqual(bundle.validate_bundle(root, tag)[0], contents)
            with self.assertRaises(ValueError):
                bundle.validate_bundle(root, 'polaroid-v'+contents['version'])
            installer.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                bundle.validate_bundle(root, tag)
            checksums()
            for change in ('url', 'version', 'duplicate'):
                invalid = copy.deepcopy(contents)
                if change == 'duplicate':
                    invalid['products'][1] = invalid['products'][0]
                else:
                    invalid['products'][0][change] = 'https://other.test/file.exe' if change == 'url' else '999.0.0'
                manifest.write_text(json.dumps(invalid), encoding='utf-8')
                checksums()
                with self.assertRaises(ValueError):
                    bundle.validate_bundle(root, tag)

    def test_individual_installers_own_family_shortcuts_and_removal(self):
        for product, (_, name, _) in PRODUCTS.items():
            text = (ROOT/'apps'/product/'installer'/f'{product}.iss').read_text(encoding='utf-8')
            self.assertIn('Name: "{userprograms}\\RedLab Editor\\'+name+'";', text)
            self.assertIn('Type: files; Name: "{userprograms}\\'+name+'.lnk"', text)
            self.assertIn('PrivilegesRequired=lowest', text)
            self.assertEqual(text.count('#include "..\\..\\..\\scripts\\installer_version_guard.iss"'), 1)

    def test_suite_cannot_register_a_fourth_app_or_write_update_channels(self):
        script = (ROOT/'bundle/redlab-editor.iss').read_text(encoding='utf-8')
        self.assertIn('Uninstallable=no', script)
        self.assertIn('CreateAppDir=no', script)
        self.assertIn('CheckForMutexes', script)
        publisher = (ROOT/'scripts/publish_bundle.py').read_text(encoding='utf-8')
        self.assertNotIn('update_feed(', publisher)
        self.assertNotIn('update.json', publisher)


if __name__ == '__main__':
    unittest.main()

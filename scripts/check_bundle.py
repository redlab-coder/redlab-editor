"""Exercise genuine installers only on a disposable GitHub Windows runner."""
import configparser
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request
import winreg

from bundle import BUNDLE, ROOT, digest, identities, package
from publish import PRODUCTS


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('Use uma conta Windows descartável no GitHub Actions. O teste não roda no computador do operador.')
    config = package()
    setup = BUNDLE/'dist'/f'RedlabEditor-Setup-{config["version"]}.exe'
    keys = {product: identities(product)[0]+'_is1' for product in PRODUCTS}
    keys = {product: 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\'+key for product, key in keys.items()}
    def installed(product):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, keys[product], 0, winreg.KEY_READ|view) as key:
                    return {field: winreg.QueryValueEx(key, field)[0] for field in ('DisplayVersion', 'InstallLocation')}
            except FileNotFoundError:
                continue
        return None
    if any(installed(product) for product in PRODUCTS):
        raise SystemExit('Já existe um editor registrado. O teste não alterará instalações existentes.')
    def folder(csidl):
        value = ctypes.create_unicode_buffer(32768)
        assert ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, value) == 0
        return Path(value.value)
    programs, desktop = folder(2), folder(16)
    def set_version(product, version):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, keys[product], 0, winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
            winreg.SetValueEx(key, 'DisplayVersion', 0, winreg.REG_SZ, version)
    flags = subprocess.CREATE_NO_WINDOW
    runtime = None
    with tempfile.TemporaryDirectory(prefix='RedLab-suite-test-') as temporary:
        sandbox = Path(temporary)
        apps = sandbox/'Aplicativos de impressão'
        def application(product):
            return apps/PRODUCTS[product][1]/(PRODUCTS[product][0]+'.exe')
        def run(name, components=None, tasks=''):
            logs = sandbox/'logs'/name
            command = [str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                f'/INSTALLROOT={apps}', f'/LOGDIR={logs}', f'/LOG={sandbox/name}.log', '/TASKS='+tasks]
            if components is not None:
                command += ['/COMPONENTS='+','.join(item.replace('-', '_') for item in components)]
            result = subprocess.run(command, timeout=300, creationflags=flags)
            report = configparser.ConfigParser()
            if (logs/'result.ini').exists():
                data = (logs/'result.ini').read_bytes()
                report.read_string(data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig', errors='replace'))
            return result.returncode, report
        def uninstall(product):
            uninstaller = application(product).parent/'unins000.exe'
            if not uninstaller.exists():
                return
            subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], check=True, timeout=90, creationflags=flags)
            deadline = time.monotonic()+30
            while (uninstaller.exists() or installed(product)) and time.monotonic() < deadline:
                time.sleep(.15)
            assert not uninstaller.exists() and installed(product) is None, product
        def close_runtime():
            nonlocal runtime
            if not runtime:
                return
            process, state, product = runtime
            html = urllib.request.urlopen(state['url'], timeout=5).read().decode()
            token = re.search('name="'+product+'-token" content="([^"]+)', html).group(1)
            request = urllib.request.Request(state['url']+'/api/quit', data=b'{}',
                headers={'Content-Type':'application/json', 'X-'+PRODUCTS[product][0]+'-Token':token})
            urllib.request.urlopen(request, timeout=5).close()
            assert process.wait(timeout=30) == 0
            runtime = None
        def start(product):
            nonlocal runtime
            assert runtime is None
            state_root = sandbox/'estado'
            namespace = PRODUCTS[product][0]+'-Installed'
            metadata = state_root/namespace/'runtime.json'
            process = subprocess.Popen([str(application(product)), '--no-browser', '--no-updates'],
                env=dict(os.environ, LOCALAPPDATA=str(state_root)), creationflags=flags)
            deadline = time.monotonic()+45
            while time.monotonic() < deadline:
                try:
                    state = json.loads(metadata.read_text())
                    health = json.load(urllib.request.urlopen(state['url']+'/health', timeout=1))
                    if health['instance'] == state['instance'] and health['version'] == config['products'][product]:
                        runtime = process, state, product
                        return
                except (OSError, ValueError, KeyError):
                    pass
                if process.poll() is not None:
                    raise AssertionError('O editor encerrou antes de abrir: '+product)
                time.sleep(.15)
            raise AssertionError('O editor não iniciou: '+product)
        try:
            code, report = run('seleção parcial', ['bottons-editor', 'polaroid-editor'])
            assert code == 0, code
            assert report['medidas-editor']['state'] == 'not-selected'
            assert installed('medidas-editor') is None
            for product in ('bottons-editor', 'polaroid-editor'):
                assert report[product]['state'] == 'installed'
                name = PRODUCTS[product][1]
                assert (programs/'RedLab Editor'/(name+'.lnk')).exists()
                assert not (programs/(name+'.lnk')).exists()
                assert not (desktop/(name+'.lnk')).exists()
            code, report = run('pacote completo', tasks='desktopicon')
            assert code == 0
            for product in PRODUCTS:
                assert report[product]['state'] == ('installed' if product == 'medidas-editor' else 'repaired')
                assert installed(product)['DisplayVersion'] == config['products'][product]
                assert Path(installed(product)['InstallLocation']).resolve() == application(product).parent.resolve()
                assert (desktop/(PRODUCTS[product][1]+'.lnk')).exists()
                start(product)
                close_runtime()
            # User files survive repairs, existing app paths are reused, no downgrade.
            sentinel = application('bottons-editor').parent/'trabalho.bottons'
            sentinel.write_bytes(b'preserve this user work')
            before = digest(application('bottons-editor'))
            set_version('bottons-editor', '9999.0.0')
            set_version('polaroid-editor', '0.9.0')
            code, report = run('versões existentes')
            assert code == 0
            assert report['bottons-editor']['state'] == 'newer-preserved'
            assert installed('bottons-editor')['DisplayVersion'] == '9999.0.0'
            assert digest(application('bottons-editor')) == before
            assert sentinel.read_bytes() == b'preserve this user work'
            assert report['polaroid-editor']['state'] == 'updated'
            set_version('bottons-editor', config['products']['bottons-editor'])
            # An in-use selected editor blocks the entire batch before any update.
            start('medidas-editor')
            set_version('polaroid-editor', '0.9.0')
            code, _ = run('editor aberto')
            assert code != 0
            assert installed('polaroid-editor')['DisplayVersion'] == '0.9.0'
            assert runtime[0].poll() is None
            # An unselected running editor does not block another editor.
            code, report = run('outro editor aberto', ['polaroid-editor'])
            assert code == 0 and report['polaroid-editor']['state'] == 'updated'
            close_runtime()
            for product in PRODUCTS:
                uninstall(product)
            assert sentinel.read_bytes() == b'preserve this user work'
            sentinel.unlink()
            # A genuine child failure must not prevent the others from installing.
            collision = apps/'Polaroid Editor'
            collision.parent.mkdir(parents=True, exist_ok=True)
            if collision.exists():
                collision.rmdir()  # empty, owned directory only
            collision.write_text('owned failure fixture', encoding='utf-8')
            code, report = run('falha individual')
            assert code == 1
            assert report['polaroid-editor']['state'] == 'failed'
            assert report['bottons-editor']['state'] == report['medidas-editor']['state'] == 'installed'
            assert installed('polaroid-editor') is None
            collision.unlink()
            # An independent installer still repairs its own app and shortcut.
            child = BUNDLE/'build/inputs/bottons-editor'/f'BottonsEditor-Setup-{config["products"]["bottons-editor"]}.exe'
            subprocess.run([str(child), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/TASKS='], check=True, timeout=90, creationflags=flags)
            assert (programs/'RedLab Editor/Bottons Editor.lnk').exists()
            assert not (programs/'Bottons Editor.lnk').exists()
            uninstall('bottons-editor')
            assert (programs/'RedLab Editor/Medidas Editor.lnk').exists()
            start('medidas-editor')
            close_runtime()
            print(json.dumps({'partial_selection':'OK', 'offline_full_install':'OK',
                'three_actual_applications':'OK', 'desktop_and_grouped_shortcuts':'OK',
                'no_downgrade':'OK', 'existing_directory_and_work_preserved':'OK',
                'running_selected_blocks_before_changes':'OK', 'running_unselected_allowed':'OK',
                'individual_failure_continues':'OK', 'independent_repair_and_uninstall':'OK'}))
        finally:
            close_runtime()
            for product in PRODUCTS:
                uninstall(product)
            # Keep logs for diagnosing CI; only sandbox data, never operator files.
            import shutil
            shutil.copytree(sandbox/'logs', BUNDLE/'build/test-logs', dirs_exist_ok=True)
        assert all(installed(product) is None for product in PRODUCTS)
        assert all(not (programs/'RedLab Editor'/(name+'.lnk')).exists() for _, name, _ in PRODUCTS.values())
        print('Uninstall: OK; no fourth application registered.')


if __name__ == '__main__':
    main()

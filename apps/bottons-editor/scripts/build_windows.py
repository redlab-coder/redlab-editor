"""Build portable EXE, per-user installer, update manifest and checksums."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION, REPOSITORY, PRODUCT_ID, RELEASE_PREFIX


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-exe', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    if os.name != 'nt':
        raise SystemExit('Compile os binários no Windows.')
    if not args.skip_exe:
        from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
        numbers = tuple(map(int, VERSION.split('.'))) + (0,)
        info = VSVersionInfo(ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[StringFileInfo([StringTable('041604B0', [StringStruct('CompanyName', 'RedLab'), StringStruct('FileDescription', 'Bottons Editor — Montagem de bottons'), StringStruct('FileVersion', VERSION), StringStruct('ProductName', 'Bottons Editor'), StringStruct('ProductVersion', VERSION), StringStruct('OriginalFilename', 'BottonsEditor.exe')])]), VarFileInfo([VarStruct('Translation', [1046, 1200])])])
        resource = ROOT / 'build' / 'version-info.txt'
        resource.parent.mkdir(exist_ok=True)
        resource.write_text(str(info), encoding='utf-8')
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed', '--name', 'BottonsEditor-Portable', '--icon', 'assets/bottons-editor.ico', '--version-file', str(resource), '--add-data', 'ui;ui', '--exclude-module', 'numpy', '--exclude-module', 'psutil', '--exclude-module', 'charset_normalizer', 'app.py'], check=True)
    compiler = Path(os.environ.get('ISCC', ROOT / '.tools' / 'inno' / 'ISCC.exe'))
    subprocess.run([str(compiler), f'/DAppVersion={VERSION}', 'installer/bottons-editor.iss'], check=True)
    setup = ROOT / 'dist' / f'BottonsEditor-Setup-{VERSION}.exe'
    with setup.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'product': PRODUCT_ID, 'version': VERSION, 'url': f'https://github.com/{REPOSITORY}/releases/download/{RELEASE_PREFIX}{VERSION}/{setup.name}', 'sha256': digest, 'size': setup.stat().st_size}
    (ROOT / 'dist' / 'update.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    checksums = []
    for path in (setup, ROOT / 'dist' / 'BottonsEditor-Portable.exe', ROOT / 'dist' / 'update.json'):
        with path.open('rb') as stream:
            checksums.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}')
    (ROOT / 'dist' / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()

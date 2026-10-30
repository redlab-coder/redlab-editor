"""Publish a tested product release and then advance only its update feed."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPOSITORY = 'redlab-coder/redlab-editor'
PRODUCTS = {'bottons-editor': ('BottonsEditor', 'Bottons Editor', 'bottons-v'),
            'polaroid-editor': ('PolaroidEditor', 'Polaroid Editor', 'polaroid-v'),
            'medidas-editor': ('MedidasEditor', 'Medidas Editor', 'medidas-v')}


def gh(*args, body=None):
    command = ['gh', *args]
    if body is not None:
        command += ['--input', '-']
    try:
        return subprocess.check_output(command, input=json.dumps(body).encode() if body is not None else None,
                                       stderr=subprocess.PIPE).decode('utf-8')
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr.decode('utf-8', errors='replace'))
        raise


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}', value):
        raise ValueError('Versão inválida.')
    return tuple(map(int, value.split('.')))


def validate_artifacts(product, tag, directory):
    executable, _, prefix = PRODUCTS[product]
    manifest = json.loads((directory/'update.json').read_text(encoding='utf-8'))
    version_tuple(manifest.get('version'))
    version = manifest['version']
    installer = f'{executable}-Setup-{version}.exe'
    if (manifest.get('product') != product or tag != prefix+version or
            manifest.get('url') != f'https://github.com/{REPOSITORY}/releases/download/{tag}/{installer}'):
        raise ValueError('Produto, tag e origem do instalador devem coincidir.')
    checks = dict((name, digest) for digest, name in
                  (line.split() for line in (directory/'SHA256SUMS.txt').read_text().splitlines()))
    if set(checks) != {installer, executable+'-Portable.exe', 'update.json'}:
        raise ValueError('Conjunto de arquivos inválido.')
    for name, expected in checks.items():
        with (directory/name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('Verificação de integridade falhou: '+name)
    if (manifest.get('sha256') != checks[installer] or type(manifest.get('size')) is not int
            or manifest['size'] != (directory/installer).stat().st_size):
        raise ValueError('Manifesto não corresponde ao instalador.')
    return manifest, checks


def should_advance(current, candidate):
    if current is None:
        return True
    if current.get('product') != candidate['product']:
        raise ValueError('O canal pertence a outro produto.')
    previous, following = version_tuple(current['version']), version_tuple(candidate['version'])
    if following < previous:
        return False
    if following == previous:
        if current != candidate:
            raise ValueError('Uma versão publicada não pode trocar de instalador.')
        return False
    return True


def update_feed(product, manifest):
    path = f'repos/{REPOSITORY}/contents/updates/{product}.json'
    for attempt in range(4):
        # Read the directory first: a missing product feed is expected initially;
        # authorization or network failures must never masquerade as a missing feed.
        entries = json.loads(gh('api', f'repos/{REPOSITORY}/contents/updates'))
        entry = next((entry for entry in entries if entry['name'] == product+'.json'), None)
        previous, sha = None, None
        if entry:
            response = json.loads(gh('api', path))
            previous = json.loads(base64.b64decode(response['content']))
            sha = response['sha']
        if not should_advance(previous, manifest):
            return
        content = json.dumps(manifest, indent=2)+'\n'
        body = {'message': f'Publica canal {product} {manifest["version"]}',
                'content': base64.b64encode(content.encode()).decode(), 'branch': 'main'}
        if sha:
            body['sha'] = sha
        try:
            gh('api', '-X', 'PUT', path, body=body)
            return
        except subprocess.CalledProcessError:
            if attempt == 3:
                raise
            # Two products may advance independently at the same time.
            time.sleep(1+attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('product', choices=PRODUCTS)
    parser.add_argument('tag')
    parser.add_argument('--directory', type=Path, default=Path('dist'))
    args = parser.parse_args()
    manifest, checks = validate_artifacts(args.product, args.tag, args.directory)
    executable, name, _ = PRODUCTS[args.product]
    # A verified tag must contain the same version as the compiled application.
    namespace = {}
    exec((Path('apps')/args.product/'version.py').read_text(encoding='utf-8'), namespace)
    if namespace['VERSION'] != manifest['version'] or namespace['PRODUCT_ID'] != args.product:
        raise ValueError('O código não corresponde aos artefatos.')
    notes = Path('apps')/args.product/'RELEASE_NOTES.md'
    gh('release', 'create', args.tag, '--repo', REPOSITORY, '--verify-tag', '--draft',
       '--title', f'{name} {manifest["version"]}', '--notes-file', str(notes))
    files = [str(args.directory/name) for name in (*checks, 'SHA256SUMS.txt')]
    gh('release', 'upload', args.tag, '--repo', REPOSITORY, *files)
    release = json.loads(gh('release', 'view', args.tag, '--repo', REPOSITORY, '--json', 'assets,isDraft'))
    expected_names = set(checks)|{'SHA256SUMS.txt'}
    if {asset['name'] for asset in release['assets']} != expected_names:
        raise ValueError('Release incompleta.')
    for asset in release['assets']:
        with (args.directory/asset['name']).open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if asset['digest'] != 'sha256:'+digest or asset['state'] != 'uploaded':
            raise ValueError('Arquivo enviado difere do arquivo testado.')
    gh('release', 'edit', args.tag, '--repo', REPOSITORY, '--draft=false', '--latest=false')
    update_feed(args.product, manifest)
    print(f'{name} {manifest["version"]}: release e canal publicados.')


if __name__ == '__main__':
    main()

"""Build an offline suite from verified, independently installable products.

No application is installed by this script. Actual installer checks belong on
an isolated Windows runner (scripts/check_bundle.py).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from publish import PRODUCTS, REPOSITORY, gh, validate_artifacts, version_tuple

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'bundle'
TAG_PREFIX = 'redlab-v'


def package():
    data = json.loads((BUNDLE/'package.json').read_text(encoding='utf-8'))
    version_tuple(data['version'])
    if set(data['products']) != set(PRODUCTS):
        raise ValueError('O pacote deve identificar exatamente os três editores.')
    for version in data['products'].values():
        version_tuple(version)
    return data


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identities(product):
    text = (ROOT/'apps'/product/'installer'/f'{product}.iss').read_text(encoding='utf-8')
    app_id = re.search(r'^AppId=\{(\{[A-F0-9-]{36}\})$', text, re.M).group(1)
    namespace = {}
    exec((ROOT/'apps'/product/'version.py').read_text(encoding='utf-8'), namespace)
    mutexes = [namespace['INSTALLED_MUTEX'], 'Local\\'+PRODUCTS[product][0]+'.Setup.Running']
    if product == 'bottons-editor':
        mutexes.append('Local\\Moldura.Installed.Running')
    return app_id, ','.join(mutexes)


def fetch_inputs(directory):
    """Fetch exact stable releases, never an ambiguous global Latest release."""
    for product, version in package()['products'].items():
        tag = PRODUCTS[product][2]+version
        release = json.loads(gh('api', f'repos/{REPOSITORY}/releases/tags/{tag}'))
        if release['draft'] or release['prerelease']:
            raise ValueError('O pacote exige uma release estável: '+tag)
        destination = directory/product
        destination.mkdir(parents=True, exist_ok=False)
        gh('release', 'download', tag, '--repo', REPOSITORY, '--dir', str(destination))
        validate_artifacts(product, tag, destination)
        expected = set(p.name for p in destination.iterdir())
        if expected != {asset['name'] for asset in release['assets']} or len(expected) != 4:
            raise ValueError('Release de entrada incompleta: '+tag)
        for asset in release['assets']:
            path = destination/asset['name']
            if (asset['state'] != 'uploaded' or asset['size'] != path.stat().st_size
                    or asset.get('digest') != 'sha256:'+digest(path)):
                raise ValueError('Arquivo público não confere: '+asset['name'])


def verified_contents(inputs):
    config = package()
    contents = {'product': 'redlab-editor-bundle', 'version': config['version'], 'products': []}
    for product, version in config['products'].items():
        executable, name, prefix = PRODUCTS[product]
        source = inputs/product
        manifest, _ = validate_artifacts(product, prefix+version, source)
        if manifest['version'] != version:
            raise ValueError('Versão da entrada incorreta: '+product)
        contents['products'].append(dict(id=product, name=name, version=version,
            installer=f'{executable}-Setup-{version}.exe', url=manifest['url'],
            sha256=manifest['sha256'], size=manifest['size']))
    return contents


def generate_inputs(inputs, build):
    contents = verified_contents(inputs)
    build.mkdir(parents=True, exist_ok=True)
    (build/'definitions.iss').write_text('#define BundleVersion "'+contents['version']+'"\n', encoding='utf-8')
    sections = ['[Components]']
    for item in contents['products']:
        sections.append(f'Name: "{item["id"].replace("-", "_")}"; Description: "{item["name"]} {item["version"]}"; Types: full')
    sections += ['', '[Files]']
    for item in contents['products']:
        source = (inputs/item['id']/item['installer']).resolve()
        sections.append(f'Source: "{source}"; Flags: dontcopy')
    sections += ['', '[Code]', 'procedure LoadProducts;', 'begin']
    for index, item in enumerate(contents['products']):
        executable = PRODUCTS[item['id']][0]
        app_id, mutexes = identities(item['id'])
        values = dict(Id=item['id'], Component=item['id'].replace('-', '_'), Name=item['name'], Version=item['version'],
            Installer=item['installer'], Hash=item['sha256'],
            Executable=executable+'.exe', BinaryHash=digest(inputs/item['id']/(executable+'-Portable.exe')),
            RegistryKey='Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\'+app_id+'_is1',
            Mutexes=mutexes)
        for key, value in values.items():
            sections.append(f"  Products[{index}].{key} := '{value.replace(chr(39), chr(39)*2)}';")
    sections += ['end;', '']
    (build/'products.iss').write_text('\n'.join(sections), encoding='utf-8-sig')
    return contents


def build_bundle(inputs):
    if os.name != 'nt':
        raise ValueError('Compile o instalador no Windows.')
    contents = generate_inputs(inputs, BUNDLE/'build')
    compiler = Path(os.environ.get('ISCC', ROOT/'apps/bottons-editor/.tools/inno/ISCC.exe'))
    subprocess.run([str(compiler), str(BUNDLE/'redlab-editor.iss')], check=True)
    directory = BUNDLE/'dist'
    (directory/'contents.json').write_text(json.dumps(contents, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    files = [directory/f'RedlabEditor-Setup-{contents["version"]}.exe', directory/'contents.json']
    (directory/'SHA256SUMS.txt').write_text(''.join(digest(path)+'  '+path.name+'\n' for path in files), encoding='utf-8')
    return contents


def validate_bundle(directory, tag):
    contents = json.loads((directory/'contents.json').read_text(encoding='utf-8'))
    config = package()
    if contents.get('product') != 'redlab-editor-bundle' or contents.get('version') != config['version'] or tag != TAG_PREFIX+config['version']:
        raise ValueError('Identidade, tag ou versão incorreta do pacote.')
    items = contents.get('products', [])
    if len(items) != len(config['products']) or {item['id']: item['version'] for item in items} != config['products']:
        raise ValueError('Conteúdo do pacote incorreto.')
    for item in items:
        executable, name, prefix = PRODUCTS[item['id']]
        installer = f'{executable}-Setup-{item["version"]}.exe'
        url = f'https://github.com/{REPOSITORY}/releases/download/{prefix}{item["version"]}/{installer}'
        if (item['name'] != name or item['installer'] != installer or item['url'] != url
                or not re.fullmatch('[a-f0-9]{64}', item['sha256']) or type(item['size']) is not int or item['size'] <= 0):
            raise ValueError('Origem ou integridade inválida do componente.')
    checks = dict((name, value) for value, name in (line.split() for line in (directory/'SHA256SUMS.txt').read_text().splitlines()))
    if set(checks) != {f'RedlabEditor-Setup-{config["version"]}.exe', 'contents.json'}:
        raise ValueError('Arquivos do pacote incorretos.')
    for name, value in checks.items():
        if digest(directory/name) != value:
            raise ValueError('Integridade inválida: '+name)
    return contents, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'build'))
    parser.add_argument('--inputs', type=Path, default=BUNDLE/'build/inputs')
    args = parser.parse_args()
    if args.action == 'fetch':
        fetch_inputs(args.inputs)
    else:
        print(json.dumps(build_bundle(args.inputs), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

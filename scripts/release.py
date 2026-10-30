"""Prepare consistent release files, or publish a reviewed commit on main.

Preparation previews its diff unless --write is supplied. It does not commit,
tag or publish. The separate publish command creates a new immutable tag only
after verifying a clean checkout and the current remote main.
"""
import argparse
from datetime import datetime, timedelta, timezone
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys

from publish import PRODUCTS, REPOSITORY, version_tuple

ROOT = Path(__file__).resolve().parents[1]


def current_version(root, target):
    if target == 'bundle':
        return json.loads((root/'bundle/package.json').read_text(encoding='utf-8'))['version']
    text = (root/'apps'/target/'version.py').read_text(encoding='utf-8')
    return re.search(r'^VERSION = "([0-9.]+)"$', text, re.M).group(1)


def replace_links(text, target, previous, version):
    executable, _, prefix = PRODUCTS[target] if target != 'bundle' else ('RedlabEditor', '', 'redlab-v')
    text = re.sub(re.escape(prefix+previous)+r'(?![0-9.])', lambda _: prefix+version, text)
    return text.replace(f'{executable}-Setup-{previous}.exe', f'{executable}-Setup-{version}.exe')


def prepend_entry(text, title, notes):
    heading, separator, remainder = text.partition('\n')
    if not separator or not heading.startswith('# '):
        raise ValueError('O changelog precisa manter seu título principal.')
    return heading+'\n\n## '+title+'\n\n'+notes.strip()+'\n\n'+remainder.lstrip()


def prepare(root, target, version, notes, *, included=None, date=None):
    version_tuple(version)
    previous = current_version(root, target)
    if version_tuple(version) <= version_tuple(previous):
        raise ValueError('A nova versão precisa ser maior que a versão atual.')
    if not notes.strip() or re.search(r'\b(TODO|PREENCHER)\b', notes, re.I):
        raise ValueError('Informe notas reais da alteração, sem marcadores pendentes.')
    date = date or datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y')
    changes = {}

    def read(path):
        return (root/path).read_text(encoding='utf-8')

    name = PRODUCTS[target][1] if target != 'bundle' else 'Pacote completo'
    changes[Path('CHANGELOG.md')] = prepend_entry(read('CHANGELOG.md'), name+' '+version+' — '+date, notes)
    changes[Path('README.md')] = replace_links(read('README.md'), target, previous, version)
    if target != 'bundle':
        if included:
            raise ValueError('--include só é válido para o pacote completo.')
        folder = Path('apps')/target
        text = read(folder/'version.py')
        changes[folder/'version.py'] = text.replace('VERSION = "'+previous+'"', 'VERSION = "'+version+'"', 1)
        path = folder/'installer'/f'{target}.iss'
        changes[path] = read(path).replace('#define AppVersion "'+previous+'"', '#define AppVersion "'+version+'"', 1)
        text = replace_links(read(folder/'README.md'), target, previous, version)
        changes[folder/'README.md'] = text.replace('Versão '+previous, 'Versão '+version)
        changes[folder/'RELEASE_NOTES.md'] = '# '+name+' '+version+'\n\n'+notes.strip()+'\n'
        changes[folder/'CHANGELOG.md'] = prepend_entry(read(folder/'CHANGELOG.md'), version+' — '+date, notes)
        # This table describes current source releases; historical migration
        # sections and the fixed bundle composition must remain unchanged.
        text = read('docs/maintenance.md')
        old_tag = PRODUCTS[target][2]+previous
        new_tag = PRODUCTS[target][2]+version
        text = re.sub(r'(^\| '+re.escape(name)+r' \|[^\n]*)'+re.escape(old_tag), lambda match: match[1]+new_tag, text, count=1, flags=re.M)
        changes[Path('docs/maintenance.md')] = text
    else:
        config = json.loads(read('bundle/package.json'))
        config['version'] = version
        old_products = config['products'].copy()
        for product, product_version in (included or {}).items():
            if product not in PRODUCTS:
                raise ValueError('Produto desconhecido: '+product)
            version_tuple(product_version)
            if version_tuple(product_version) < version_tuple(old_products[product]):
                raise ValueError('O novo pacote não deve regredir um componente.')
            config['products'][product] = product_version
        changes[Path('bundle/package.json')] = json.dumps(config, indent=2)+'\n'
        for path in (Path('README.md'), Path('docs/package.md')):
            text = replace_links(changes.get(path, read(path)), target, previous, version)
            text = text.replace('O pacote '+previous, 'O pacote '+version)
            for product, product_version in config['products'].items():
                short_name = PRODUCTS[product][1].removesuffix(' Editor')
                text = text.replace(short_name+' '+old_products[product], short_name+' '+product_version)
            changes[path] = text
        rows = '\n'.join('| '+PRODUCTS[product][1]+' '+product_version+' |' for product, product_version in config['products'].items())
        changes[Path('bundle/RELEASE_NOTES.md')] = ('# RedLab Editor · Pacote completo '+version+'\n\n'+notes.strip()
            +'\n\n| Ferramenta incluída |\n| --- |\n'+rows
            +'\n\nInstalação por usuário, sem administrador, com escolha dos editores e funcionamento offline após o download. '
            +'Cada ferramenta mantém suas atualizações e desinstalação independentes.\n\n'
            +'`contents.json` identifica a composição; `SHA256SUMS.txt` permite conferir o download. '
            +'A validação física de escala e cor do Medidas Editor na Noritsu continua pendente.\n')
        text = read('docs/maintenance.md')
        text = text.replace('O pacote '+previous, 'O pacote '+version)
        changes[Path('docs/maintenance.md')] = replace_links(text, target, previous, version)
    return {path: text for path, text in changes.items() if text != read(path)}


def publish(target):
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('Finalize e integre as alterações antes de publicar: o checkout precisa estar limpo.')
    subprocess.run(['git', 'fetch', 'origin', 'main', '--tags'], cwd=ROOT, check=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    main = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=ROOT, text=True).strip()
    if head != main:
        raise ValueError('Publique a partir do commit atual de origin/main.')
    version = current_version(ROOT, target)
    prefix = 'redlab-v' if target == 'bundle' else PRODUCTS[target][2]
    tag = prefix+version
    existing = subprocess.check_output(['git', 'tag', '--list', tag], cwd=ROOT, text=True).strip()
    if existing:
        raise ValueError('A tag já existe e não será substituída: '+tag)
    # Run all publication contracts before making a tag visible.
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT, check=True)
    if target == 'bundle':
        from bundle import input_plan
        input_plan(require_public=True)
    subprocess.run(['git', 'tag', '-a', tag, '-m', 'Publica '+tag], cwd=ROOT, check=True)
    subprocess.run(['git', 'push', 'origin', 'refs/tags/'+tag], cwd=ROOT, check=True)
    print('Publicação solicitada: '+tag+'. Acompanhe https://github.com/'+REPOSITORY+'/actions')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='action', required=True)
    preparation = subparsers.add_parser('prepare')
    preparation.add_argument('target', choices=(*PRODUCTS, 'bundle'))
    preparation.add_argument('--version', required=True)
    preparation.add_argument('--notes-file', type=Path, required=True)
    preparation.add_argument('--include', action='append', default=[], metavar='PRODUTO=VERSÃO')
    preparation.add_argument('--write', action='store_true')
    publication = subparsers.add_parser('publish')
    publication.add_argument('target', choices=(*PRODUCTS, 'bundle'))
    args = parser.parse_args()
    if args.action == 'publish':
        publish(args.target)
        return
    included = {}
    for item in args.include:
        product, separator, version = item.partition('=')
        if not separator or product in included:
            parser.error('--include deve identificar cada produto uma única vez: produto=versão')
        included[product] = version
    changes = prepare(ROOT, args.target, args.version, args.notes_file.read_text(encoding='utf-8-sig'), included=included)
    for path, text in changes.items():
        if args.write:
            # Write only after the complete plan has passed validation.
            (ROOT/path).write_text(text, encoding='utf-8', newline='\n')
            print('Atualizado: '+path.as_posix())
        else:
            print(''.join(difflib.unified_diff((ROOT/path).read_text(encoding='utf-8').splitlines(True), text.splitlines(True),
                                             fromfile=path.as_posix(), tofile=path.as_posix())), end='')
    print('Preparação concluída; nenhuma publicação foi iniciada.' if args.write else 'Prévia: nenhum arquivo foi alterado. Use --write para aplicar.')


if __name__ == '__main__':
    main()

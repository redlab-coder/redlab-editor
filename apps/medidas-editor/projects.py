"""Portable batches: originals and validated edits in a bounded ZIP container."""
import hashlib
import json
import zipfile
from engine import normalized_settings
from montage import photo_size

MAX_PHOTOS = 100
MAX_FILE = 50 * 1024**2
MAX_TOTAL = 4 * 1024**3


def project_tool(value):
    if value not in ('medidas', 'montagem'):
        raise ValueError('Ferramenta inválida para o lote.')
    return value


def photo_edits(tool, edits):
    if tool == 'medidas':
        return normalized_settings(edits, allow_empty=True)
    if not isinstance(edits, dict):
        raise ValueError('Ajustes de montagem inválidos.')
    return dict(size=photo_size(edits.get('size'), allow_empty=True))


def write_project(stream, records):
    version = 2 if any(meta.get('tool') == 'montagem' for _, meta in records) else 1
    manifest = {'application': 'MedidasEditor', 'format': version, 'photos': []}
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_STORED) as archive:
        for index, (record, meta) in enumerate(records):
            filename = f'photos/{index:04d}.bin'
            with record.original.open('rb') as file:
                digest = hashlib.file_digest(file, 'sha256').hexdigest()
            archive.write(record.original, filename)
            tool = project_tool(meta.get('tool', 'medidas'))
            item = dict(file=filename, sha256=digest, name=meta['name'],
                        edits=photo_edits(tool, meta.get('edits')), reviewed=bool(meta.get('reviewed')),
                        manual=bool(meta.get('manual')))
            if version == 2:
                item.update(tool=tool, selected=meta.get('selected') is True, checked=meta.get('checked') is True)
            manifest['photos'].append(item)
        archive.writestr('project.json', json.dumps(manifest, ensure_ascii=False))


def read_project(stream, make_record):
    staged = []
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_PHOTOS + 1 or len({e.filename for e in entries}) != len(entries):
                raise ValueError('Lote inválido ou com arquivos duplicados.')
            info = archive.getinfo('project.json')
            if info.file_size > 1024**2:
                raise ValueError('Manifesto do lote muito grande.')
            manifest = json.loads(archive.read(info))
            if (not isinstance(manifest, dict) or manifest.get('application') != 'MedidasEditor'
                    or type(manifest.get('format')) is not int or manifest['format'] not in (1, 2)):
                raise ValueError('Este arquivo não é um lote do Medidas Editor compatível.')
            photos = manifest.get('photos')
            if not isinstance(photos, list) or not 1 <= len(photos) <= MAX_PHOTOS:
                raise ValueError('O lote deve conter entre 1 e 100 fotos.')
            if {e.filename for e in entries} != {'project.json'} | {f'photos/{i:04d}.bin' for i in range(len(photos))}:
                raise ValueError('Estrutura do lote inválida.')
            total = 0
            for index, item in enumerate(photos):
                if not isinstance(item, dict) or item.get('file') != f'photos/{index:04d}.bin':
                    raise ValueError('Referência de foto inválida.')
                info = archive.getinfo(item['file'])
                total += info.file_size
                if not 0 < info.file_size <= MAX_FILE or total > MAX_TOTAL or info.flag_bits & 1:
                    raise ValueError('O lote excede os limites de tamanho ou usa criptografia.')
                tool = project_tool(item.get('tool')) if manifest['format'] == 2 else 'medidas'
                edits = photo_edits(tool, item.get('edits'))
                data = archive.read(info)
                if hashlib.sha256(data).hexdigest() != item.get('sha256'):
                    raise ValueError('Uma foto do lote está incompleta ou alterada.')
                name = item.get('name')
                if not isinstance(name, str) or not 1 <= len(name) <= 512:
                    raise ValueError('Nome de foto inválido.')
                meta = dict(name=name, edits=edits, reviewed=bool(item.get('reviewed')), manual=bool(item.get('manual')))
                if manifest['format'] == 2:
                    meta.update(tool=tool, selected=item.get('selected') is True, checked=item.get('checked') is True)
                staged.append((make_record(data), meta))
        return staged
    except Exception as error:
        for record,_ in staged:record._cleanup()
        raise ValueError('Não foi possível abrir este lote do Medidas Editor.') from error

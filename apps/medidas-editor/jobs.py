"""A single export worker, independent item failures and cancellable results."""
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
import unicodedata
import zipfile
from engine import export_jpeg, layout, ExportCancelled


def output_name(name, index):
    stem = unicodedata.normalize('NFC', Path(name.replace('\\', '/')).stem)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', stem).strip(' .')[:90] or 'Foto'
    # Prefix guarantees uniqueness, including Windows reserved names and case.
    return f'{index+1:03d}-{stem}.jpg'


class ExportManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}

    def start(self, records):
        with self.lock:
            if any(job['state'] == 'running' for job in self.jobs.values()):
                raise ValueError('Aguarde ou cancele a exportação em andamento.')
            for key, old in list(self.jobs.items()):
                if time.monotonic()-old['created'] > 3600 or len(self.jobs) >= 3:
                    old['directory'].cleanup(); del self.jobs[key]
            identifier = secrets.token_hex(12)
            directory = tempfile.TemporaryDirectory(prefix='MedidasEditor-export-')
            job = dict(state='running', done=0, total=len(records), percent=0,
                       items=[dict(name=meta['name'], state='queued', error=None) for _, meta in records],
                       success=0, error=None, filename=None, created=time.monotonic(),
                       directory=directory, cancel=threading.Event(), path=None, download_key=secrets.token_urlsafe(24))
            self.jobs[identifier] = job
            thread = threading.Thread(target=self._work, args=(job, records), daemon=True, name='MedidasEditor-export')
            job['thread'] = thread
            thread.start()
            return identifier

    def _work(self, job, records):
        folder = Path(job['directory'].name)
        successful = []
        try:
            for index, (record, meta) in enumerate(records):
                if job['cancel'].is_set():
                    raise ExportCancelled()
                with self.lock:
                    item = job['items'][index]; item['state'] = 'running'; job['percent'] = 0
                path = folder / output_name(meta['name'], index)
                partial = path.with_suffix('.part')
                try:
                    if record is None:
                        raise ValueError('A foto não está mais disponível. Importe novamente.')
                    plan = layout((record.width, record.height), meta['settings'])
                    if (plan['needs_review'] or record.metadata['warnings']) and not meta.get('reviewed'):
                        raise ValueError('Enquadramento ou cor pendente de revisão. Confira a foto antes de exportar.')
                    export_jpeg(record.original, meta['settings'], partial, cancel=job['cancel'],
                                progress=lambda value: self._progress(job, value))
                    partial.replace(path)
                    successful.append(path)
                    with self.lock:
                        item['state'] = 'ready'; job['success'] += 1
                except ExportCancelled:
                    raise
                except Exception as error:
                    partial.unlink(missing_ok=True)
                    message = str(error) if isinstance(error, ValueError) else 'Falha ao processar esta imagem. Confira o arquivo e o espaço temporário.'
                    with self.lock:
                        item.update(state='failed', error=message)
                finally:
                    with self.lock:
                        job['done'] = index+1
            if job['cancel'].is_set():
                raise ExportCancelled()
            if not successful:
                with self.lock:
                    job.update(state='failed', error='Nenhum JPEG foi gerado. Confira os avisos de cada foto.')
                return
            if len(records) == 1:
                result = successful[0]
            else:
                result = folder/'MedidasEditor-fotos.zip'
                with zipfile.ZipFile(result, 'w', zipfile.ZIP_STORED) as archive:
                    for path in successful:
                        if job['cancel'].is_set():
                            raise ExportCancelled()
                        archive.write(path, path.name)
                    failures = [f'{item["name"]}: {item["error"]}' for item in job['items'] if item['state'] == 'failed']
                    if failures:
                        archive.writestr('LEIA-ME-falhas.txt', '\n'.join(failures).encode('utf-8'))
                for path in successful:
                    path.unlink()
            with self.lock:
                if job['cancel'].is_set():
                    raise ExportCancelled()
                job.update(state='ready', path=result, filename=result.name, percent=100)
        except ExportCancelled:
            with self.lock:
                job.update(state='cancelled', error='Exportação cancelada. Nenhum resultado parcial foi disponibilizado.')
                for item in job['items']:
                    if item['state'] in ('running', 'queued'):
                        item['state'] = 'cancelled'
            for path in folder.iterdir():
                if path.is_file():
                    path.unlink(missing_ok=True)
        except Exception:
            with self.lock:
                job.update(state='failed', error='Falha ao finalizar o lote. Confira o espaço em disco e tente novamente.')
            # An incomplete ZIP must not retain copies of all successful JPEGs.
            for path in folder.iterdir():
                try:
                    if path.is_file():
                        path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _progress(self, job, value):
        with self.lock:
            job['percent'] = value

    def status(self, identifier):
        with self.lock:
            job = self.jobs[identifier]
            result = {key: ([item.copy() for item in job[key]] if key == 'items' else job[key])
                      for key in ('state', 'done', 'total', 'percent', 'items', 'success', 'error', 'filename')}
            result['download_url'] = f'/download?job={identifier}&key={job["download_key"]}' if job['state'] == 'ready' else None
            return result

    def cancel(self, identifier):
        with self.lock:
            job = self.jobs[identifier]
            if job['state'] == 'running':
                job['cancel'].set()

    def running(self):
        with self.lock:
            return any(job['state'] == 'running' for job in self.jobs.values())

    def close(self, timeout=15):
        with self.lock:
            jobs = list(self.jobs.values())
            for job in jobs:
                job['cancel'].set()
        deadline = time.monotonic() + timeout
        for job in jobs:
            job['thread'].join(timeout=max(0, deadline-time.monotonic()))
            if not job['thread'].is_alive():
                job['directory'].cleanup()

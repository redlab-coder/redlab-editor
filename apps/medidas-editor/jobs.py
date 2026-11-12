"""A single export worker, independent item failures and cancellable results."""
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
import unicodedata
import zipfile
from engine import choose_sheet, export_jpeg, layout, normalized_settings, ExportCancelled
from montage import export_sheet


def output_name(name, index):
    stem = unicodedata.normalize('NFC', Path(name.replace('\\', '/')).stem)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', stem).strip(' .')[:90] or 'Foto'
    # Prefix guarantees uniqueness, including Windows reserved names and case.
    return f'{index+1:03d}-{stem}.jpg'


class ExportManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}

    def start(self, records, destination=None):
        return self._start(records, self._render_photo, 'MedidasEditor-fotos.zip', destination)

    def start_montage(self, sheets, records, destination=None):
        folders = len({sheet.preset.name for sheet in sheets}) > 1
        tasks = []
        for index, sheet in enumerate(sheets, start=1):
            model = sheet.preset.name
            filename = f'Folha {index:02d}.jpg' if destination or len(sheets) > 1 else f'{model} - Folha 01.jpg'
            tasks.append((sheet, dict(name=f'Folha {index:02d} · {model}', filename=filename,
                                      output_folder=model, archive_name=f'{model}/{filename}' if folders else filename)))

        def render(sheet, meta, path, cancel, progress):
            export_sheet(sheet, records, path, cancel=cancel, progress=progress)

        return self._start(tasks, render, 'MedidasEditor-montagens.zip', destination)

    @staticmethod
    def _render_photo(record, meta, path, cancel, progress):
        if record is None:
            raise ValueError('A foto não está mais disponível. Importe novamente.')
        plan = layout((record.width, record.height), meta['settings'])
        if (plan['needs_review'] or record.metadata['warnings']) and not meta.get('reviewed'):
            raise ValueError('Enquadramento ou cor pendente de revisão. Confira a foto antes de exportar.')
        export_jpeg(record.original, meta['settings'], path, cancel=cancel, progress=progress)

    def _start(self, records, render, zip_name, destination):
        with self.lock:
            if any(job['state'] == 'running' for job in self.jobs.values()):
                raise ValueError('Aguarde ou cancele a exportação em andamento.')
            for key, old in list(self.jobs.items()):
                if time.monotonic()-old['created'] > 3600 or len(self.jobs) >= 3:
                    old['directory'].cleanup(); del self.jobs[key]
            identifier = secrets.token_hex(12)
            directory = tempfile.TemporaryDirectory(prefix='MedidasEditor-export-', ignore_cleanup_errors=True)
            job = dict(state='running', done=0, total=len(records), percent=0,
                       items=[dict(name=meta['name'], state='queued', error=None) for _, meta in records],
                       success=0, error=None, filename=None, folder=None, created=time.monotonic(),
                       directory=directory, cancel=threading.Event(), path=None, download_key=secrets.token_urlsafe(24))
            self.jobs[identifier] = job
            thread = threading.Thread(target=self._work, args=(job, records, render, zip_name, destination),
                                      daemon=True, name='MedidasEditor-export')
            job['thread'] = thread
            thread.start()
            return identifier

    def _work(self, job, records, render, zip_name, destination):
        folder = Path(job['directory'].name)
        successful = []
        try:
            for index, (record, meta) in enumerate(records):
                if job['cancel'].is_set():
                    raise ExportCancelled()
                with self.lock:
                    item = job['items'][index]; item['state'] = 'running'; job['percent'] = 0
                filename = meta.get('filename') or output_name(meta['name'], index)
                path = folder / filename
                partial = path.with_suffix('.part')
                try:
                    progress = lambda value: self._progress(job, value)
                    if destination:
                        output_folder = meta.get('output_folder') or self._measure_folder(meta['settings'])
                        with destination.file(output_folder, filename) as output:
                            render(record, meta, output, job['cancel'], progress)
                            if job['cancel'].is_set():
                                raise ExportCancelled()
                    else:
                        render(record, meta, partial, job['cancel'], progress)
                        partial.replace(path)
                        successful.append((path, meta.get('archive_name', path.name)))
                    with self.lock:
                        item['state'] = 'ready'; job['success'] += 1
                except ExportCancelled:
                    raise
                except Exception as error:
                    message = str(error) if isinstance(error, ValueError) else 'Falha ao processar esta imagem. Confira o arquivo e o espaço temporário.'
                    with self.lock:
                        item.update(state='failed', error=message)
                finally:
                    with self.lock:
                        job['done'] = index+1
            if job['cancel'].is_set():
                raise ExportCancelled()
            if not job['success']:
                with self.lock:
                    job.update(state='failed', error='Nenhum JPEG foi gerado. Confira os avisos de cada foto.')
                return
            if destination:
                with self.lock:
                    job.update(state='ready', folder=destination.result(), percent=100)
                return
            if len(records) == 1:
                result = successful[0][0]
            else:
                result = folder/zip_name
                with zipfile.ZipFile(result, 'w', zipfile.ZIP_STORED) as archive:
                    for path, archive_name in successful:
                        if job['cancel'].is_set():
                            raise ExportCancelled()
                        archive.write(path, archive_name)
                    failures = [f'{item["name"]}: {item["error"]}' for item in job['items'] if item['state'] == 'failed']
                    if failures:
                        archive.writestr('LEIA-ME-falhas.txt', '\n'.join(failures).encode('utf-8'))
                for path, _ in successful:
                    path.unlink()
            with self.lock:
                if job['cancel'].is_set():
                    raise ExportCancelled()
                job.update(state='ready', path=result, filename=result.name, percent=100)
        except ExportCancelled:
            with self.lock:
                job.update(state='cancelled', folder=destination.result() if destination else None,
                           error='Exportação cancelada.')
                for item in job['items']:
                    if item['state'] in ('running', 'queued'):
                        item['state'] = 'cancelled'
        except Exception:
            with self.lock:
                job.update(state='failed', error='Falha ao finalizar o lote. Confira o espaço em disco e tente novamente.')
        finally:
            # Release encoder exceptions before removing files on Windows.
            keep = job['path']
            try:
                for path in folder.iterdir():
                    if path != keep and path.is_file():
                        try:
                            path.unlink(missing_ok=True)
                        except OSError:
                            pass  # The job's temporary directory retries cleanup when closed.
            except OSError:
                pass

    @staticmethod
    def _measure_folder(settings):
        settings = normalized_settings(settings)
        width, height = settings['width_cm'], settings['height_cm']
        sheet = choose_sheet(width, height, settings['sheet'])
        measure = f'{width}x{height}'.replace('.', ',')
        return f'{sheet["id"]} ({measure})'

    def _progress(self, job, value):
        with self.lock:
            job['percent'] = value

    def status(self, identifier):
        with self.lock:
            job = self.jobs[identifier]
            result = {key: ([item.copy() for item in job[key]] if key == 'items' else job[key])
                      for key in ('state', 'done', 'total', 'percent', 'items', 'success', 'error', 'filename', 'folder')}
            result['download_url'] = f'/download?job={identifier}&key={job["download_key"]}' if job['state'] == 'ready' and job['path'] else None
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

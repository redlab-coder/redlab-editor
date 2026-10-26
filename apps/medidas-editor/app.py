"""Local desktop service: immutable originals, interactive proxies and jobs."""
import argparse
import io
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote, quote, parse_qs
from PIL import Image, UnidentifiedImageError
from engine import FORMATS, layout, normalized_settings, proportional_size, cm_text, render_preview
from photo_store import PhotoRecord, PhotoCache, MAX_FILE, MAX_PHOTOS, MAX_TOTAL
from projects import read_project, write_project
from jobs import ExportManager
from desktop import SingleInstance, run_tray
from updater import Updater, installed_directory
from version import VERSION, PORTABLE_NAMESPACE, INSTALLED_NAMESPACE, INSTALLED_MUTEX

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
TOKEN = secrets.token_urlsafe(24)
INSTANCE = secrets.token_hex(16)
IMAGES = {}
LOCK = threading.RLock()
CACHE = PhotoCache()
EXPORTS = ExportManager()
LAST_ACTIVE = time.monotonic()


def photo_response(identifier, photo):
    record = photo['record']
    return dict(id=identifier, name=photo['name'], width=record.width, height=record.height,
                metadata=record.metadata)


def snapshots(items, allow_missing=False):
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_PHOTOS:
        raise ValueError('Selecione entre 1 e 100 fotos.')
    result = []
    with LOCK:
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                raise ValueError('Lista de fotos inválida.')
            photo = IMAGES.get(item['id'])
            if photo is None and not allow_missing:
                raise ValueError('A foto não está mais disponível. Importe novamente.')
            result.append((photo['record'] if photo else None,
                           dict(name=photo['name'] if photo else str(item.get('name', 'Foto'))[:512],
                                settings=item.get('settings', {}), reviewed=item.get('reviewed') is True)))
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if not getattr(sys, 'frozen', False):
            super().log_message(format, *args)

    def reply(self, data, content_type='application/json', status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(data)

    def json_reply(self, value, status=200):
        self.reply(json.dumps(value, ensure_ascii=False).encode(), status=status)

    def send_file(self, stream, filename, content_type):
        stream.seek(0, 2); size = stream.tell(); stream.seek(0)
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Content-Disposition', "attachment; filename*=UTF-8''"+quote(filename, safe=''))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        while chunk := stream.read(256*1024):
            self.wfile.write(chunk)

    def authorized_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.authorized_host():
            return self.json_reply({'error':'Acesso inválido.'}, 403)
        path = urlparse(self.path).path
        if path == '/health':
            return self.json_reply(dict(product='Medidas Editor', version=VERSION, instance=INSTANCE, pid=os.getpid()))
        if path == '/download':
            query = parse_qs(urlparse(self.path).query)
            with EXPORTS.lock:
                job = EXPORTS.jobs.get(query.get('job', [''])[0])
                supplied = query.get('key', [''])[0]
                if (job is None or job['state'] != 'ready' or not supplied.isascii()
                        or not hmac.compare_digest(supplied, job['download_key'])):
                    return self.json_reply({'error':'Download indisponível.'}, 403)
                try:
                    stream = job['path'].open('rb')
                except OSError:
                    return self.json_reply({'error':'O resultado não está mais disponível.'}, 404)
                filename = job['filename']
            try:
                with stream:
                    self.send_file(stream, filename, 'image/jpeg' if filename.endswith('.jpg') else 'application/zip')
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if path == '/':
            html = (ROOT/'ui/index.html').read_text(encoding='utf-8')
            html = html.replace('__TOKEN__', TOKEN).replace('__VERSION__', VERSION).replace('__FORMATS__', json.dumps(FORMATS, ensure_ascii=False))
            return self.reply(html.encode(), 'text/html; charset=utf-8')
        if path in ('/app.js', '/icons.js', '/style.css'):
            return self.reply((ROOT/'ui'/path[1:]).read_bytes(), 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
        if path == '/favicon.ico':
            from desktop import icon_image
            output = io.BytesIO(); icon_image().save(output, 'ICO')
            return self.reply(output.getvalue(), 'image/x-icon')
        return self.json_reply({'error':'Não encontrado.'}, 404)

    def do_POST(self):
        global LAST_ACTIVE
        origin = self.headers.get('Origin')
        if (not self.authorized_host() or self.headers.get('X-MedidasEditor-Token') != TOKEN or
                origin and origin != f'http://127.0.0.1:{self.server.server_port}'):
            return self.json_reply({'error':'Acesso inválido.'}, 403)
        LAST_ACTIVE = time.monotonic()
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = MAX_TOTAL+2*1024**2 if path == '/api/project/open' else MAX_FILE if path == '/api/upload' else 1024**2
            if length < 0 or length > limit:
                raise ValueError('O arquivo ou a solicitação excede o limite permitido.')
            if path == '/api/project/open':
                if EXPORTS.running():
                    raise ValueError('Aguarde a exportação terminar.')
                with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as stream:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(remaining, 256*1024))
                        if not chunk:
                            raise ValueError('O envio do lote foi interrompido.')
                        stream.write(chunk); remaining -= len(chunk)
                    stream.seek(0)
                    with CACHE.lock:
                        staged = read_project(stream, PhotoRecord)
                        replacement, response = {}, []
                        for record, meta in staged:
                            identifier = secrets.token_hex(12)
                            photo = dict(record=record, name=meta['name'])
                            replacement[identifier] = photo
                            response.append(dict(**photo_response(identifier, photo), settings=meta['edits'], reviewed=meta['reviewed']))
                        with LOCK:
                            IMAGES.clear(); IMAGES.update(replacement)
                        CACHE.clear()
                return self.json_reply({'photos':response})
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('O envio foi interrompido.')
            if path == '/api/upload':
                name = unquote(self.headers.get('X-Filename', 'Foto'))[:512]
                with CACHE.lock:
                    with LOCK:
                        if len(IMAGES) >= MAX_PHOTOS or sum(p['record'].bytes for p in IMAGES.values())+length > MAX_TOTAL:
                            raise ValueError('O lote aceita até 100 fotos e 4 GB de originais.')
                    record = PhotoRecord(body)
                    identifier = secrets.token_hex(12); photo = dict(record=record, name=name)
                    with LOCK:
                        IMAGES[identifier] = photo
                return self.json_reply(photo_response(identifier, photo))
            data = json.loads(body or b'{}')
            if not isinstance(data, dict):
                raise ValueError('Solicitação inválida.')
            if path == '/api/heartbeat':
                updater = getattr(self.server, 'updater', None)
                return self.json_reply(dict(version=VERSION, update=updater.snapshot() if updater else {'state':'disabled'}))
            if path == '/api/quit':
                if EXPORTS.running():
                    raise ValueError('Cancele ou aguarde a exportação antes de encerrar.')
                self.json_reply({'ok':True})
                threading.Thread(target=getattr(self.server, 'request_shutdown', self.server.shutdown), daemon=True).start()
                return
            if path in ('/api/delete', '/api/clear'):
                ids = [data['id']] if path.endswith('/delete') else data.get('ids')
                if not isinstance(ids, list) or len(ids) > MAX_PHOTOS or any(not isinstance(key, str) for key in ids):
                    raise ValueError('Lista de fotos inválida.')
                with LOCK:
                    removed = [IMAGES.pop(key) for key in dict.fromkeys(ids) if key in IMAGES]
                for photo in removed:
                    CACHE.discard(photo['record'])
                return self.json_reply({'ok':True})
            if path == '/api/project/save':
                records = snapshots(data['items'])
                portable = [(record, dict(name=meta['name'], edits=meta['settings'], reviewed=meta['reviewed'], manual=False)) for record, meta in records]
                with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as stream:
                    write_project(stream, portable)
                    self.send_file(stream, 'Meu lote.medidas', 'application/zip')
                return
            if path == '/api/export/start':
                return self.json_reply({'job':EXPORTS.start(snapshots(data['items'], allow_missing=True))})
            if path == '/api/export/status':
                return self.json_reply(EXPORTS.status(data['job']))
            if path == '/api/export/cancel':
                EXPORTS.cancel(data['job'])
                return self.json_reply({'ok':True})
            if path == '/api/export/download':
                with EXPORTS.lock:
                    job = EXPORTS.jobs[data['job']]
                    if job['state'] != 'ready':
                        raise ValueError('A exportação ainda não está pronta.')
                    stream = job['path'].open('rb'); filename = job['filename']
                with stream:
                    self.send_file(stream, filename, 'image/jpeg' if filename.endswith('.jpg') else 'application/zip')
                return
            with LOCK:
                record = IMAGES[data['id']]['record']
            if path == '/api/source':
                return self.reply(record.proxy.read_bytes(), 'image/png')
            if path == '/api/thumbnail':
                with CACHE.lock:
                    image = CACHE.get(record).copy()
                    image.thumbnail((128,128), Image.Resampling.LANCZOS)
                    output = io.BytesIO(); image.save(output, 'PNG'); image.close()
                return self.reply(output.getvalue(), 'image/png')
            if path == '/api/measure':
                width, height = proportional_size(data.get('width_cm'), data.get('height_cm'), (record.width, record.height))
                settings = dict(data.get('settings') or {}, width_cm=cm_text(width), height_cm=cm_text(height), cx=.5, cy=.5, zoom=1.)
                return self.json_reply(layout((record.width, record.height), settings))
            if path == '/api/plan':
                return self.json_reply(layout((record.width, record.height), data.get('settings')))
            if path == '/api/preview':
                with CACHE.lock:
                    image, plan = render_preview(CACHE.get(record), (record.width, record.height), data.get('settings'))
                    output = io.BytesIO()
                    try:
                        image.save(output, 'PNG')
                    finally:
                        image.close()
                return self.reply(output.getvalue(), 'image/png')
            return self.json_reply({'error':'Não encontrado.'}, 404)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, UnidentifiedImageError,
                OSError, Image.DecompressionBombError, zipfile.BadZipFile) as error:
            message = str(error) if isinstance(error, ValueError) else 'Não foi possível processar o arquivo ou a solicitação.'
            return self.json_reply({'error':message}, 400)
        except (BrokenPipeError, ConnectionResetError):
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--no-tray', action='store_true')
    parser.add_argument('--isolated', action='store_true', help='Instância separada apenas para testes.')
    parser.add_argument('--no-updates', action='store_true', help='Não consultar atualizações nesta execução.')
    args = parser.parse_args()
    install_dir = installed_directory() if not args.isolated else None
    instance = None if args.isolated else SingleInstance(INSTALLED_NAMESPACE if install_dir else PORTABLE_NAMESPACE, mutex_name=INSTALLED_MUTEX if install_dir else None)
    if instance and not instance.owner:
        existing = instance.existing_url()
        instance.close()
        if existing:
            if not args.no_browser:
                webbrowser.open(existing)
            if sys.stdout:
                print(existing, flush=True)
        elif sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'O Medidas Editor já está iniciando ou encerrando. Aguarde alguns segundos e tente novamente.', 'Medidas Editor', 0x40)
        return
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        if instance:
            instance.close()
        raise
    server.daemon_threads = True
    updates = None
    if install_dir and not args.no_updates:
        try:
            updates = Updater(install_dir)
            updates.start()
        except OSError:
            pass  # An update failure must never prevent local editing.
    server.updater = updates
    url = f'http://127.0.0.1:{server.server_port}'
    if instance:
        instance.publish(url, INSTANCE)
    stopped = threading.Event()
    shutdown_lock = threading.Lock()
    diagnostic = None
    if os.environ.get('MEDIDAS_EDITOR_TEST_TRACE'):
        import faulthandler
        diagnostic = open(os.environ['MEDIDAS_EDITOR_TEST_TRACE'], 'w')
        faulthandler.enable(file=diagnostic)
    tray = None
    def request_shutdown():
        with shutdown_lock:
            if stopped.is_set():
                return
            stopped.set()
        if diagnostic:
            faulthandler.dump_traceback_later(8, file=diagnostic)
        server.shutdown()
        if tray:
            tray.stop()
    server.request_shutdown = request_shutdown
    if sys.platform == 'win32' and not args.no_tray:
        tray = run_tray(url, request_shutdown, lambda: bool(IMAGES), updates)
    if not args.no_browser:
        webbrowser.open(url)
    if sys.stdout:
        print(url, flush=True)
    # With a tray icon, the session deliberately stays available until explicit exit.
    if not tray:
        def idle_monitor():
            while not stopped.wait(20):
                if not EXPORTS.running() and time.monotonic() - LAST_ACTIVE > 300:
                    request_shutdown()
                    return
        threading.Thread(target=idle_monitor, daemon=True).start()
    try:
        if tray:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                tray.run()
            finally:
                request_shutdown()
                thread.join(timeout=5)
        else:
            server.serve_forever()
    finally:
        server.server_close()
        with LOCK:
            IMAGES.clear()
        EXPORTS.close()
        CACHE.clear()
        if instance:
            instance.close()
        if updates:
            updates.install_on_exit()


if __name__ == '__main__':
    main()

"""Loopback-only desktop companion. No cloud or external assets."""
import argparse
import os
import io
import json
import secrets
import sys
import threading
import tempfile
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from PIL import UnidentifiedImageError, Image
from engine import render_tile, jpeg_bytes, template_info, TEMPLATES
from layout import plan_pages, compose_sheet
from projects import read_project, write_project, normalized_edits, MAX_FILE, MAX_TOTAL
from desktop import SingleInstance, run_tray, clear_session
from photo_store import PhotoRecord, PhotoCache
from updater import Updater, installed_directory
from recovery import CheckpointStore, UpdateSession, UpdateBusy
from version import VERSION, PORTABLE_NAMESPACE, INSTALLED_NAMESPACE, INSTALLED_MUTEX

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
TOKEN = secrets.token_urlsafe(24)
INSTANCE = secrets.token_hex(16)
IMAGES = {}
LOCK = threading.Lock()
LAST_ACTIVE = time.monotonic()
CACHE = PhotoCache()
MAX_STORAGE = 4 * 1024**3


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if not getattr(sys, 'frozen', False):
            super().log_message(format, *args)

    def check_open(self):
        if getattr(self.server, 'closing', threading.Event()).is_set():
            raise ValueError('O editor está encerrando.')

    def reply(self, data, content_type='application/json', status=200, filename=None):
        if content_type in ('image/jpeg', 'application/zip'):
            self.check_open()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def json_reply(self, value, status=200):
        self.reply(json.dumps(value, ensure_ascii=False).encode(), status=status)

    def authorized_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.authorized_host():
            return self.json_reply({'error': 'Acesso inválido.'}, 403)
        path = urlparse(self.path).path
        if path == '/health':
            return self.json_reply({'product': 'Bottons Editor', 'instance': INSTANCE, 'pid': __import__('os').getpid(), 'version': VERSION})
        if path == '/':
            html = (ROOT / 'ui' / 'index.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN)
            html = html.replace('__VERSION__', VERSION)
            html = html.replace('__TEMPLATES__', json.dumps({key: template_info(key) for key in TEMPLATES}, ensure_ascii=False))
            return self.reply(html.encode(), 'text/html; charset=utf-8')
        if path in ('/app.js', '/icons.js', '/update.js', '/style.css'):
            return self.reply((ROOT / 'ui' / path[1:]).read_bytes(), 'text/javascript; charset=utf-8' if path.endswith('js') else 'text/css; charset=utf-8')
        if path == '/favicon.ico':
            from desktop import icon_image
            output = io.BytesIO()
            icon_image().save(output, 'ICO')
            return self.reply(output.getvalue(), 'image/x-icon')
        self.json_reply({'error': 'Não encontrado.'}, 404)

    def update_records(self,items):
        if not isinstance(items,list) or len(items)>100:raise ValueError('Lote inválido.')
        if not items:return []
        plan_pages(items)
        with LOCK:
            return [(IMAGES[item['id']]['record'],dict(name=IMAGES[item['id']].get('name','Foto'),edits=normalized_edits(item.get('edits',{})),template=item.get('template','square'))) for item in items]

    def update_api(self,path,data):
        session=getattr(self.server,'update_session',None)
        if not session:
            return self.json_reply({} if path=='/api/update/recovery' else {'error':'Atualização indisponível.'},200 if path=='/api/update/recovery' else 400)
        if path=='/api/update/recovery':
            with session.load_lock:
                if not session.loaded:
                    try:
                        recovered=session.store.load() if session.store else None
                        if recovered:
                            response=[];replacement={}
                            for record,meta in recovered.pop('records'):
                                identifier=secrets.token_hex(12)
                                replacement[identifier]=dict(record=record,name=meta['name'])
                                response.append(dict(id=identifier,width=record.width,height=record.height,**meta))
                            with LOCK:
                                IMAGES.clear();IMAGES.update(replacement)
                            recovered['photos']=response;session.recovered=recovered
                    except Exception:
                        session.recovery_error='Não foi possível recuperar o lote automaticamente. A cópia foi preservada em: '+str(session.store.root)
                    session.loaded=True
            return self.json_reply(session.recovered or ({'error':session.recovery_error} if session.recovery_error else {}))
        if path=='/api/update/ack':
            if session.recovered and data.get('generation')==session.recovered['generation']:
                session.store.acknowledge(data['generation']);session.recovered=None
            return self.json_reply({'ok':True})
        if path=='/api/update/apply':
            session.apply(lambda:self.update_records(data.get('items')),data.get('ui',{}),busy=lambda:False)
            self.json_reply({'ok':True})
            threading.Thread(target=self.server.request_shutdown,daemon=True).start()
            return
        return self.json_reply({'error':'Não encontrado.'},404)

    def do_POST(self):
        session=getattr(self.server,'update_session',None);counted=False
        try:
            if session:counted=session.enter(urlparse(self.path).path)
            return self.handle_POST()
        except UpdateBusy as error:
            return self.json_reply({'error':str(error)},409)
        finally:
            if counted:session.leave()

    def handle_POST(self):
        global LAST_ACTIVE
        origin = self.headers.get('Origin')
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if not self.authorized_host() or self.headers.get('X-BottonsEditor-Token') != TOKEN or (origin and origin != expected):
            return self.json_reply({'error': 'Acesso inválido.'}, 403)
        LAST_ACTIVE = time.monotonic()
        path = urlparse(self.path).path
        if getattr(self.server, 'closing', threading.Event()).is_set():
            return self.json_reply({'error': 'O editor está encerrando.'}, 503)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = MAX_TOTAL+2*1024**2 if path=='/api/project/open' else MAX_FILE if path=='/api/upload' else 1024**2
            if length < 0 or length > limit:
                raise ValueError('O arquivo ou a solicitação excede o limite permitido.')
            if path == '/api/project/open':
                with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as stream:
                    remaining=length
                    while remaining:
                        chunk=self.rfile.read(min(remaining,256*1024))
                        if not chunk:raise ValueError('O envio do lote foi interrompido.')
                        stream.write(chunk);remaining-=len(chunk)
                    stream.seek(0)
                    with CACHE.lock:
                        staged=read_project(stream,PhotoRecord)
                        replacement,response={},[]
                        for record,meta in staged:
                            id_=secrets.token_hex(12);replacement[id_]=dict(record=record,name=meta['name'])
                            response.append(dict(id=id_,width=record.width,height=record.height,**meta))
                        self.check_open()
                        with LOCK:
                            IMAGES.clear();IMAGES.update(replacement)
                        CACHE.clear()
                return self.json_reply(dict(photos=response))
            body = self.rfile.read(length)
            if path == '/api/upload':
                with CACHE.lock:
                    with LOCK:
                        self.check_capacity(length)
                    CACHE.clear()
                    record = PhotoRecord(body)
                    with LOCK:
                        self.check_capacity(length)
                        id_ = secrets.token_hex(12)
                        name=unquote(self.headers.get('X-Filename','Foto'))[:512] or 'Foto'
                        IMAGES[id_] = {'record': record,'name':name}
                return self.json_reply({'id': id_, 'width': record.width, 'height': record.height, 'name': name})
            payload = json.loads(body or b'{}')
            if not isinstance(payload, dict):
                raise ValueError('Solicitação inválida.')
            if path == '/api/templates':
                return self.json_reply([template_info(key) for key in TEMPLATES])
            if path.startswith('/api/update/'):
                return self.update_api(path,payload)
            if path == '/api/heartbeat':
                updates = getattr(self.server, 'updater', None)
                return self.json_reply({'ok': True, 'version': VERSION, 'update': updates.snapshot() if updates else {'state': 'disabled', 'version': None}})
            if path == '/api/quit':
                self.json_reply({'ok': True})
                stop = getattr(self.server, 'request_shutdown', self.server.shutdown)
                threading.Thread(target=stop, daemon=True).start()
                return
            if path == '/api/delete':
                with LOCK:
                    removed = IMAGES.pop(payload['id'], None)
                if removed:
                    CACHE.discard(removed['record'])
                return self.json_reply({'ok': True})
            if path == '/api/clear':
                ids=payload.get('ids')
                if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(id_,str) for id_ in ids):
                    raise ValueError('Lista de fotos inválida.')
                with LOCK:
                    removed=[IMAGES.pop(id_) for id_ in dict.fromkeys(ids) if id_ in IMAGES]
                for photo in removed:CACHE.discard(photo['record'])
                return self.json_reply({'ok':True,'removed':len(removed)})
            if path in ('/api/preview', '/api/thumbnail'):

                item = payload
                record = self.record(item['id'])
                with CACHE.lock:
                    source = CACHE.get(record)
                    tile = render_tile(source, item.get('edits', {}), item.get('template', 'square'))
                    del source
                if path == '/api/thumbnail':
                    tile.thumbnail((128, 128), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                tile.save(output, 'PNG')
                return self.reply(output.getvalue(), 'image/png')
            if path == '/api/source':
                record = self.record(payload['id'])
                return self.reply(record.live.read_bytes(), 'image/jpeg')
            if path == '/api/layout':
                return self.json_reply(dict(pages=plan_pages(payload.get('items'),payload.get('template','square'))))
            if path in ('/api/sheet', '/api/export', '/api/project/save'):
                items=payload['items'];default=payload.get('template','square')
                plans=plan_pages(items,default)
                with LOCK:
                    records=[(IMAGES[item['id']]['record'],dict(name=IMAGES[item['id']].get('name','Foto'),
                             edits=normalized_edits(item.get('edits',{})),template=item.get('template',default))) for item in items]
                if path == '/api/project/save':
                    with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as output:
                        write_project(output,records)
                        self.send_stream(output,'Meu lote.bottons','application/zip')
                    return
                def compose(plan):
                    tiles=[]
                    try:
                        for index in plan['indices']:
                            self.check_open();record,meta=records[index]
                            with CACHE.lock:
                                tiles.append(render_tile(CACHE.get(record,full=path=='/api/export'),meta['edits'],meta['template']))
                        return compose_sheet(tiles,plan['positions'])
                    finally:
                        for tile in tiles:tile.close()
                if path == '/api/sheet':
                    if len(plans)!=1:raise ValueError('A prévia excede a capacidade da folha.')
                    with compose(plans[0]) as page:
                        page.thumbnail((1000,1000),Image.Resampling.LANCZOS)
                        output=io.BytesIO();page.save(output,'PNG')
                    return self.reply(output.getvalue(),'image/png')
                if len(plans)==1:
                    with compose(plans[0]) as page:data=jpeg_bytes(page)
                    return self.reply(data,'image/jpeg',filename='BottonsEditor-01.jpg')
                with tempfile.SpooledTemporaryFile(max_size=8*1024**2) as output:
                    with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED) as archive:
                        for index,plan in enumerate(plans):
                            with compose(plan) as page:archive.writestr(f'BottonsEditor-{index+1:02}.jpg',jpeg_bytes(page))
                    self.send_stream(output,'BottonsEditor-folhas.zip','application/zip')
                return
            self.json_reply({'error': 'Não encontrado.'}, 404)
        except UpdateBusy as error:
            return self.json_reply({'error':str(error)},409)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            message = str(error) if isinstance(error, ValueError) else 'Não foi possível processar a imagem ou a solicitação. Use JPG, PNG, WebP, BMP ou TIFF.'
            self.json_reply({'error': message}, 400)

    def send_stream(self, stream, filename, content_type):
        self.check_open();size=stream.tell();stream.seek(0)
        self.send_response(200)
        for key,value in [('Content-Type',content_type),('Content-Length',str(size)),
                          ('Content-Disposition',f'attachment; filename="{filename}"'),
                          ('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]:self.send_header(key,value)
        self.end_headers()
        while chunk:=stream.read(256*1024):self.wfile.write(chunk)

    @staticmethod
    def check_capacity(length):
        if len(IMAGES) >= 100:
            raise ValueError('O lote aceita até 100 fotos. Exporte e inicie um novo lote.')
        if sum(value['record'].bytes for value in IMAGES.values()) + length > MAX_STORAGE:
            raise ValueError('O lote atingiu 4 GB de arquivos temporários. Exporte e remova algumas fotos para continuar.')

    def record(self, id_):
        with LOCK:
            return IMAGES[id_]['record']

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
            ctypes.windll.user32.MessageBoxW(None, 'O Bottons Editor já está iniciando ou encerrando. Aguarde alguns segundos e tente novamente.', 'Bottons Editor', 0x40)
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
            updates.restart_no_browser = args.no_browser
            updates.start()
        except OSError:
            pass  # An update failure must never prevent local editing.
    server.updater = updates
    recovery_root=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'BottonsEditor'/'updates'/'recovery'
    store=CheckpointStore(recovery_root,write_project,read_project,PhotoRecord,suffix='.bottons') if install_dir else None
    server.update_session=UpdateSession(updates,store)
    url = f'http://127.0.0.1:{server.server_port}'
    if instance:
        instance.publish(url, INSTANCE)
    stopped = threading.Event()
    shutdown_lock=threading.Lock()
    server.closing = stopped
    tray = None
    def request_shutdown():
        with shutdown_lock:
            if stopped.is_set():
                return
            stopped.set()
        # The tray callback must return to the Windows message loop promptly.
        # Both entry points share this idempotent, asynchronous shutdown path.
        def stop_service():
            try:
                server.shutdown()
            finally:
                if tray:
                    tray.stop()
        threading.Thread(target=stop_service, daemon=True, name='RedLab-shutdown').start()
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
                if time.monotonic() - LAST_ACTIVE > 300:
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
        clear_session(IMAGES, LOCK, CACHE)
        if instance:
            instance.close()
        if updates:
            updates.install_on_exit()


if __name__ == '__main__':
    main()

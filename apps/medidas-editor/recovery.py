"""Crash-safe update checkpoint and exclusion of in-flight API operations."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading


class UpdateBusy(ValueError):
    pass


def ui_state(value):
    if not isinstance(value,dict):raise ValueError('Estado da sessão inválido.')
    result={}
    for key in ('selected_index','template','guides','filter_review','draft_width','draft_height','draft_dirty','checked_indices'):
        if key not in value:continue
        item=value[key]
        if key=='checked_indices':
            if not isinstance(item,list) or len(item)>100 or any(type(i) is not int or not 0<=i<100 for i in item):raise ValueError('Seleção inválida.')
        elif key=='selected_index':
            if type(item) is not int or not -1<=item<100:raise ValueError('Seleção inválida.')
        elif key in ('template','draft_width','draft_height'):
            if not isinstance(item,str) or len(item)>128:raise ValueError('Campo da sessão inválido.')
        elif type(item) is not bool:raise ValueError('Estado da sessão inválido.')
        result[key]=item
    return result


class CheckpointStore:
    def __init__(self,root,writer,reader,make_record,suffix=".project"):
        self.root=Path(root);self.suffix=suffix;self.writer=writer;self.reader=reader;self.make_record=make_record
        self.marker=self.root/'current.json'
    def write(self,records,state):
        state=ui_state(state);self.root.mkdir(parents=True,exist_ok=True)
        generation=secrets.token_hex(12);path=self.root/(generation+self.suffix)
        try:
            with path.open('xb') as stream:
                if records:self.writer(stream,records)
                stream.flush();os.fsync(stream.fileno())
            with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            manifest=dict(generation=generation,sha256=digest,has_photos=bool(records),ui=state)
            temporary=self.marker.with_suffix('.tmp')
            with temporary.open('w',encoding='utf-8') as stream:
                json.dump(manifest,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
            temporary.replace(self.marker)
            return generation
        except Exception:
            path.unlink(missing_ok=True)
            raise
    def load(self):
        if not self.marker.exists():return None
        if self.marker.stat().st_size>65536:raise ValueError('Recuperação inválida.')
        manifest=json.loads(self.marker.read_text(encoding='utf-8'))
        generation=manifest.get('generation')
        if not isinstance(generation,str) or not re.fullmatch('[a-f0-9]{24}',generation):raise ValueError('Recuperação inválida.')
        state=ui_state(manifest.get('ui'))
        path=self.root/(generation+self.suffix)
        if path.stat().st_size>4*1024**3+2*1024**2:raise ValueError('Recuperação excede o limite.')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest.get('sha256'):raise ValueError('A cópia de recuperação está incompleta.')
            stream.seek(0);records=self.reader(stream,self.make_record) if manifest.get('has_photos') is True else []
        return dict(generation=generation,records=records,ui=state)
    def acknowledge(self,generation):
        if not self.marker.exists():return
        current=json.loads(self.marker.read_text(encoding='utf-8'))
        if generation!=current.get('generation'):raise ValueError('A recuperação pertence a outra sessão.')
        # Only generated file names under this product's own checkpoint folder.
        for path in self.root.glob('*'+self.suffix):
            if re.fullmatch('[a-f0-9]{24}',path.stem):path.unlink(missing_ok=True)
        self.marker.unlink(missing_ok=True)


class UpdateSession:
    def __init__(self,updater,store):
        self.updater=updater;self.store=store;self.lock=threading.Lock();self.active=0;self.applying=False
        self.recovered=None;self.recovery_error=None;self.loaded=False;self.load_lock=threading.Lock()
    def enter(self,path):
        if path in ('/api/heartbeat','/api/quit') or path.startswith('/api/update/'):return False
        with self.lock:
            if self.applying:raise UpdateBusy('O editor está preparando a atualização.')
            self.active+=1
        return True
    def leave(self):
        with self.lock:self.active-=1
    def apply(self,records,state,busy=False):
        with self.lock:
            if self.applying or self.active or (busy() if callable(busy) else busy):raise UpdateBusy('Aguardando a operação terminar.')
            self.applying=True
        updater=self.updater;locked=False
        try:
            if not updater:raise ValueError('Atualização automática disponível somente na versão instalada.')
            locked=updater.lock.acquire(blocking=False)
            if not locked:raise UpdateBusy('A atualização está sendo preparada.')
            if not updater.pending or not updater.valid_download(updater.pending):raise ValueError('A atualização ainda não está pronta. Aguarde o download verificado.')
            try:self.store.write(records(),state)
            except OSError as error:raise ValueError('Não foi possível salvar a cópia do lote. Verifique espaço e permissões antes de tentar novamente.') from error
            updater.restart_requested=True;updater.stopped.set()
        except Exception:
            with self.lock:self.applying=False
            raise
        finally:
            if locked:updater.lock.release()

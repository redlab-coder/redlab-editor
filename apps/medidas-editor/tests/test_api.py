import io
import json
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from PIL import Image
import app
from jobs import ExportManager


class ApiTests(unittest.TestCase):
    def setUp(self):
        app.IMAGES.clear();app.CACHE.clear();app.EXPORTS=ExportManager()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close()
        app.EXPORTS.close();app.CACHE.clear();app.IMAGES.clear()

    def api(self,path,data,token=app.TOKEN):
        raw=isinstance(data,bytes)
        request=urllib.request.Request(self.url+'/api/'+path,data=data if raw else json.dumps(data).encode(),headers={
            'X-MedidasEditor-Token':token,'Content-Type':'application/octet-stream' if raw else 'application/json'})
        with urllib.request.urlopen(request) as response:return response.read()

    def upload(self):
        data=io.BytesIO();Image.new('RGB',(300,200),'red').save(data,'PNG')
        return json.loads(self.api('upload',data.getvalue())),data.getvalue()

    def test_auth_validation_preview_and_saved_project(self):
        photo,original=self.upload()
        with self.assertRaises(urllib.error.HTTPError):self.api('plan',{'id':photo['id']},token='wrong')
        with self.assertRaises(urllib.error.HTTPError):self.api('upload',b'invalid photograph')
        plan=json.loads(self.api('measure',dict(id=photo['id'],width_cm='30',height_cm='36')))
        self.assertEqual(plan['sheet']['size_px'],[3602,4724])
        with Image.open(io.BytesIO(self.api('preview',dict(id=photo['id'],settings=plan['settings'])))) as preview:
            self.assertLessEqual(max(preview.size),1000)
        saved=self.api('project/save',dict(items=[dict(id=photo['id'],settings=plan['settings'],reviewed=True)]))
        with zipfile.ZipFile(io.BytesIO(saved)) as archive:self.assertEqual(archive.read('photos/0000.bin'),original)
        restored=json.loads(self.api('project/open',saved))['photos'][0]
        self.assertEqual(restored['settings']['width_cm'],'30');self.assertTrue(restored['reviewed'])
        self.assertEqual(restored['metadata'],photo['metadata'])

    def test_batch_rejects_pending_crop_but_exports_other_photo(self):
        first,_=self.upload();second,_=self.upload()
        job=json.loads(self.api('export/start',dict(items=[
            dict(id=first['id'],settings=dict(width_cm='3',height_cm='3')),
            dict(id=second['id'],settings=dict(width_cm='3',height_cm='3',mode='contain'))])))['job']
        app.EXPORTS.jobs[job]['thread'].join(timeout=30)
        result=json.loads(self.api('export/status',dict(job=job)))
        self.assertEqual(result['state'],'ready');self.assertEqual(result['success'],1)
        output=self.api('export/download',dict(job=job))
        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            self.assertEqual(len([n for n in archive.namelist() if n.endswith('.jpg')]),1)
            self.assertIn('LEIA-ME-falhas.txt',archive.namelist())

    def test_clear_is_atomic_and_originals_remain_for_snapshots(self):
        photo,original=self.upload();record=app.IMAGES[photo['id']]['record']
        with self.assertRaises(urllib.error.HTTPError):self.api('clear',dict(ids=[photo['id'],None]))
        self.assertIn(photo['id'],app.IMAGES)
        self.api('clear',dict(ids=[photo['id']]))
        self.assertFalse(app.IMAGES);self.assertEqual(record.original.read_bytes(),original)

import io
import json
import threading
import unittest
import urllib.request
import urllib.error
import zipfile
from unittest.mock import patch
from unittest.mock import Mock
from http.server import ThreadingHTTPServer
from PIL import Image
import app


class ApiTests(unittest.TestCase):
    def test_clear_validates_all_ids_before_mutation_and_preserves_other_photos(self):
        data=io.BytesIO();Image.new('RGB',(120,100),'blue').save(data,'PNG')
        with self.request('upload',data.getvalue(),True) as response:first=json.load(response)['id']
        with self.request('upload',data.getvalue(),True) as response:second=json.load(response)['id']
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:self.request('clear',{'ids':[first,None]})
            caught.exception.close();self.assertIn(first,app.IMAGES);self.assertIn(second,app.IMAGES)
            with self.request('clear',{'ids':[first,first,'missing']}) as response:self.assertEqual(json.load(response)['removed'],1)
            self.assertNotIn(first,app.IMAGES);self.assertIn(second,app.IMAGES)
        finally:
            with self.request('clear',{'ids':[first,second]}):pass
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def request(self,path,data,raw=False,token=app.TOKEN,origin=None):
        headers={'X-BottonsEditor-Token':token,'Content-Type':'application/octet-stream' if raw else 'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+'/api/'+path,data=data if raw else json.dumps(data).encode(),headers=headers)
        return urllib.request.urlopen(req)

    def test_version_and_update_status_are_available_without_affecting_session(self):
        with urllib.request.urlopen(self.url) as response:
            html=response.read().decode()
        self.assertIn('v'+app.VERSION,html)
        self.assertNotIn('__VERSION__',html)
        with self.request('heartbeat',{}) as response:
            state=json.load(response)
        self.assertEqual(state['version'],app.VERSION)
        self.assertEqual(state['update']['state'],'disabled')
        self.server.updater=Mock(snapshot=Mock(return_value={'state':'ready','version':'1.1.0'}))
        try:
            with self.request('heartbeat',{}) as response:
                self.assertEqual(json.load(response)['update'],{'state':'ready','version':'1.1.0'})
        finally:del self.server.updater

    def test_full_three_photo_export_and_delete(self):
        items=[]
        for color in ('red','green','blue'):
            stream=io.BytesIO();Image.new('RGB',(800,1100),color).save(stream,'PNG')
            with self.request('upload',stream.getvalue(),True) as response:photo=json.load(response)
            items.append({'id':photo['id'],'edits':{'zoom':1.2,'brightness':1.1}})
        with self.request('preview',items[0]) as response:
            self.assertEqual(Image.open(io.BytesIO(response.read())).size,(827,827))
        with self.request('source',{'id':items[0]['id']}) as response:
            self.assertEqual(Image.open(io.BytesIO(response.read())).size,(800,1100))
        with self.request('sheet',{'items':items[:2]}) as response:
            self.assertEqual(Image.open(io.BytesIO(response.read())).size,(1000,671))
        with self.request('export',{'items':items}) as response:
            archive=zipfile.ZipFile(io.BytesIO(response.read()))
            self.assertEqual(archive.namelist(),['BottonsEditor-01.jpg','BottonsEditor-02.jpg'])
            for filename in archive.namelist():
                image=Image.open(io.BytesIO(archive.read(filename)))
                self.assertEqual(image.size,(1795,1205));self.assertEqual(image.info['dpi'],(300,300))
            last=Image.open(io.BytesIO(archive.read('BottonsEditor-02.jpg')))
            self.assertGreater(last.getpixel((897,602))[2],240)
            self.assertEqual(last.getpixel((200,602)),(255,255,255))
        with self.request('export',{'items':items[:1]}) as response:
            self.assertEqual(response.headers['Content-Type'],'image/jpeg')
        for item in items:
            with self.request('delete',{'id':item['id']}) as response:self.assertTrue(json.load(response)['ok'])

    def test_invalid_input_and_access_rejected(self):
        for path,data,raw,token,origin,status in [
            ('upload',b'not an image',True,app.TOKEN,None,400),
            ('export',{'items':[]},False,app.TOKEN,None,400),
            ('heartbeat',{},False,'invalid',None,403),
            ('heartbeat',{},False,app.TOKEN,'https://other.example',403),
            ('heartbeat',[],False,app.TOKEN,None,400),
            ('preview',{'id':'missing'},False,app.TOKEN,None,400),
            ('export',{'items':[{'id':'missing'}],'template':'invalid'},False,app.TOKEN,None,400),
        ]:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(path,data,raw,token,origin)
            self.assertEqual(caught.exception.code,status)
            caught.exception.close()

    def test_small_round_six_per_page_and_overflow(self):
        stream=io.BytesIO();Image.new('RGB',(1000,800),'red').save(stream,'PNG')
        with self.request('upload',stream.getvalue(),True) as response:photo=json.load(response)
        item={'id':photo['id'],'edits':{}}
        try:
            with self.request('templates',{}) as response:models=json.load(response)
            self.assertEqual([m['capacity'] for m in models],[2,2,2,6])
            for count,expected_type in [(6,'image/jpeg'),(7,'application/zip')]:
                with self.request('export',{'items':[item]*count,'template':'round_p'}) as response:
                    self.assertEqual(response.headers['Content-Type'],expected_type)
                    data=response.read()
                if count==7:
                    archive=zipfile.ZipFile(io.BytesIO(data));self.assertEqual(len(archive.namelist()),2)
                    page=Image.open(io.BytesIO(archive.read('BottonsEditor-02.jpg')))
                    self.assertGreater(page.getpixel((897,602))[0],240)
                    self.assertLess(page.getpixel((897,602))[1],10)
            with self.request('sheet',{'items':[item]*6,'template':'round_p'}) as response:
                self.assertEqual(Image.open(io.BytesIO(response.read())).size,(1000,671))
        finally:
            with self.request('delete',{'id':photo['id']}):pass

    def test_export_keeps_sources_if_removed_during_processing(self):
        stream=io.BytesIO();Image.new('RGB',(100,100),'blue').save(stream,'PNG')
        with self.request('upload',stream.getvalue(),True) as response:photo=json.load(response)
        original_render=app.render_tile
        def remove_then_render(source,edits,template):
            with app.LOCK:app.IMAGES.pop(photo['id'],None)
            return original_render(source,edits,template)
        with patch('app.render_tile',side_effect=remove_then_render):
            with self.request('export',{'items':[{'id':photo['id']}]*7,'template':'round_p'}) as response:
                archive=zipfile.ZipFile(io.BytesIO(response.read()))
                self.assertEqual(len(archive.namelist()),2)

    def test_mixed_sheet_and_project_roundtrip_use_identical_composition(self):
        items=[]
        for key,color in [('square','red'),('round_p','green'),('round_p','blue')]:
            stream=io.BytesIO();Image.new('RGB',(800,800),color).save(stream,'PNG')
            with self.request('upload',stream.getvalue(),True) as response:photo=json.load(response)
            items.append(dict(id=photo['id'],template=key,edits={}))
        with self.request('layout',dict(items=items)) as response:plan=json.load(response)['pages']
        self.assertEqual(len(plan),1)
        with self.request('export',dict(items=items)) as response:
            image=Image.open(io.BytesIO(response.read()));image.load()
            self.assertEqual(image.size,(1795,1205));self.assertEqual(image.info['dpi'],(300,300))
            colors=[(255,0,0),(0,128,0),(0,0,255)]
            from engine import template_info
            for index,(x,y) in zip(plan[0]['indices'],plan[0]['positions']):
                size=template_info(items[index]['template'])['cut_px'];actual=image.getpixel((x+size//2,y+size//2))
                self.assertTrue(all(abs(a-b)<6 for a,b in zip(actual,colors[index])))
        with self.request('project/save',dict(items=items)) as response:saved=response.read()
        # A malformed project must leave every current image available.
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('project/open',b'broken',True)
        error.exception.close()
        with self.request('layout',dict(items=items)) as response:self.assertEqual(json.load(response)['pages'],plan)
        with self.request('export',dict(items=items)) as response:before=response.read()
        with self.request('project/open',saved,True) as response:restored=json.load(response)['photos']
        self.assertEqual([p['template'] for p in restored],['square','round_p','round_p'])
        with self.request('export',dict(items=restored)) as response:self.assertEqual(response.read(),before)
        for photo in restored:
            with self.request('delete',dict(id=photo['id'])):pass


if __name__ == '__main__':unittest.main()

import hashlib
import io
import json
import unittest
import zipfile
from PIL import Image
from photo_store import PhotoRecord
from projects import write_project,read_project


class ProjectTests(unittest.TestCase):
    def setUp(self):
        data=io.BytesIO();Image.new('RGB',(200,300),'red').save(data,'PNG')
        self.original=data.getvalue();self.record=PhotoRecord(self.original)
    def tearDown(self):self.record._cleanup()
    def batch(self):
        stream=io.BytesIO();write_project(stream,[(self.record,dict(name='Foto.png',template=key,edits=dict(zoom=1.25,brightness=1.1))) for key in ('square','round_p')]);return stream.getvalue()
    def mutate(self,change):
        source=zipfile.ZipFile(io.BytesIO(self.batch()));output=io.BytesIO()
        with source,zipfile.ZipFile(output,'w') as archive:
            meta=json.loads(source.read('project.json'));change(meta)
            for name in source.namelist():archive.writestr(name,json.dumps(meta).encode() if name=='project.json' else source.read(name))
        return output.getvalue()
    def test_roundtrip_keeps_originals_order_models_and_edits(self):
        result=read_project(io.BytesIO(self.batch()),PhotoRecord)
        try:
            self.assertEqual([meta['template'] for _,meta in result],['square','round_p'])
            for record,meta in result:
                self.assertEqual(record.original.read_bytes(),self.original);self.assertEqual(meta['edits']['zoom'],1.25);self.assertEqual(meta['edits']['brightness'],1.1)
        finally:
            for record,_ in result:record._cleanup()
    def test_invalid_format_model_rotation_and_hash_reject_and_release_staged_files(self):
        changes=[lambda m:m.update(application='PolaroidEditor'),lambda m:m['photos'][1].update(template='other'),
                 lambda m:m['photos'][1]['edits'].update(rotation=45),lambda m:m['photos'][1].update(sha256='0'*64)]
        for change in changes:
            created=[]
            def make(data):
                record=PhotoRecord(data);created.append(record);return record
            with self.assertRaises(ValueError):read_project(io.BytesIO(self.mutate(change)),make)
            self.assertTrue(all(not r.original.exists() for r in created))

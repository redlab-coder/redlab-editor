import io
import json
import unittest
import zipfile
from PIL import Image
from projects import write_project, read_project
from photo_store import PhotoRecord


class ProjectTests(unittest.TestCase):
    def test_empty_dimensions_and_reviewed_crop_roundtrip_preserve_bytes(self):
        data=io.BytesIO();Image.new('RGB',(100,80),'blue').save(data,'PNG')
        record=PhotoRecord(data.getvalue());records=[(record,dict(name='foto.png',edits=dict(width_cm='30',height_cm='36',cx=.75,zoom=2),reviewed=True,manual=False)),
            (record,dict(name='outra.png',edits={},reviewed=False,manual=False))]
        stream=io.BytesIO();write_project(stream,records);stream.seek(0)
        staged=read_project(stream,PhotoRecord)
        try:
            self.assertEqual(staged[0][0].original.read_bytes(),data.getvalue())
            self.assertTrue(staged[0][1]['reviewed']);self.assertEqual(staged[0][1]['edits']['cx'],.75)
            self.assertIsNone(staged[1][1]['edits']['width_cm'])
        finally:
            for item,_ in staged:item._cleanup()
            record._cleanup()

    def test_wrong_application_and_tampered_original_rejected(self):
        for application in ('PolaroidEditor','MedidasEditor'):
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:
                archive.writestr('project.json',json.dumps(dict(application=application,format=1,photos=[dict(file='photos/0000.bin',name='foto.png',sha256='a'*64)])))
                archive.writestr('photos/0000.bin',b'altered')
            stream.seek(0)
            with self.assertRaises(ValueError):read_project(stream,PhotoRecord)

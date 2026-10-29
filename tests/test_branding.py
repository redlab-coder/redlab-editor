import importlib.util
import json
from pathlib import Path
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


class BrandingTests(unittest.TestCase):
    def test_shared_modules_and_geometry_stay_in_sync(self):
        products=list((ROOT/'apps').glob('*-editor'))
        for name in ('branding.py','tray_panel.py','ui/family.css'):
            contents=[(product/name).read_bytes() for product in products]
            self.assertTrue(all(content==contents[0] for content in contents),name)
        boxes=[]
        for product in products:
            with Image.open(product/'assets'/f'{product.name}.ico') as image:
                self.assertEqual(image.ico.sizes(),{(size,size) for size in (16,20,24,32,40,48,64,128,256)})
                boxes.append(image.ico.getimage((256,256)).getbbox())
        self.assertTrue(all(box==boxes[0] for box in boxes))

    def test_palette_text_contrast_and_distinct_product_accents(self):
        def luminance(color):
            values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            values=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in values]
            return sum(value*weight for value,weight in zip(values,(.2126,.7152,.0722)))
        accents=[]
        for product in (ROOT/'apps').glob('*-editor'):
            theme=json.loads((product/'ui/theme.json').read_text(encoding='utf-8'));accents.append(theme['accent'])
            for foreground,background in ((theme['ink'],theme['header']),(theme['muted'],theme['header']),('#ffffff',theme['accent'])):
                low,high=sorted((luminance(foreground),luminance(background)))
                self.assertGreaterEqual((high+.05)/(low+.05),4.5,(product.name,foreground,background))
        self.assertEqual(len(set(accents)),3)

    def test_popup_stays_inside_each_monitor_including_negative_coordinates(self):
        spec=importlib.util.spec_from_file_location('redlab_panel',ROOT/'apps/bottons-editor/tray_panel.py')
        panel=importlib.util.module_from_spec(spec);spec.loader.exec_module(panel)
        for work in ((0,0,1920,1040),(-1920,0,0,1040),(0,-1080,1920,0)):
            for point in ((work[0],work[1]),(work[2],work[3])):
                for scale in (1,1.25,1.5,2,2.5):
                    width,height=round(300*scale),round(236*scale)
                    x,y=panel.popup_position(point,(width,height),work)
                    self.assertGreaterEqual(x,work[0]);self.assertGreaterEqual(y,work[1])
                    self.assertLessEqual(x+width,work[2]);self.assertLessEqual(y+height,work[3])

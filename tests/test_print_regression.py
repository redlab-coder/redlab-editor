"""Production Bottons geometry must remain pixel-identical to the approved Moldura."""
import importlib.util
from pathlib import Path
import subprocess
import types
import unittest
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]


class PrintRegressionTests(unittest.TestCase):
    def test_templates_and_rendering_match_the_original_moldura(self):
        legacy=types.ModuleType('legacy_engine')
        source=subprocess.check_output(['git','show','21dde5bc2322aa14bf07fc257f87ccc462517691:engine.py'],cwd=ROOT).decode('utf-8')
        exec(compile(source,'legacy_engine','exec'),legacy.__dict__)
        spec=importlib.util.spec_from_file_location('bottons_engine',ROOT/'apps/bottons-editor/engine.py')
        current=importlib.util.module_from_spec(spec);spec.loader.exec_module(current)
        self.assertEqual(legacy.TEMPLATES,current.TEMPLATES)
        photo=Image.new('RGB',(900,650),(70,110,90));draw=ImageDraw.Draw(photo)
        draw.rectangle((20,30,300,290),fill=(230,100,50));draw.ellipse((500,200,850,620),fill=(20,90,170))
        for template in current.TEMPLATES:
            for rotation in (0,90):
                edits={'rotation':rotation,'zoom':1.7,'cx':.2,'cy':.7,'brightness':1.12,'contrast':.94,'saturation':1.05,'sharpness':1.2}
                old,new=legacy.render_tile(photo,edits,template),current.render_tile(photo,edits,template)
                self.assertEqual(old.tobytes(),new.tobytes(),template)
                for count in (1,current.template_info(template)['capacity']):
                    self.assertEqual(legacy.compose_page([old]*count,template).tobytes(),current.compose_page([new]*count,template).tobytes())

import itertools
import random
import unittest
from engine import PAGE,TEMPLATES,page_positions,template_info
from layout import plan_pages,compose_sheet,GAP,MARGIN


class LayoutTests(unittest.TestCase):
    def check_plan(self,keys):
        items=[dict(template=key) for key in keys];pages=plan_pages(items)
        self.assertEqual(sorted(i for page in pages for i in page['indices']),list(range(len(keys))))
        for page in pages:
            boxes=[]
            for index,(x,y) in zip(page['indices'],page['positions']):
                size=template_info(keys[index])['cut_px'];self.assertGreaterEqual(min(x,y),0)
                self.assertLessEqual(x+size,PAGE[0]);self.assertLessEqual(y+size,PAGE[1]);boxes.append((x,y,size))
            for i,(x,y,size) in enumerate(boxes):
                for xx,yy,ss in boxes[i+1:]:self.assertTrue(x+size<=xx or xx+ss<=x or y+size<=yy or yy+ss<=y)
            left=min(x for x,y,size in boxes);right=PAGE[0]-max(x+size for x,y,size in boxes)
            top=min(y for x,y,size in boxes);bottom=PAGE[1]-max(y+size for x,y,size in boxes)
            self.assertLessEqual(abs(left-right),1)
            self.assertLessEqual(abs(top-bottom),1)
            if len({keys[index] for index in page['indices']})>1:
                self.assertGreaterEqual(min(left,right,top,bottom),MARGIN)
            # A page preview/download, planned from its own items, has identical geometry.
            subset=plan_pages([items[i] for i in page['indices']])
            self.assertEqual(len(subset),1);self.assertEqual(subset[0]['positions'],page['positions'])
        return pages

    def test_homogeneous_batches_retain_every_legacy_position(self):
        for key in TEMPLATES:
            for count in range(1,101):
                pages=self.check_plan([key]*count);capacity=template_info(key)['capacity']
                self.assertEqual(len(pages),(count+capacity-1)//capacity)
                for page in pages:self.assertEqual(page['positions'],page_positions(len(page['indices']),key))

    def test_square_and_two_small_rounds_fit_with_full_bleed_and_spacing(self):
        keys=['square','round_p','round_p'];pages=self.check_plan(keys);self.assertEqual(len(pages),1)
        self.assertEqual([template_info(k)['cut_px'] for k in keys],[827,531,531])
        x,y=pages[0]['positions'][0]
        for xx,yy in pages[0]['positions'][1:]:self.assertGreaterEqual(xx-(x+827),GAP)

    def test_exhaustive_small_mixes_random_batches_and_determinism(self):
        for count in range(1,6):
            for keys in itertools.product(TEMPLATES,repeat=count):
                pages=self.check_plan(keys);self.assertEqual(pages,plan_pages([dict(template=k) for k in keys]))
        rng=random.Random(220)
        for _ in range(100):self.check_plan(rng.choices(list(TEMPLATES),k=100))

    def test_mixed_pages_from_report_are_centered_without_changing_capacity(self):
        keys=['round_g','square','round_m','round_p']
        pages=self.check_plan(keys)
        self.assertEqual([page['indices'] for page in pages],[[0,1],[2,3]])
        for page in pages:
            first,second=page['indices'];(x,y),(xx,yy)=page['positions']
            self.assertEqual(xx-x-template_info(keys[first])['cut_px'],GAP)
            self.assertEqual(y,yy)

    def test_rendered_mixed_sheet_has_symmetric_margins_and_original_tile_sizes(self):
        from PIL import Image,ImageChops
        keys=['square','round_p','round_p']
        page=self.check_plan(keys)[0]
        colors=['red','green','blue']
        tiles=[Image.new('RGB',(template_info(key)['cut_px'],)*2,color) for key,color in zip(keys,colors)]
        try:
            with compose_sheet(tiles,page['positions']) as sheet,Image.new('RGB',PAGE,'white') as white:
                left,top,right,bottom=ImageChops.difference(sheet,white).getbbox()
                self.assertLessEqual(abs(left-(PAGE[0]-right)),1)
                self.assertLessEqual(abs(top-(PAGE[1]-bottom)),1)
                for tile,(x,y) in zip(tiles,page['positions']):
                    self.assertEqual(sheet.crop((x,y,x+tile.width,y+tile.height)).tobytes(),tile.tobytes())
        finally:
            for tile in tiles:tile.close()

    def test_invalid_models_and_empty_batch_are_rejected(self):
        for items in ([],[dict(template='invalid')],[None],[{}]*101):
            with self.assertRaises((ValueError,TypeError)):plan_pages(items)

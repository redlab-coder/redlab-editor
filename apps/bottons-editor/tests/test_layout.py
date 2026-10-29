import itertools
import random
import unittest
from engine import PAGE,TEMPLATES,page_positions,template_info
from layout import plan_pages,GAP


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

    def test_invalid_models_and_empty_batch_are_rejected(self):
        for items in ([],[dict(template='invalid')],[None],[{}]*101):
            with self.assertRaises((ValueError,TypeError)):plan_pages(items)

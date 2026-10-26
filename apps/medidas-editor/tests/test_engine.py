import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageCms
from PIL.JpegImagePlugin import get_sampling
from engine import FORMATS, SRGB, centimetres, pixels, choose_sheet, proportional_size, layout, load_image, export_jpeg, render_preview


class GeometryTests(unittest.TestCase):
    def test_exact_official_catalog_and_decimal_edges(self):
        self.assertEqual(len(FORMATS), 27)
        self.assertNotIn('50x190', [f['id'] for f in FORMATS])
        self.assertEqual(pixels('30'),3543); self.assertEqual(pixels('36'),4252)
        self.assertEqual(pixels('61'),7205); self.assertEqual(pixels('250'),29528)
        self.assertEqual(centimetres('30,5'),centimetres('30.5'))
        self.assertEqual(choose_sheet('30.500000','40')['id'],'30x40')
        self.assertNotEqual(choose_sheet('30.500001','40')['id'],'30x40')
        for value in ('', 'x', '-1', '0', 'NaN', 'Infinity', True, None, '1e10'):
            with self.subTest(value=value), self.assertRaises(ValueError):centimetres(value)

    def test_required_30_36_and_rotated_fit(self):
        first=layout((3000,3600),dict(width_cm='30',height_cm='36'))
        self.assertEqual(first['photo_px'],[3543,4252])
        self.assertEqual(first['sheet']['id'],'30x40')
        self.assertEqual(first['sheet']['size_px'],[3602,4724])
        self.assertEqual(first['position_px'],[0,0])
        self.assertEqual([3602-3543,4724-4252],[59,472])
        rotated=layout((3600,3000),dict(width_cm='36',height_cm='30'))
        self.assertEqual(rotated['sheet']['id'],'30x40')
        self.assertEqual(rotated['sheet']['rotation'],90)
        self.assertEqual(rotated['placed_photo_px'],first['photo_px'])

    def test_smallest_area_manual_and_no_silent_shrink(self):
        self.assertEqual(choose_sheet('30.5','40')['id'],'30x40')
        self.assertNotEqual(choose_sheet('30.6','40')['id'],'30x40')
        self.assertEqual(choose_sheet('30','36','40x50')['id'],'40x50')
        with self.assertRaises(ValueError):choose_sheet('30','36','10x15')
        for width,height in (('62','251'),('0','10')):
            with self.assertRaises(ValueError):choose_sheet(width,height)
        # Area decision precedes the extra-rotation preference.
        self.assertEqual(choose_sheet('14','10')['id'],'10x15')

    def test_single_dimension_and_metadata_do_not_set_intention(self):
        width,height=proportional_size('30','',(3000,3600))
        self.assertEqual((width,height),(centimetres('30'),centimetres('36')))
        self.assertEqual(proportional_size('', '36', (3000,3600)),(width,height))
        with self.assertRaises(ValueError):proportional_size('', '',(3000,3600))

    def test_cover_pan_zoom_effective_resolution_and_contain(self):
        base=layout((4000,2000),dict(width_cm='10',height_cm='10'))
        self.assertTrue(base['needs_review'])
        self.assertEqual(base['crop_box'],[1000,0,3000,2000])
        edge=layout((4000,2000),dict(width_cm='10',height_cm='10',zoom=2,cx=1,cy=0))
        self.assertEqual(edge['crop_box'],[3000,0,4000,1000])
        self.assertAlmostEqual(edge['effective_ppi'],base['effective_ppi']/2,places=1)
        low=layout((100,100),dict(width_cm='30',height_cm='36'))
        self.assertLess(low['effective_ppi'],10); self.assertTrue(low['warnings'])
        whole=layout((4000,2000),dict(width_cm='10',height_cm='10',mode='contain',zoom=5))
        self.assertFalse(whole['needs_review']); self.assertEqual(whole['crop_box'],[0,0,4000,2000])
        self.assertEqual(whole['settings']['zoom'],1)
        self.assertGreater(whole['content_box'][1],0)

    def test_positions_and_rotation_preserve_crop(self):
        for position in ('top_left','top_right','bottom_left','bottom_right','center'):
            a=layout((2000,1000),dict(width_cm='10',height_cm='10',position=position))
            self.assertEqual(a['crop_box'],[500,0,1500,1000])
        a=layout((2000,1000),dict(width_cm='10',height_cm='10',rotation=90))
        self.assertEqual(a['oriented_source'],[1000,2000])
        self.assertEqual(a['crop_box'],[0,500,1000,1500])


class ImageTests(unittest.TestCase):
    def test_tiny_source_at_maximum_zoom_and_edge_is_reported_and_can_render(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'pixel.png';target=root/'result.jpg'
            Image.new('RGB',(1,1),(120,20,30)).save(source)
            plan,_=export_jpeg(source,dict(width_cm='3',height_cm='3',zoom=10,cx=1,cy=1),target)
            self.assertTrue(plan['needs_review']);self.assertTrue(plan['warnings'])
            self.assertLess(plan['effective_ppi'],1)
            with Image.open(target) as result:
                self.assertTrue(all(abs(a-b)<=2 for a,b in zip(result.getpixel((50,50)),(120,20,30))))

    def test_exif_orientation_metadata_and_opaque_white(self):
        data=io.BytesIO();image=Image.new('RGB',(120,80),'red');exif=Image.Exif();exif[274]=6
        image.save(data,'JPEG',exif=exif,dpi=(300,150)); image.close()
        oriented,meta=load_image(data.getvalue())
        self.assertEqual(oriented.size,(80,120)); self.assertEqual(meta['dpi'],[150,300]);oriented.close()
        data=io.BytesIO();Image.new('RGBA',(20,20),(100,0,0,0)).save(data,'PNG')
        opaque,meta=load_image(data.getvalue()); self.assertEqual(opaque.getpixel((0,0)),(255,255,255));opaque.close()

    def test_icc_policy_valid_invalid_and_untagged_cmyk(self):
        for profile in (SRGB,b'not-an-icc-profile'):
            data=io.BytesIO();Image.new('RGB',(20,20),'red').save(data,'PNG',icc_profile=profile)
            image,meta=load_image(data.getvalue())
            self.assertEqual(image.info['icc_profile'],SRGB)
            self.assertEqual(bool(meta['warnings']),profile!=SRGB);image.close()
        data=io.BytesIO();Image.new('CMYK',(20,20),(0,255,255,0)).save(data,'TIFF')
        image,meta=load_image(data.getvalue());self.assertTrue(meta['warnings']);image.close()

    def test_production_jpeg_geometry_resolution_profile_and_unchanged_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original=root/'source.png';destination=root/'result.jpg'
            Image.new('RGB',(600,720),(170,60,30)).save(original)
            digest=hashlib.sha256(original.read_bytes()).digest()
            plan,_=export_jpeg(original,dict(width_cm='30',height_cm='36'),destination)
            self.assertEqual(plan['position_px'],[0,0])
            with Image.open(destination) as result:
                self.assertEqual(result.size,(3602,4724));self.assertEqual(result.info['dpi'],(300,300))
                self.assertEqual(get_sampling(result),0)
                self.assertEqual(result.quantization[0],[1]*64)
                self.assertIn('sRGB',ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(result.info['icc_profile']))))
                self.assertTrue(all(abs(a-b)<=2 for a,b in zip(result.getpixel((100,100)),(170,60,30))))
                self.assertTrue(min(result.getpixel((3570,100)))>=253)
                self.assertTrue(min(result.getpixel((100,4600)))>=253)
            self.assertEqual(hashlib.sha256(original.read_bytes()).digest(),digest)

    def test_contain_and_sheet_whites_are_distinct_before_jpeg(self):
        source=Image.new('RGB',(200,100),'red')
        preview,plan=render_preview(source,source.size,dict(width_cm='10',height_cm='10',mode='contain'))
        self.assertEqual(preview.getpixel((5,5)),(255,255,255))
        self.assertEqual(preview.getpixel((50,300)),(255,0,0))
        self.assertEqual(preview.getpixel((10,900)),(255,255,255))
        preview.close();source.close()

    def test_accommodation_rotation_is_after_the_photo_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.png';target=root/'result.jpg'
            image=Image.new('RGB',(420,300),'red')
            image.paste(Image.new('RGB',(210,300),'blue'),(210,0));image.save(source);image.close()
            plan,_=export_jpeg(source,dict(width_cm='14',height_cm='10'),target)
            self.assertEqual(plan['sheet']['id'],'10x15');self.assertEqual(plan['sheet']['rotation'],90)
            with Image.open(target) as result:
                self.assertGreater(result.getpixel((100,100))[0],250)
                self.assertGreater(result.getpixel((100,1500))[2],250)
                self.assertGreater(min(result.getpixel((1198,100))),250)

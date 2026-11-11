import io
import unittest
import zipfile

from PIL import Image

from jobs import ExportManager
from montage import COPIES, FIVE_LARGE, FIVE_SMALL, SEVEN, plan_sheets, render_sheet
from photo_store import PhotoRecord
from projects import read_project, write_project


class MontageTests(unittest.TestCase):
    def test_five_by_seven_boundaries_and_order(self):
        for count, expected in ((0, []), (1, [(FIVE_SMALL, 1)]), (3, [(FIVE_SMALL, 3)]),
                                (4, [(FIVE_LARGE, 4)]), (9, [(FIVE_LARGE, 9)]),
                                (10, [(FIVE_LARGE, 9), (FIVE_SMALL, 1)]),
                                (12, [(FIVE_LARGE, 9), (FIVE_SMALL, 3)]),
                                (13, [(FIVE_LARGE, 9), (FIVE_LARGE, 4)]),
                                (19, [(FIVE_LARGE, 9), (FIVE_LARGE, 9), (FIVE_SMALL, 1)])):
            with self.subTest(count=count):
                sheets = plan_sheets(['5x7'] * count)
                self.assertEqual([(sheet.preset, len(sheet.indices)) for sheet in sheets], expected)
                self.assertEqual([i for sheet in sheets for i in sheet.indices], list(range(count)))
        mixed = plan_sheets(['7x10', '5x7', '3x4', None, '7x10', '5x7'])
        self.assertEqual([(sheet.preset, sheet.indices) for sheet in mixed],
                         [(COPIES, (2,)), (FIVE_SMALL, (1, 5)), (SEVEN, (0, 4))])

    def setUp(self):
        data = io.BytesIO()
        with Image.new('RGB', (900, 600), (220, 10, 10)) as photo:
            photo.paste((10, 220, 10), (450, 0, 900, 600))
            photo.save(data, 'PNG')
        self.record = PhotoRecord(data.getvalue())
        self.addCleanup(self.record._cleanup)

    def test_legacy_orientation_repeat_positions_and_preview(self):
        records = [(self.record, {'name': 'Paisagem.png'})] * 2
        five, = plan_sheets(['5x7', '5x7'])
        with render_sheet(five, records) as sheet:
            self.assertEqual(sheet.size, (1795, 1181))
            self.assertEqual(sheet.getpixel((280, 480)), (10, 220, 10))
            self.assertEqual(sheet.getpixel((280, 1080)), (220, 10, 10))
            self.assertEqual(sheet.getpixel((591, 700)), (255, 255, 255))
            self.assertEqual(sheet.getpixel((1300, 700)), (255, 255, 255))
        with render_sheet(five, records, maximum=320) as preview:
            self.assertEqual(preview.size, (320, 211))
            self.assertEqual(preview.getpixel((50, 84)), (10, 220, 10))
        copies, = plan_sheets(['3x4'])
        with render_sheet(copies, records) as sheet:
            self.assertEqual(sheet.size, (1795, 1205))
            for y in (200, 690):
                for x in (188, 543, 898, 1253):
                    self.assertEqual(sheet.getpixel((x + 45, y)), (220, 10, 10))
                    self.assertEqual(sheet.getpixel((x + 300, y)), (10, 220, 10))

    def test_zip_groups_exact_models_and_single_sheet_is_jpeg(self):
        sizes = ['5x7'] * 12 + ['3x4', '7x10', '7x10']
        records = [(self.record, {'name': 'Paisagem.png'})] * len(sizes)
        manager = ExportManager()
        self.addCleanup(manager.close)
        job = manager.start_montage(plan_sheets(sizes), records)
        manager.jobs[job]['thread'].join(timeout=30)
        self.assertEqual(manager.status(job)['success'], 4)
        with zipfile.ZipFile(manager.jobs[job]['path']) as archive:
            sizes_by_folder = {'10x15 (3x4)': (1795, 1205), '10x15 (5x7)': (1795, 1181),
                               '10x15 (7x10)': (1795, 1205), '15x21 (5x7)': (1795, 2551)}
            self.assertEqual({name.split('/')[0] for name in archive.namelist()}, set(sizes_by_folder))
            for name in archive.namelist():
                with Image.open(io.BytesIO(archive.read(name))) as image:
                    self.assertEqual(image.size, sizes_by_folder[name.split('/')[0]])
                    self.assertEqual(image.info['dpi'], (300, 300))
                    self.assertTrue(image.info['icc_profile'])
        job = manager.start_montage(plan_sheets(['3x4']), records[:1])
        manager.jobs[job]['thread'].join(timeout=30)
        self.assertTrue(manager.status(job)['filename'].endswith('.jpg'))

    def test_mixed_recovery_project_retains_custom_edits_and_montage_selection(self):
        stream = io.BytesIO()
        write_project(stream, [(self.record, dict(name='Medidas.png', edits={'width_cm': '7', 'height_cm': '8'})),
                               (self.record, dict(name='Corte.png', tool='montagem', edits={'size': '5x7'}, selected=True, checked=True))])
        staged = read_project(stream, PhotoRecord)
        for record, _ in staged:
            self.addCleanup(record._cleanup)
        self.assertEqual(staged[0][1]['edits']['height_cm'], '8')
        meta = staged[1][1]
        self.assertEqual((meta['tool'], meta['edits']['size'], meta['selected'], meta['checked']), ('montagem', '5x7', True, True))

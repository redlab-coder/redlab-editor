"""The four production layouts of RedLab Tool, planned from per-photo sizes."""
from dataclasses import dataclass

from PIL import Image

from engine import DPI, SRGB, ExportCancelled, load_image, pixels


PHOTO_SIZES = ('3x4', '5x7', '7x10')
GAP = 1


@dataclass(frozen=True)
class Preset:
    paper: str
    photo: str
    paper_cm: tuple[str, str]
    photo_cm: tuple[str, str]
    columns: int
    rows: int
    repeat: bool = False

    @property
    def name(self):
        return f'{self.paper} ({self.photo})'

    @property
    def capacity(self):
        return 1 if self.repeat else self.columns * self.rows

    @property
    def paper_px(self):
        return tuple(map(pixels, self.paper_cm))

    @property
    def photo_px(self):
        return tuple(map(pixels, self.photo_cm))

    def position(self, index):
        width, height = self.paper_px
        pw, ph = self.photo_px
        col, row = index % self.columns, index // self.columns
        if self.repeat:
            grid_w = self.columns * pw + (self.columns - 1) * GAP
            grid_h = self.rows * ph + (self.rows - 1) * GAP
            return (width - grid_w) // 2 + col * (pw + GAP), (height - grid_h) // 2 + row * (ph + GAP)
        return col * (pw + GAP), height - ph - row * (ph + GAP)


COPIES = Preset('10x15', '3x4', ('15.2', '10.2'), ('3', '4'), 4, 2, repeat=True)
FIVE_SMALL = Preset('10x15', '5x7', ('15.2', '10'), ('5', '7'), 3, 1)
FIVE_LARGE = Preset('15x21', '5x7', ('15.2', '21.6'), ('5', '7'), 3, 3)
SEVEN = Preset('10x15', '7x10', ('15.2', '10.2'), ('7', '10.2'), 2, 1)


@dataclass(frozen=True)
class Sheet:
    preset: Preset
    indices: tuple[int, ...]

    def describe(self):
        return dict(model=self.preset.name, paper_cm=self.preset.paper_cm,
                    photo_cm=self.preset.photo_cm, photo_count=len(self.indices),
                    print_count=8 if self.preset.repeat else len(self.indices))


def photo_size(value, *, allow_empty=False):
    if value is None and allow_empty:
        return None
    if value not in PHOTO_SIZES:
        raise ValueError('Escolha 3×4, 5×7 ou 7×10 para a foto.')
    return value


def plan_sheets(sizes):
    groups = {size: [] for size in PHOTO_SIZES}
    for index, size in enumerate(sizes):
        if photo_size(size, allow_empty=True) is not None:
            groups[size].append(index)
    sheets = [Sheet(COPIES, (index,)) for index in groups['3x4']]
    five = groups['5x7']
    for start in range(0, len(five), FIVE_LARGE.capacity):
        batch = tuple(five[start:start + FIVE_LARGE.capacity])
        preset = FIVE_SMALL if len(batch) <= FIVE_SMALL.capacity else FIVE_LARGE
        sheets.append(Sheet(preset, batch))
    seven = groups['7x10']
    sheets.extend(Sheet(SEVEN, tuple(seven[start:start + SEVEN.capacity]))
                  for start in range(0, len(seven), SEVEN.capacity))
    return sheets


def center_box(width, height, ratio):
    if abs(width / height - ratio) < 1e-6:
        return 0, 0, width, height
    if width / height > ratio:
        crop = max(1, min(width, round(height * ratio)))
        left = (width - crop) // 2
        return left, 0, left + crop, height
    crop = max(1, min(height, round(width / ratio)))
    top = (height - crop) // 2
    return 0, top, width, top + crop


def prepare_tile(source, original_size, preset, target):
    width, height = original_size
    if preset.repeat:
        return source.resize(target, Image.Resampling.LANCZOS)
    if width > height:
        with source.transpose(Image.Transpose.ROTATE_90) as upright:
            return crop_tile(upright, (height, width), preset.photo_px, target)
    return crop_tile(source, original_size, preset.photo_px, target)


def crop_tile(source, original_size, photo_size_px, target):
    width, height = original_size
    pw, ph = photo_size_px
    left, top, right, bottom = center_box(width, height, pw / ph)
    # Calculate the crop against the original, then project it onto the proxy.
    if source.size != original_size:
        sx, sy = source.width / width, source.height / height
        left = min(source.width - 1, round(left * sx))
        top = min(source.height - 1, round(top * sy))
        right = max(left + 1, round(right * sx))
        bottom = max(top + 1, round(bottom * sy))
    with source.crop((left, top, right, bottom)) as cropped:
        return cropped.resize(target, Image.Resampling.LANCZOS)


def render_sheet(sheet, records, *, maximum=None, cancel=None, progress=None):
    preset = sheet.preset
    width, height = preset.paper_px
    pw, ph = preset.photo_px
    scale = min(1, maximum / max(width, height)) if maximum else 1
    target = max(1, round(pw * scale)), max(1, round(ph * scale))
    canvas = Image.new('RGB', (round(width * scale), round(height * scale)), 'white')
    try:
        for index, source_index in enumerate(sheet.indices):
            if cancel is not None and cancel.is_set():
                raise ExportCancelled()
            record, meta = records[source_index]
            try:
                source = Image.open(record.proxy) if maximum else load_image(record.original.read_bytes())[0]
                with source:
                    tile = prepare_tile(source, (record.width, record.height), preset, target)
                with tile:
                    for slot in range(preset.columns * preset.rows) if preset.repeat else (index,):
                        x, y = preset.position(slot)
                        canvas.paste(tile, (round(x * scale), round(y * scale)))
            except (ValueError, OSError) as error:
                raise ValueError(f'Não foi possível montar a foto {meta["name"]}.') from error
            if progress:
                progress((index + 1) * 100 / len(sheet.indices))
        return canvas
    except BaseException:
        canvas.close()
        raise


def export_sheet(sheet, records, path, *, cancel, progress):
    with render_sheet(sheet, records, cancel=cancel, progress=progress) as image:
        if cancel.is_set():
            raise ExportCancelled()
        image.save(path, 'JPEG', quality=100, subsampling=0, dpi=(DPI, DPI), icc_profile=SRGB)

"""Physical photo area, independent sheet selection and bounded production JPEG.

Centimetres use Decimal; raster edges use ROUND_HALF_UP at 300 pixels/inch.
All crop coordinates refer to the EXIF-corrected, manually rotated original.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

from PIL import Image, ImageCms, ImageOps

DPI = 300
MAX_INPUT_PIXELS = 60_000_000
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
FORMATS = tuple(json.loads(Path(__file__).with_name('formats.json').read_text(encoding='utf-8')))
POSITIONS = ('top_left', 'top_right', 'bottom_left', 'bottom_right', 'center')


def centimetres(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('Informe uma medida positiva em centímetros.')
    text = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'\d{1,6}(?:\.\d{1,6})?', text):
        raise ValueError('Use uma medida positiva, com vírgula ou ponto e até seis casas decimais.')
    try:
        result = Decimal(text)
    except InvalidOperation:
        raise ValueError('Medida inválida.') from None
    if not result.is_finite() or result <= 0:
        raise ValueError('As medidas devem ser maiores que zero.')
    return result


def cm_text(value):
    return format(value.normalize(), 'f')


def pixels(value):
    result = int((centimetres(value) / Decimal('2.54') * DPI).to_integral_value(rounding=ROUND_HALF_UP))
    if result < 1:
        raise ValueError('A medida é menor que um pixel a 300 dpi.')
    return result


def sheet_options(width_cm, height_cm):
    width, height = centimetres(width_cm), centimetres(height_cm)
    options = []
    for index, spec in enumerate(FORMATS):
        sw, sh = Decimal(spec['width_cm']), Decimal(spec['height_cm'])
        rotation = 0 if width <= sw and height <= sh else 90 if height <= sw and width <= sh else None
        if rotation is not None:
            options.append((sw * sh, rotation != 0, index, dict(spec, rotation=rotation,
                           size_px=[pixels(sw), pixels(sh)])))
    return [option[3] for option in sorted(options, key=lambda row: row[:3])]


def choose_sheet(width_cm, height_cm, sheet_id='auto'):
    options = sheet_options(width_cm, height_cm)
    if not options:
        raise ValueError('Nenhuma folha cadastrada comporta essa foto, mesmo girando 90°. Confira as medidas.')
    if sheet_id == 'auto':
        return options[0]
    selected = next((option for option in options if option['id'] == sheet_id), None)
    if selected is None:
        raise ValueError('A folha escolhida não comporta a área solicitada.')
    return selected


def proportional_size(width, height, source_size):
    """An explicit single dimension determines the other; metadata never does."""
    sw, sh = source_size
    if width not in (None, '') and height not in (None, ''):
        return centimetres(width), centimetres(height)
    if width not in (None, ''):
        width = centimetres(width)
        return width, (width * sh / sw).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
    if height not in (None, ''):
        height = centimetres(height)
        return (height * sw / sh).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP), height
    raise ValueError('Informe largura e altura, ou uma delas para usar a proporção original.')


def normalized_settings(value=None, allow_empty=False):
    if not isinstance(value, (dict, type(None))):
        raise ValueError('Ajustes inválidos.')
    value = value or {}
    result = dict(width_cm=None, height_cm=None, mode='cover', zoom=1., cx=.5, cy=.5,
                  rotation=0, sheet='auto', position='top_left')
    for key in ('width_cm', 'height_cm'):
        supplied = value.get(key)
        if supplied not in (None, ''):
            result[key] = cm_text(centimetres(supplied))
        elif not allow_empty:
            raise ValueError('Defina a largura e a altura da foto antes de exportar.')
    for key in ('mode', 'sheet', 'position', 'rotation'):
        if key in value:
            result[key] = value[key]
    if result['mode'] not in ('cover', 'contain') or result['position'] not in POSITIONS:
        raise ValueError('Modo ou posição inválidos.')
    if type(result['rotation']) is not int or result['rotation'] not in (0, 90, 180, 270):
        raise ValueError('A rotação deve ser 0°, 90°, 180° ou 270°.')
    if result['sheet'] not in ('auto', *(spec['id'] for spec in FORMATS)):
        raise ValueError('Folha inválida.')
    for key, low, high in (('zoom', 1, 10), ('cx', 0, 1), ('cy', 0, 1)):
        if isinstance(value.get(key), bool):
            raise ValueError('Enquadramento inválido.')
        try:
            number = float(value.get(key, result[key]))
        except (ValueError, TypeError):
            raise ValueError('Enquadramento inválido.') from None
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError('Enquadramento fora dos limites.')
        result[key] = number
    if result['mode'] == 'contain':
        result.update(zoom=1., cx=.5, cy=.5)
    return result


def layout(source_size, settings):
    settings = normalized_settings(settings)
    pw, ph = pixels(settings['width_cm']), pixels(settings['height_cm'])
    sheet = choose_sheet(settings['width_cm'], settings['height_cm'], settings['sheet'])
    sw, sh = sheet['size_px']
    iw, ih = source_size if settings['rotation'] % 180 == 0 else source_size[::-1]
    if settings['mode'] == 'cover':
        side_scale = min(iw / pw, ih / ph) / settings['zoom']
        cw, ch = pw * side_scale, ph * side_scale
        cx = max(cw / 2, min(iw - cw / 2, settings['cx'] * iw))
        cy = max(ch / 2, min(ih - ch / 2, settings['cy'] * ih))
        crop = [cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2]
        content = [0, 0, pw, ph]
        ppi = DPI * side_scale
        needs_review = iw - cw > 1.01 or ih - ch > 1.01
    else:
        crop = [0, 0, iw, ih]
        scale = min(pw / iw, ph / ih)
        dw, dh = min(pw, max(1, round(iw * scale))), min(ph, max(1, round(ih * scale)))
        x, y = (pw - dw) // 2, (ph - dh) // 2
        content = [x, y, x + dw, y + dh]
        ppi = min(iw / dw, ih / dh) * DPI
        needs_review = False
    placed_w, placed_h = (ph, pw) if sheet['rotation'] else (pw, ph)
    if placed_w > sw or placed_h > sh:
        raise ValueError('O arredondamento em pixels excedeu a folha. Confira as medidas.')
    position = settings['position']
    x = (sw - placed_w) // 2 if position == 'center' else sw - placed_w if position.endswith('right') else 0
    y = (sh - placed_h) // 2 if position == 'center' else sh - placed_h if position.startswith('bottom') else 0
    warnings = []
    if ppi < DPI - .1:
        warnings.append(f'Resolução efetiva: {ppi:.0f} ppi. Haverá ampliação; reamostrar não recupera detalhes.')
    if settings['mode'] == 'contain' and (content[2] - content[0] < pw or content[3] - content[1] < ph):
        warnings.append('Imagem inteira: a foto visível ocupa menos que a área solicitada e terá branco interno.')
    return dict(settings=settings, photo_px=[pw, ph], sheet=sheet, oriented_source=[iw, ih],
                crop_box=crop, content_box=content, placed_photo_px=[placed_w, placed_h],
                position_px=[x, y], effective_ppi=round(ppi, 2), needs_review=needs_review,
                warnings=warnings, options=sheet_options(settings['width_cm'], settings['height_cm']))


def load_image(data):
    """Match existing sRGB policy, but report every profile fallback explicitly."""
    warnings = []
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > MAX_INPUT_PIXELS:
            raise ValueError('A entrada excede 60 megapixels. O limite não se aplica à folha de saída.')
        orientation = source.getexif().get(274, 1)
        raw_dpi = source.info.get('dpi')
        dpi = None
        if isinstance(raw_dpi, (list, tuple)) and len(raw_dpi) >= 2:
            try:
                dx, dy = map(float, raw_dpi[:2])
                if all(math.isfinite(n) and n > 0 for n in (dx, dy)):
                    dpi = [dy, dx] if orientation in (5, 6, 7, 8) else [dx, dy]
            except (ValueError, TypeError, OverflowError):
                pass
        icc = source.info.get('icc_profile')
        source.load()
        oriented = ImageOps.exif_transpose(source) if orientation != 1 else source
        image = None
        try:
            alpha = oriented.getchannel('A') if 'A' in oriented.getbands() else oriented.convert('RGBA').getchannel('A') if oriented.mode == 'P' else None
            if icc:
                try:
                    profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                    description = ImageCms.getProfileDescription(profile).strip()[:160]
                    color = oriented.convert('RGB') if oriented.mode in ('RGBA', 'LA', 'P') else oriented
                    image = ImageCms.profileToProfile(color, profile, ImageCms.ImageCmsProfile(io.BytesIO(SRGB)),
                               outputMode='RGB', renderingIntent=ImageCms.Intent.PERCEPTUAL)
                except (ValueError, OSError, ImageCms.PyCMSError):
                    image = oriented.convert('RGB')
                    description = 'Perfil ICC inválido'
                    warnings.append('O perfil ICC não pôde ser convertido. Foi usada conversão RGB; confira a cor antes de produzir.')
            else:
                image = oriented if oriented.mode == 'RGB' and oriented is not source else oriented.convert('RGB')
                description = 'Sem perfil ICC; sRGB assumido'
                if oriented.mode == 'CMYK':
                    warnings.append('CMYK sem perfil ICC: conversão RGB aproximada. Confira a cor antes de produzir.')
            if alpha is not None:
                background = Image.new('RGB', image.size, 'white')
                background.paste(image, mask=alpha)
                image.close()
                alpha.close()
                image = background
            image.info.clear()
            image.info['icc_profile'] = SRGB
            metadata = dict(dpi=dpi, size_cm=[round(image.width / dpi[0] * 2.54, 6),
                       round(image.height / dpi[1] * 2.54, 6)] if dpi else None,
                       profile=description, color_policy='sRGB · ICC convertido quando válido', warnings=warnings)
            return image, metadata
        finally:
            if oriented is not image:
                oriented.close()


def render_preview(source, original_size, settings, maximum=1000):
    plan = layout(original_size, settings)
    sw, sh = plan['sheet']['size_px']
    factor = min(maximum / sw, maximum / sh, 1.)
    page_size = max(1, round(sw * factor)), max(1, round(sh * factor))
    pw, ph = plan['photo_px']
    photo_size = max(1, round(pw * factor)), max(1, round(ph * factor))
    image = source.rotate(-plan['settings']['rotation'], expand=True)
    try:
        area = Image.new('RGB', photo_size, 'white')
        crop = plan['crop_box']
        iw, ih = plan['oriented_source']
        crop = [crop[0] * image.width / iw, crop[1] * image.height / ih,
                crop[2] * image.width / iw, crop[3] * image.height / ih]
        content = plan['content_box']
        box = [round(content[0] * factor), round(content[1] * factor),
               max(round(content[0] * factor) + 1, round(content[2] * factor)),
               max(round(content[1] * factor) + 1, round(content[3] * factor))]
        tile = image.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS, box=tuple(crop))
        area.paste(tile, box[:2]); tile.close()
        if plan['sheet']['rotation']:
            rotated = area.transpose(Image.Transpose.ROTATE_270); area.close(); area = rotated
        page = Image.new('RGB', page_size, 'white')
        x, y = plan['position_px']
        page.paste(area, (round(x * factor), round(y * factor))); area.close()
        return page, plan
    finally:
        image.close()


class ExportCancelled(Exception):
    pass


def export_jpeg(original, settings, destination, cancel=None, progress=None):
    """Normalize one original, then stream a demand-driven libvips JPEG pipeline.

    optimize_coding=False is deliberate: optimized Huffman coding can buffer all
    JPEG coefficients. Quality 100 and 4:4:4 are preserved without that buffer.
    """
    os.environ.setdefault('VIPS_CONCURRENCY', '2')
    os.environ.setdefault('VIPS_DISC_THRESHOLD', '32m')
    import pyvips
    pyvips.cache_set_max(0)
    pyvips.cache_set_max_mem(32 * 1024**2)
    settings = normalized_settings(settings)
    if cancel and cancel.is_set():
        raise ExportCancelled()
    image, metadata = load_image(Path(original).read_bytes())
    try:
        plan = layout(image.size, settings)
        needed = image.width * image.height * 3 + plan['sheet']['size_px'][0] * plan['sheet']['size_px'][1] * 3 + 64 * 1024**2
        if shutil.disk_usage(Path(destination).parent).free < needed:
            raise ValueError('Pouco espaço temporário para gerar esse formato. Libere espaço e tente novamente.')
        with tempfile.TemporaryDirectory(prefix='MedidasEditor-render-') as temporary:
            normalized = Path(temporary) / 'source.tif'
            image.save(normalized, 'TIFF', compression='raw', icc_profile=SRGB)
            image.close(); image = None
            if cancel and cancel.is_set():
                raise ExportCancelled()
            # Input is already normalized by the same Pillow/ICC policy as preview.
            source = pyvips.Image.new_from_file(str(normalized), access='random')
            rotation = settings['rotation']
            if rotation:
                source = source.rot({90:'d90', 180:'d180', 270:'d270'}[rotation])
            left, top, right, bottom = plan['crop_box']
            # Integer edge rounding is shared and never enlarges the photo area.
            x0, y0 = max(0, round(left)), max(0, round(top))
            x1, y1 = min(source.width, round(right)), min(source.height, round(bottom))
            cropped = source.crop(x0, y0, max(1, x1-x0), max(1, y1-y0))
            x, y, r, b = plan['content_box']; dw, dh = r-x, b-y
            content = cropped.resize(dw / cropped.width, vscale=dh / cropped.height, kernel='lanczos3')
            # Accommodate encoder/library rounding while keeping exact raster edges.
            if content.width != dw or content.height != dh:
                content = content.embed(0, 0, max(dw, content.width), max(dh, content.height), extend='copy').crop(0, 0, dw, dh)
            pw, ph = plan['photo_px']
            area = content.embed(x, y, pw, ph, extend='background', background=[255,255,255])
            if plan['sheet']['rotation']:
                area = area.rot('d90')
            sw, sh = plan['sheet']['size_px']; px, py = plan['position_px']
            page = area.embed(px, py, sw, sh, extend='background', background=[255,255,255])
            page = page.copy(interpretation='srgb', xres=DPI / 25.4, yres=DPI / 25.4)
            page.set_type(pyvips.GValue.blob_type, 'icc-profile-data', SRGB)
            page.set_type(pyvips.GValue.gstr_type, 'resolution-unit', 'in')
            page.set_progress(True)
            def on_progress(sender, status):
                if cancel and cancel.is_set():
                    sender.set_kill(True)
                if progress:
                    progress(int(status.percent))
            page.signal_connect('eval', on_progress)
            try:
                page.jpegsave(str(destination), Q=100, subsample_mode='off', optimize_coding=False,
                              interlace=False, keep='exif,icc')
            except pyvips.Error:
                if cancel and cancel.is_set():
                    raise ExportCancelled() from None
                raise
            if cancel and cancel.is_set():
                Path(destination).unlink(missing_ok=True)
                raise ExportCancelled()
            return plan, metadata
    finally:
        if image is not None:
            image.close()

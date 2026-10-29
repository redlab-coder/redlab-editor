"""Render suite installer artwork using the existing family icons."""
import importlib.util
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT/'bundle/assets'


def brands():
    result = []
    for product in ('bottons-editor', 'polaroid-editor', 'medidas-editor'):
        spec = importlib.util.spec_from_file_location('suite_brand', ROOT/'apps'/product/'branding.py')
        brand = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(brand)
        result.append(brand)
    return result


def generate():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    family = brands()
    scale = 4
    welcome = Image.new('RGB', (164*scale, 314*scale), '#f4f6f1')
    draw = ImageDraw.Draw(welcome)
    def text(x, y, value, size, color='#253c2d', bold=False):
        font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf', size*scale)
        draw.text((x*scale, y*scale), value, font=font, fill=color)
    text(16, 20, 'RedLab', 23, bold=True)
    text(18, 50, 'EDITOR', 10, '#62715f')
    for y, brand in zip((92, 156, 220), family):
        icon = brand.icon_image(48*scale)
        welcome.paste(icon, (16*scale, y*scale), icon)
        text(76, y+8, brand.THEME['name'].split()[0], 10, bold=True)
        text(76, y+24, 'Editor', 9, '#62715f')
    welcome.resize((164, 314), Image.Resampling.LANCZOS).save(DESTINATION/'welcome.bmp')
    icon = Image.new('RGBA', (1024, 1024))
    canvas = ImageDraw.Draw(icon)
    canvas.rounded_rectangle((32, 32, 992, 992), radius=232, fill='#f4f6f1')
    for x, y, brand in zip((156, 384, 612), (412, 320, 412), family):
        tile = brand.icon_image(256)
        icon.alpha_composite(tile, (x, y))
    icon = icon.resize((256, 256), Image.Resampling.LANCZOS)
    icon.save(DESTINATION/'redlab-editor.ico', sizes=[(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    small = Image.new('RGB', (55, 55), 'white')
    resized = icon.resize((55, 55), Image.Resampling.LANCZOS)
    small.paste(resized, (0, 0), resized)
    small.save(DESTINATION/'small.bmp')
    icon.save(DESTINATION/'redlab-editor.png')


if __name__ == '__main__':
    generate()

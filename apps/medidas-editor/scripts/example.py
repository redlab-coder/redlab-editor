"""Reproduce the 30 × 36 cm example with synthetic content, no overwrites."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import export_jpeg


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'dist/exemplo-30x36.jpg')
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise SystemExit('O arquivo de destino já existe. Escolha outro nome.')
    with tempfile.TemporaryDirectory(prefix='MedidasEditor-example-') as temporary:
        root=Path(temporary);original=root/'foto.png';result=root/'result.jpg'
        image=Image.new('RGB',(1200,1440),'#c3d2c2');draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,1199,719),fill='#94b1b6')
        draw.ellipse((800,180,1040,420),fill='#f2d7a5')
        draw.polygon([(0,1440),(520,440),(1200,1440)],fill='#7d906d')
        image.save(original);image.close()
        plan,_=export_jpeg(original,dict(width_cm='30',height_cm='36'),result)
        # Exclusive creation prevents overwrites even if another process creates
        # the name between the first check and completion of the render.
        with args.output.open('xb') as destination,result.open('rb') as source:
            shutil.copyfileobj(source,destination)
    print(json.dumps(dict(file=str(args.output.resolve()),photo_px=plan['photo_px'],
        sheet_px=plan['sheet']['size_px'],position=plan['position_px'],right_white_px=59,bottom_white_px=472,dpi=300)))


if __name__=='__main__':main()

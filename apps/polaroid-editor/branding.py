"""Shared icon geometry; palette and identity come from the product theme."""
import json
from pathlib import Path
import sys
from PIL import Image,ImageDraw

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
THEME=json.loads((ROOT/'ui/theme.json').read_text(encoding='utf-8'))


def shapes():
    result=[('line',points,6) for points in (((48,84),(48,48),(84,48)),((172,48),(208,48),(208,84)),((208,172),(208,208),(172,208)),((84,208),(48,208),(48,172)))]
    if THEME['symbol']=='bottons':result += [('rect',(78,78,178,178,22),6),('ellipse',(103,103,153,153),6)]
    elif THEME['symbol']=='polaroid':result += [('rect',(83,68,173,188,5),6),('rect',(97,82,159,144,0),5),('line',((106,168),(150,168)),5)]
    else:
        result += [('rect',(78,73,178,183,5),6),('rect',(92,87,164,140,0),5),('line',((93,161),(163,161)),5)]
        result += [('line',((x,155),(x,171 if x in (99,139) else 167)),4) for x in (99,119,139,159)]
    return result


def glyph_svg(viewport=24):
    factor=viewport/256
    number=lambda value:format(value*factor,'.5g')
    result=[]
    for kind,values,width in shapes():
        if kind=='line':result.append('<polyline points="'+' '.join(number(x)+','+number(y) for x,y in values)+'"/>')
        elif kind=='rect':
            x,y,right,bottom,radius=values
            result.append(f'<rect x="{number(x)}" y="{number(y)}" width="{number(right-x)}" height="{number(bottom-y)}" rx="{number(radius)}"/>')
        else:
            x,y,right,bottom=values
            result.append(f'<ellipse cx="{number((x+right)/2)}" cy="{number((y+bottom)/2)}" rx="{number((right-x)/2)}" ry="{number((bottom-y)/2)}"/>')
    return ''.join(result)


def icon_image(size=64):
    image=Image.new('RGBA',(768,768));draw=ImageDraw.Draw(image);color='#f8faf6'
    box=lambda values:tuple(round(value*3) for value in values)
    draw.rounded_rectangle(box((8,8,248,248)),radius=174,fill=THEME['accent'])
    for kind,values,width in shapes():
        if kind=='line':
            points=[box(point) for point in values];draw.line(points,fill=color,width=width*3,joint='curve')
            for x,y in (points[0],points[-1]):draw.ellipse((x-width*1.5,y-width*1.5,x+width*1.5,y+width*1.5),fill=color)
        elif kind=='rect':draw.rounded_rectangle(box(values[:4]),radius=values[4]*3,outline=color,width=width*3)
        else:draw.ellipse(box(values),outline=color,width=width*3)
    return image.resize((size,size),Image.Resampling.LANCZOS)

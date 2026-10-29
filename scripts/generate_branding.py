"""Regenerate the browser tokens, inline glyph and multi-size Windows icon."""
import argparse
import importlib.util
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def generate(check=False):
    stale=[]
    for root in sorted((ROOT/'apps').glob('*-editor')):
        spec=importlib.util.spec_from_file_location('redlab_brand',root/'branding.py')
        brand=importlib.util.module_from_spec(spec);spec.loader.exec_module(brand)
        theme=brand.THEME
        tokens={key:value for key,value in theme.items() if isinstance(value,str) and value.startswith('#')}
        tokens.update(surface='#ffffff',green='var(--accent)',danger='#934d43',**{'danger-hover':'#783e35','warning':'#8c681f'})
        for role in ('accent','ink'):tokens[role+'-rgb']=' '.join(str(int(theme[role][i:i+2],16)) for i in (1,3,5))
        css='/* Generated from theme.json by scripts/generate_branding.py. */\n:root{'+''.join('--'+key+':'+value+';' for key,value in tokens.items())+'}\n'
        icons=(root/'ui/icons.js').read_text(encoding='utf-8')
        icons=re.sub(r"brand:\s*'[^']*'",lambda match:"brand:'"+brand.glyph_svg()+"'",icons,count=1)
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect x="8" y="8" width="240" height="240" rx="58" fill="'+theme['accent']+'"/><g fill="none" stroke="#f8faf6" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">'+brand.glyph_svg(256)+'</g></svg>\n'
        for path,content in ((root/'ui/theme.css',css),(root/'ui/icons.js',icons),(root/'assets'/f'{root.name}.svg',svg)):
            if check:
                if not path.exists() or path.read_text(encoding='utf-8')!=content:stale.append(str(path.relative_to(ROOT)))
            else:path.write_text(content,encoding='utf-8')
        import io
        data=io.BytesIO();brand.icon_image(256).save(data,'ICO',sizes=[(size,size) for size in (16,20,24,32,40,48,64,128,256)])
        path=root/'assets'/f'{root.name}.ico'
        if check:
            from PIL import Image
            data.seek(0)
            with Image.open(path) as stored,Image.open(data) as generated:
                sizes=generated.ico.sizes()
                if stored.ico.sizes()!=sizes or any(stored.ico.getimage(size).tobytes()!=generated.ico.getimage(size).tobytes() for size in sizes):stale.append(str(path.relative_to(ROOT)))
        else:path.write_bytes(data.getvalue())
    if stale:raise SystemExit('Atualize a identidade visual: '+', '.join(stale))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');generate(parser.parse_args().check)

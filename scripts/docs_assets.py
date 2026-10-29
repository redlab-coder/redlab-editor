"""Generate the repository banners from the same product geometry and palettes."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DESCRIPTIONS={
    'bottons-editor':'Modelos por foto. Folhas prontas para imprimir.',
    'polaroid-editor':'Enquadre, confira e prepare suas polaroids.',
    'medidas-editor':'Suas fotos, na medida certa.'}


def generate():
    brands=[]
    for product,description in DESCRIPTIONS.items():
        root=ROOT/'apps'/product
        spec=importlib.util.spec_from_file_location('redlab_banner',root/'branding.py')
        brand=importlib.util.module_from_spec(spec);spec.loader.exec_module(brand)
        theme=brand.THEME;brands.append((brand,theme))
        symbol='<rect x="8" y="8" width="240" height="240" rx="58" fill="'+theme['accent']+'"/><g fill="none" stroke="#f8faf6" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">'+brand.glyph_svg(256)+'</g>'
        image=root/'docs/images';image.mkdir(parents=True,exist_ok=True)
        banner=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="360" viewBox="0 0 1400 360">
<title>{theme['name']} · RedLab Editor</title>
<rect x=".5" y=".5" width="1399" height="359" rx="25" fill="{theme['bg']}" stroke="{theme['line']}"/>
<g font-family="Segoe UI,Arial,sans-serif"><text x="64" y="70" font-size="14" font-weight="600" letter-spacing="3" fill="{theme['muted']}">REDLAB EDITOR</text>
<text x="60" y="158" font-size="64" font-weight="650" letter-spacing="-2" fill="{theme['ink']}">{theme['name']}</text>
<text x="64" y="212" font-size="23" fill="{theme['muted']}">{description}</text>
<text x="64" y="302" font-size="16" fill="{theme['muted']}">Windows 10 e 11 · 64 bits · Processamento local</text></g>
<g transform="translate(1100 74) scale(.82)">{symbol}</g></svg>
'''
        (image/'banner.svg').write_text(banner,encoding='utf-8')
        download=f'''<svg xmlns="http://www.w3.org/2000/svg" width="252" height="54" viewBox="0 0 252 54"><title>Baixar {theme['name']} para Windows</title><rect width="252" height="54" rx="12" fill="{theme['accent']}"/><g fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M30 15v16m-6-6 6 6 6-6M21 34v5h18v-5"/></g><text x="58" y="33" font-family="Segoe UI,Arial,sans-serif" font-size="15" font-weight="600" fill="#fff">Baixar para Windows</text></svg>
'''
        (image/'download.svg').write_text(download,encoding='utf-8')
    tiles=[]
    for x,(brand,theme) in zip((892,1048,1204),brands):
        symbol='<rect x="8" y="8" width="240" height="240" rx="58" fill="'+theme['accent']+'"/><g fill="none" stroke="#f8faf6" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">'+brand.glyph_svg(256)+'</g>'
        tiles.append(f'<g transform="translate({x} 112) scale(.5)">{symbol}</g><text x="{x+64}" y="276" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="15" font-weight="600" fill="{theme["accent"]}">{theme["name"]}</text>')
    banner='''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="360" viewBox="0 0 1400 360"><title>RedLab Editor · ferramentas para impressão</title><rect x=".5" y=".5" width="1399" height="359" rx="25" fill="#f4f6f1" stroke="#e0e6db"/><g font-family="Segoe UI,Arial,sans-serif"><text x="64" y="70" font-size="14" font-weight="600" letter-spacing="3" fill="#62715f">FERRAMENTAS DE IMPRESSÃO</text><text x="60" y="158" font-size="64" font-weight="650" letter-spacing="-2" fill="#253c2d">RedLab Editor</text><text x="64" y="212" font-size="23" fill="#62715f">Enquadre. Prepare. Imprima.</text><text x="64" y="302" font-size="16" fill="#62715f">Três ferramentas · Processamento local · 300 dpi</text></g>'''+''.join(tiles)+'</svg>\n'
    (ROOT/'docs/images/banner.svg').write_text(banner,encoding='utf-8')


if __name__=='__main__':generate()

"""Per-image models, mixed-page production and portable project recovery."""
import io
import json
from pathlib import Path
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

OUT=Path(__file__).parent/'artifacts';OUT.mkdir(exist_ok=True)
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18735'
files=[]
for index,color in enumerate(('red','green','blue')):
    data=io.BytesIO();Image.new('RGB',(1000,800),color).save(data,'PNG')
    files.append(dict(name=f'Mista-{index+1}.png',mimeType='image/png',buffer=data.getvalue()))

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(URL);page.wait_for_function('editingAllowed&&!restoring')
    page.locator('#files').set_input_files(files)
    page.wait_for_function('photos.length===3&&!importing&&pagesCurrent()')
    page.locator('#zoom-number').fill('1.25');page.locator('#zoom-number').press('Enter')
    page.get_by_role('button',name='Editar Mista-2.png',exact=True).click()
    page.get_by_role('button',name='Button Redondo P',exact=True).click()
    page.get_by_role('button',name='Editar Mista-3.png',exact=True).click()
    page.get_by_role('button',name='Button Redondo P',exact=True).click()
    page.wait_for_function("pagesCurrent()&&sheetPlan.length===1&&document.querySelector('.sheet-open')?.disabled===false")
    assert page.evaluate('photos.map(p=>p.template)')==['square','round_p','round_p']
    page.get_by_role('button',name='Editar Mista-1.png',exact=True).click()
    assert page.locator('[data-template=square]').get_attribute('aria-pressed')=='true'
    assert page.locator('#zoom-number').input_value()=='1.25'
    assert not page.locator('#safe-guide').is_visible()
    page.get_by_role('button',name='Editar Mista-2.png',exact=True).click()
    assert page.locator('[data-template=round_p]').get_attribute('aria-pressed')=='true'
    assert page.locator('#zoom-number').input_value()=='1.00'
    assert page.locator('#safe-guide').is_visible()
    with page.expect_download() as event:page.locator('#export').click()
    event.value.save_as(OUT/'mista.jpg');before=(OUT/'mista.jpg').read_bytes()
    with Image.open(OUT/'mista.jpg') as image:assert image.size==(1795,1205) and image.info['dpi']==(300,300)
    page.get_by_role('button',name='Ampliar folha 1',exact=True).click()
    with page.expect_download() as event:page.locator('#download-sheet').click()
    event.value.save_as(OUT/'mista-ampliada.jpg')
    assert (OUT/'mista-ampliada.jpg').read_bytes()==before
    page.keyboard.press('Escape')
    with page.expect_download() as event:page.locator('#save-project').click()
    event.value.save_as(OUT/'misto.bottons')
    page.reload();page.wait_for_function('photos.length===3&&editingAllowed&&!restoring&&pagesCurrent()')
    assert page.evaluate('photos.map(p=>p.template)')==['square','round_p','round_p']
    # An older session only had a global model. It migrates every item explicitly.
    page.evaluate("()=>{activeTemplate='round_m';photos.forEach(p=>delete p.template);saveSession();}")
    page.reload();page.wait_for_function('photos.length===3&&editingAllowed&&!restoring&&pagesCurrent()')
    assert page.evaluate('photos.every(p=>p.template==="round_m")')
    # Opening errors are atomic; the loaded batch is still available.
    page.locator('#project-file').set_input_files(dict(name='invalido.bottons',mimeType='application/zip',buffer=b'broken'))
    page.wait_for_function('!importing');assert page.evaluate('photos.length')==3
    page.locator('#open-project').click();page.locator('#open-dialog').wait_for(state='visible')
    page.get_by_role('button',name='Cancelar',exact=True).click()
    page.locator('#clear-all').click();page.locator('#clear-confirm').click()
    page.wait_for_function('!photos.length&&!clearing')
    page.locator('#project-file').set_input_files(OUT/'misto.bottons')
    page.wait_for_function('photos.length===3&&!importing&&pagesCurrent()&&sheetPlan.length===1')
    assert page.evaluate('photos.map(p=>p.template)')==['square','round_p','round_p']
    with page.expect_download() as event:page.locator('#export').click()
    event.value.save_as(OUT/'mista-restaurada.jpg')
    assert (OUT/'mista-restaurada.jpg').read_bytes()==before
    # The new project actions stay inside the screen at every family breakpoint.
    for width in (1440,1024,768,520,390,320):
        page.set_viewport_size(dict(width=width,height=900))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        assert page.locator('#open-project').is_visible() and page.locator('#save-project').is_visible()
        page.screenshot(path=str(OUT/f'misto-{width}.png'),full_page=True)
    # Other tabs must preserve each model and cannot mutate them while read-only.
    second=context.new_page();second.goto(URL);second.wait_for_function('photos.length===3&&!restoring')
    assert second.locator('[data-template=round_g]').is_disabled()
    second.locator('#takeover').click();second.wait_for_function('editingAllowed&&!restoring')
    assert second.evaluate('photos.map(p=>p.template)')==['square','round_p','round_p']
    second.close();page.close()
    assert not errors,errors
    print(json.dumps(dict(individual_models='OK',mixed_sheet='1 JPEG',full_quality_page_download='OK',project_and_legacy_session='OK',responsive='320–1440',tab_transfer='OK',errors=errors)))
    browser.close()

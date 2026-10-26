"""Product flows, print example, recoverable failures and responsive controls."""
import io
import json
from pathlib import Path
import sys
import zipfile
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/artifacts';OUT.mkdir(exist_ok=True)


def photo_file(name='Paisagem.png',size=(1200,800)):
    image=Image.new('RGB',size,'#ddd3bd');draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,size[0],size[1]//2),fill='#9eb7b3')
    draw.ellipse((size[0]*.65,size[1]*.12,size[0]*.8,size[1]*.35),fill='#edd4a0')
    draw.polygon([(0,size[1]),(size[0]*.4,size[1]*.3),(size[0],size[1])],fill='#74896e')
    data=io.BytesIO();image.save(data,'PNG');image.close()
    return dict(name=name,mimeType='image/png',buffer=data.getvalue())


def run(url):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(url);page.wait_for_function("!document.querySelector('#add').disabled")
        page.locator('#files').set_input_files([photo_file(),dict(name='invalida.png',mimeType='image/png',buffer=b'broken'),photo_file('Retrato.png',(800,1200))])
        page.wait_for_function("document.querySelector('#count').textContent==='2'&&!document.querySelector('#add').disabled")
        page.locator('#width-cm').fill('30');page.locator('#height-cm').fill('36');page.locator('#apply-size').click()
        page.wait_for_function("document.querySelector('#output-summary').textContent.includes('3602 × 4724')")
        page.wait_for_function("!document.querySelector('#review-photo').disabled")
        assert '30×40' in page.locator('#output-summary').inner_text()
        assert 'Pronta para exportar' not in page.locator('#sheets').inner_text()
        # Pending crop cannot be silently included.
        page.locator('#export-photo').click();page.locator('#export-dialog').wait_for(state='visible')
        assert page.locator('#export-ready').is_disabled()
        page.get_by_role('button',name='Voltar e conferir').click()
        page.locator('#review-photo').click()
        # Pan does no storage or network work until pointer release.
        box=page.locator('#tile-frame').bounding_box();assert box
        page.locator('#zoom-number').fill('1.50');page.locator('#zoom-number').press('Tab')
        page.wait_for_timeout(350)
        center=page.locator('#tile-frame').bounding_box();x=center['x']+center['width']/2;y=center['y']+center['height']/2
        page.evaluate("()=>{window.__moves=0;const old=Storage.prototype.setItem;Storage.prototype.setItem=function(...args){window.__moves++;return old.apply(this,args)};}")
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-25,y+20,steps=10)
        assert page.evaluate('window.__moves')==0
        page.mouse.up();page.wait_for_timeout(400)
        page.locator('#center').click();page.wait_for_timeout(300)
        page.locator('#zoom-number').fill('1');page.locator('#zoom-number').press('Tab');page.wait_for_timeout(300)
        page.locator('#review-photo').click()
        with page.expect_download(timeout=60000) as download:
            page.locator('#export-photo').click()
        result=download.value;result.save_as(OUT/'example-30x36.jpg')
        with Image.open(OUT/'example-30x36.jpg') as image:
            assert image.size==(3602,4724) and image.info['dpi']==(300,300)
            assert min(image.getpixel((3570,100)))>=253 and min(image.getpixel((100,4600)))>=253
        # Explicit batch size assignment and independent per-photo settings.
        page.locator('#select-all').check();page.locator('#width-cm').fill('12,7');page.locator('#height-cm').fill('');page.locator('#apply-selection').click()
        page.wait_for_function("!document.querySelector('#apply-selection').disabled")
        page.wait_for_function("[...document.querySelectorAll('.photo-row small')].filter(e=>e.textContent.includes('12,7')).length===2")
        page.locator('#width-cm').fill('10');page.locator('#height-cm').fill('10');page.locator('#apply-size').click();page.wait_for_timeout(350)
        page.locator('#fit-mode').select_option('contain');page.wait_for_timeout(350)
        assert page.locator('#content-outline').is_visible()
        assert 'branco' in page.locator('#resolution').inner_text().lower()
        page.locator('#position').select_option('bottom_right');page.wait_for_timeout(350)
        assert 'Canto inferior direito' in page.locator('#output-summary').inner_text()
        page.locator('#sheet').select_option('40x50');page.wait_for_timeout(350)
        assert '40×50' in page.locator('#output-summary').inner_text()
        # Save and reload the session with its original metadata.
        with page.expect_download() as saved:
            page.locator('#save-project').click()
        saved.value.save_as(OUT/'example.medidas')
        page.reload();page.wait_for_function("document.querySelector('#count').textContent==='2'&&!document.querySelector('#add').disabled")
        page.wait_for_function("document.querySelector('#output-summary').textContent.includes('40×50')")
        page.locator('#metadata-details').evaluate('e=>{e.open=true;}')
        assert 'Sem perfil' in page.locator('#metadata-text').text_content()
        page.locator('#metadata-details').evaluate('e=>{e.open=false;}')
        page.locator('#clear-all').click();page.locator('#clear-cancel').click();assert page.locator('#count').inner_text()=='2'
        page.locator('#clear-all').click();page.locator('#clear-confirm').click();page.wait_for_function("document.querySelector('#count').textContent==='0'")
        page.locator('#project-file').set_input_files(OUT/'example.medidas')
        page.wait_for_function("document.querySelector('#count').textContent==='2'&&!document.querySelector('#add').disabled")
        # Takeover must preserve the batch and not steal back on focus.
        second=context.new_page();second.goto(url);second.wait_for_selector('#session-banner:visible');second.locator('#takeover').click()
        second.wait_for_function("document.querySelector('#count').textContent==='2'&&!document.querySelector('#add').disabled")
        page.bring_to_front();page.wait_for_timeout(250);assert page.locator('#session-banner').is_visible()
        page.locator('#takeover').click()
        try:page.wait_for_function("!document.querySelector('#add').disabled",timeout=8000)
        except Exception:
            state='({editingAllowed,acquiring,restoring,importing,exporting,clearing,sessionRevision,count:photos.length,pendingRestore,restoreTask:!!restoreTask,toast:document.querySelector(\"#toast\").textContent})'
            print('TAB_FAILURE',page.evaluate(state),second.evaluate(state),flush=True)
            raise
        second.close()
        # Screenshot of native product style, with both internal and external white.
        page.locator('#position').select_option('top_left');page.wait_for_timeout(350)
        page.screenshot(path=str(ROOT/'docs/images/contain.png'),full_page=True)
        page.locator('#sheet').select_option('auto');page.wait_for_timeout(300)
        page.locator('#fit-mode').select_option('cover');page.wait_for_timeout(300)
        page.locator('#width-cm').fill('30');page.locator('#height-cm').fill('36');page.locator('#apply-size').click()
        page.wait_for_function("document.querySelector('#output-summary').textContent.includes('3602 × 4724')&&!document.querySelector('#review-photo').disabled")
        page.screenshot(path=str(OUT/'workspace.png'),full_page=True)
        (ROOT/'docs/images').mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(ROOT/'docs/images/workspace.png'),full_page=True)
        for width in (1366,1024,768,740,600,390,320):
            page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(150)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Overflow at {width}'
            assert page.locator('#apply-size').is_visible()
            page.screenshot(path=str(OUT/f'layout-{width}.png'),full_page=True)
        assert not errors,errors
        print(json.dumps(dict(browser='OK',example_30x36='OK',pending_review='OK',pan_no_storage='OK',
            invalid_import_continues='OK',batch_sizes='OK',contain_and_position='OK',project_roundtrip='OK',
            reload_and_tab_takeover='OK',responsive_widths=[1366,1024,768,740,600,390,320],errors=errors)))
        context.close();browser.close()


if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18780')

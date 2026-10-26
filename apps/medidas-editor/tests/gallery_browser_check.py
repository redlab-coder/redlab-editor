"""Gallery geometry, lazy loading, cache invalidation and exceptional export notices."""
import io
import json
from pathlib import Path
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def run(url):
    data=io.BytesIO();Image.new('RGB',(400,300),'#578caa').save(data,'PNG')
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1024,'height':900},accept_downloads=True)
        page=context.new_page();errors=[];requests=[];active=set();peak=0
        page.on('pageerror',lambda error:errors.append(str(error)))
        def requested(request):
            nonlocal peak
            if request.url.endswith('/api/preview') and request.post_data_json.get('maximum')==320:
                requests.append(request);active.add(request);peak=max(peak,len(active))
        page.on('request',requested)
        page.on('requestfinished',lambda request:active.discard(request))
        page.on('requestfailed',lambda request:active.discard(request))
        page.goto(url);page.wait_for_function("!document.querySelector('#add').disabled")
        page.locator('#files').set_input_files([dict(name=f'Foto-{index:02}.png',mimeType='image/png',buffer=data.getvalue()) for index in range(12)])
        page.wait_for_function("photos.length===12&&!importing")
        assert page.locator('#apply-selection').is_hidden()
        page.locator('#select-all').check()
        page.locator('#width-cm').fill('15');page.locator('#height-cm').fill('20');page.locator('#apply-selection').click()
        page.wait_for_function("photos.every(photo=>photo.plan)&&!importing")
        page.locator('#sheets').scroll_into_view_if_needed()
        page.wait_for_function("!cardLoading&&cardQueue.length===0")
        assert 0<len(requests)<12,'Offscreen cards must not render the whole batch'
        assert peak==1,'Composition previews must use one request at a time'
        first=page.locator('.preparation-card').first
        first.locator('img').wait_for(state='visible')
        source=first.locator('img').get_attribute('src');count=len(requests)
        page.locator('#review-photo').click()
        page.wait_for_function("!cardLoading&&cardQueue.length===0")
        assert first.locator('img').get_attribute('src')==source and len(requests)==count
        # Each composition changes only when its settings change.
        page.locator('#position').select_option('bottom_right')
        page.wait_for_function("!current().planning&&!cardLoading&&cardQueue.length===0")
        page.wait_for_function("old=>{const img=document.querySelector('.preparation-card img');return !img.hidden&&img.complete&&img.naturalWidth>0&&img.src!==old}",arg=source)
        updated=first.locator('img').get_attribute('src')
        pixels=page.evaluate("""async url=>{const bitmap=await createImageBitmap(await(await fetch(url)).blob());const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;const ctx=canvas.getContext('2d');ctx.drawImage(bitmap,0,0);bitmap.close();return [...ctx.getImageData(0,0,1,1).data];}""",updated)
        assert pixels==[255,255,255,255],'Bottom-right positioning must leave the top-left white'
        page.locator('#sheets').evaluate('el=>el.scrollLeft=el.scrollWidth')
        page.wait_for_function("!cardLoading&&cardQueue.length===0&&!!document.querySelector('.preparation-card:last-child img').src")
        assert len(requests)<24 and peak==1
        page.locator('.preparation-card').last.click()
        page.wait_for_function("!document.querySelector('#sheet-dialog-image').hidden")
        page.get_by_role('button',name='Fechar prévia').click()
        page.wait_for_function("!urls.has('dialog')&&openedPreview===null")
        # A failed export remains visible without bringing back the permanent panel.
        page.locator('#fit-mode').select_option('contain');page.wait_for_function("!current().planning")
        page.route('**/api/export/status',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(dict(state='failed',done=1,total=1,success=0,error='Falha simulada de disco',items=[dict(name='Foto-00.png',error='Arquivo indisponível')]))))
        page.locator('#export-photo').click()
        page.locator('#errors-dialog').wait_for(state='visible')
        assert 'Arquivo indisponível' in page.locator('#job-errors').inner_text()
        assert 'Falha simulada de disco' in page.locator('#job-errors').inner_text()
        page.get_by_role('button',name='Fechar avisos').click()
        page.unroute('**/api/export/status')
        # Native single-file download from the enlarged preview.
        first.click();page.wait_for_function("!document.querySelector('#sheet-dialog-image').hidden")
        with page.expect_download(timeout=60000):page.locator('#export-preview').click()
        page.wait_for_function('!exporting')
        assert page.locator('#job-panel').count()==0
        page.locator('#clear-all').click();page.locator('#clear-confirm').click()
        page.wait_for_function('photos.length===0&&!clearing')
        page.wait_for_function('!cardLoading')
        assert page.evaluate('cardPreviews.size===0&&urls.size===0')
        assert not errors,errors
        print(json.dumps(dict(gallery_lazy_loading='OK',single_preview_request='OK',cache_reuse_and_invalidation='OK',composition_white='OK',enlarged_export='OK',failure_notice='OK',resource_release='OK',errors=errors)))
        context.close();browser.close()


if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18780')

"""Safe broad drop, gradual filters, clear/retry and independent tab ownership."""
import hashlib
import io
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright


def run(url):
    output=Path(__file__).parent/'artifacts/general';output.mkdir(parents=True,exist_ok=True)
    files=[]
    for n in range(3):
        image=Image.new('RGB',(1200,800),(80,120,100));ImageDraw.Draw(image).ellipse((500,300,700,500),fill=(230,30,30))
        path=output/f'Foto-{n}.png';image.save(path);files.append(path)
    hashes={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    metadata=output/'Thumbs.db';metadata.write_bytes(b'Windows metadata')
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();errors=[];uploads=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:uploads.append(request) if request.url.endswith('/api/upload') else None)
        page.goto(url);page.wait_for_function('editingAllowed&&!restoring')
        assert page.title()=='Bottons Editor'
        assert page.locator('#review-photo,#filter-review,[aria-keyshortcuts="F"]').count()==0
        data=page.evaluate_handle("()=>{const d=new DataTransfer();d.items.add(new File([Uint8Array.from([137,80,78,71])],'ignored.png',{type:'image/png'}));return d;}")
        # Use a real file for a native Files drag rather than merely calling importFiles.
        data=page.evaluate_handle("bytes=>{const d=new DataTransfer();d.items.add(new File([new Uint8Array(bytes)],'Arrastada.png',{type:'image/png'}));return d;}",list(files[0].read_bytes()))
        page.locator('.library').dispatch_event('dragenter',{'dataTransfer':data})
        page.locator('#empty-editor h3').dispatch_event('dragenter',{'dataTransfer':data})
        page.locator('.library').dispatch_event('dragleave',{'dataTransfer':data})
        assert page.locator('#import-area').evaluate("el=>el.classList.contains('file-drop-active')")
        page.locator('#empty-editor h3').dispatch_event('drop',{'dataTransfer':data})
        page.wait_for_function('photos.length===1&&!importing')
        assert len(uploads)==1
        page.locator('#files').set_input_files([str(path) for path in files[1:]]+[str(metadata)])
        page.wait_for_function('photos.length===3&&!importing');assert len(uploads)==3
        before=page.evaluate('photos.map(photo=>photo.edits)');page.keyboard.press('f')
        assert page.evaluate('photos.map(photo=>photo.edits)')==before
        page.locator('.adjustments').dispatch_event('drop',{'dataTransfer':data});assert len(uploads)==3
        for template in ('square','round_g','round_m','round_p'):
            page.locator(f'[data-template={template}]').click()
            page.wait_for_function('key=>activeTemplate===key&&!importing',arg=template)
            page.locator('#brightness').evaluate("el=>{el.value='10';el.dispatchEvent(new Event('input',{bubbles:true}));}")
            assert page.evaluate('current().edits.brightness')==1.01
            page.locator('#brightness-number').fill('0.01');page.locator('#brightness-number').press('Enter')
            assert page.evaluate('current().edits.brightness')==1.0001
            page.locator('#brightness-zero').click()
        readonly=context.new_page();readonly.goto(url);readonly.wait_for_function('photos.length===3&&!restoring')
        assert readonly.locator('#clear-all').is_disabled()
        for _ in range(3):
            readonly.locator('#takeover').click();readonly.wait_for_function('editingAllowed&&!restoring');page.wait_for_function('!editingAllowed')
            page.evaluate("window.dispatchEvent(new Event('focus'))");assert not page.evaluate('editingAllowed')
            page.locator('#takeover').click();page.wait_for_function('editingAllowed&&!restoring');readonly.wait_for_function('!editingAllowed')
        readonly.close()
        page.locator('#clear-all').click();page.locator('#clear-cancel').click();assert page.evaluate('photos.length')==3
        page.route('**/api/clear',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Falha simulada"}'))
        page.locator('#clear-all').click();page.locator('#clear-confirm').click();page.wait_for_function('!clearing')
        assert page.evaluate('photos.length')==3 and page.locator('#clear-dialog').is_visible()
        page.unroute('**/api/clear');page.locator('#clear-confirm').click();page.wait_for_function('!photos.length&&!clearing')
        assert page.evaluate('previewSources.size===0&&objectUrls.size===0&&sheetCache.size===0&&orientedSource===null')
        assert page.evaluate('activeTemplate')=='round_p'
        page.reload();page.wait_for_function('editingAllowed&&!restoring');assert page.evaluate('photos.length')==0
        for path,digest in hashes.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        assert not errors,errors
        browser.close()
    print(json.dumps({'expanded_drop':'OK','no_review_workflow':'OK','gradual_filters_all_templates':'OK',
                      'clear_cancel_failure_retry':'OK','originals_untouched':'OK','tab_transfer':'OK'}))


if __name__=='__main__':run(sys.argv[1])

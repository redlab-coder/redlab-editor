"""Browser checks for the shared family and each product's own interaction colors."""
import io
import json
from pathlib import Path
import sys
import threading
from http.server import ThreadingHTTPServer
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def run(product,url):
    theme=json.loads((ROOT/'apps'/product/'ui/theme.json').read_text(encoding='utf-8'))
    rgb=lambda hex:'rgb('+', '.join(str(int(hex[i:i+2],16)) for i in (1,3,5))+')'
    output=ROOT/'apps'/product/'tests/artifacts';output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as play:
        browser=play.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport=dict(width=1440,height=1000))
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/api/heartbeat',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(dict(ok=True,update=dict(state='ready',version='9999.0.0')))))
        page.goto(url);page.wait_for_function('editingAllowed&&!bootRecovery&&!restoring')
        assert page.locator('.brand-family').inner_text()=='REDLAB EDITOR'
        page.locator('#drop').hover()
        page.wait_for_function("color=>getComputedStyle(document.querySelector('#drop')).backgroundColor===color",arg=rgb(theme['soft']))
        transfer=page.evaluate_handle("()=>{const data=new DataTransfer();data.items.add(new File(['test'],'cor.png',{type:'image/png'}));return data;}")
        page.dispatch_event('#import-area','dragenter',dict(dataTransfer=transfer))
        page.wait_for_function("color=>getComputedStyle(document.querySelector('#import-area'),'::after').borderTopColor===color",arg=rgb(theme['accent']))
        page.screenshot(path=str(output/'family-drop-desktop.png'))
        page.dispatch_event('#import-area','dragleave',dict(dataTransfer=transfer))
        assert not page.locator('#import-area').evaluate("e=>e.classList.contains('file-drop-active')")
        picture=io.BytesIO();Image.new('RGB',(600,800),'#b9a18a').save(picture,'PNG')
        page.locator('#files').set_input_files([dict(name='Foto de teste.png',mimeType='image/png',buffer=picture.getvalue())])
        page.wait_for_function('photos.length===1&&!importing')
        if product=='medidas-editor':
            page.locator('#width-cm').fill('30');page.locator('#height-cm').fill('36');page.locator('#apply-size').click()
            page.wait_for_function('photos[0].plan&&!photos[0].planning')
        for width in (1440,1024,768,520,390,320):
            page.set_viewport_size(dict(width=width,height=1000))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(product,width)
            for selector in ('#save-project','#open-project','#export','#update-status'):
                box=page.locator(selector).bounding_box();assert box and box['x']>=0 and box['x']+box['width']<=width,(product,width,selector,box)
            assert page.evaluate("(()=>{const a=document.querySelector('.brand').getBoundingClientRect(),b=document.querySelector('.header-actions').getBoundingClientRect();return a.right<=b.left||a.bottom<=b.top})()"),(product,width)
            if width in (1440,390):page.screenshot(path=str(output/f'family-editor-{width}.png'),full_page=True)
        page.locator('#help').click();assert page.locator('#help-dialog').is_visible();page.keyboard.press('Escape')
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('#update-status').evaluate('e=>getComputedStyle(e).animationName')=='none'
        assert not errors,errors
        context.close()
        touch=browser.new_context(viewport=dict(width=390,height=844),is_mobile=True,has_touch=True)
        page=touch.new_page();page.goto(url);page.wait_for_function('editingAllowed&&!bootRecovery&&!restoring')
        assert page.locator('#add').bounding_box()['height']>=38
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        touch.close();browser.close()
    print(json.dumps(dict(product=product,own_hover_and_drop_palette='OK',widths=[320,390,520,768,1024,1440],touch_targets='OK',reduced_motion='OK',errors=errors)),flush=True)


if __name__=='__main__':
    product=sys.argv[1]
    if len(sys.argv)>2:run(product,sys.argv[2])
    else:
        sys.path.insert(0,str(ROOT/'apps'/product));import app
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);server.updater=None;server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:run(product,f'http://127.0.0.1:{server.server_port}')
        finally:server.shutdown();server.server_close();app.IMAGES.clear();app.CACHE.clear()

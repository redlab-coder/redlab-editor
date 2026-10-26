"""Import boundaries, real cancellation, rotated pan and repeated tab handoff."""
import base64
import io
import json
from pathlib import Path
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def run(url):
    buffer=io.BytesIO();Image.new('RGB',(1200,800),'#86765c').save(buffer,'PNG',dpi=(300,300))
    encoded=base64.b64encode(buffer.getvalue()).decode()
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1366,'height':900},accept_downloads=True)
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(url);page.wait_for_function("!document.querySelector('#add').disabled")
        def drop(selector,types='Files'):
            page.evaluate('''({selector,encoded,types})=>{
                const data=new DataTransfer();if(types==='Files'){
                    const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
                    data.items.add(new File([bytes],'Medidas.png',{type:'image/png'}));
                }else data.setData('text/plain','text');
                for(const type of ['dragenter','dragover','drop'])document.querySelector(selector).dispatchEvent(new DragEvent(type,{bubbles:true,cancelable:true,dataTransfer:data}));
            }''',dict(selector=selector,encoded=encoded,types=types))
        drop('#canvas-area');page.wait_for_function("document.querySelector('#count').textContent==='1'&&!document.querySelector('#add').disabled")
        drop('.adjustments');drop('#canvas-area',types='text');page.wait_for_timeout(150)
        assert page.locator('#count').inner_text()=='1'
        assert page.locator('#width-cm').input_value()==''
        page.locator('#metadata-details').evaluate('e=>{e.open=true;}')
        page.locator('#use-metadata').click();page.wait_for_function("document.querySelector('#output-summary').textContent.includes('10,16')")
        page.locator('#width-cm').fill('30.6');page.locator('#height-cm').fill('40');page.locator('#apply-size').click()
        page.wait_for_function("!document.querySelector('#apply-size').disabled")
        assert page.evaluate("current().plan.sheet.id")!='30x40'
        page.locator('#width-cm').fill('999');page.locator('#height-cm').fill('999');page.locator('#apply-size').click()
        page.wait_for_function("!document.querySelector('#apply-size').disabled")
        assert 'Nenhuma folha' in page.locator('#toast').inner_text()
        assert page.locator('#width-cm').input_value()=='30,6'
        page.locator('#width-cm').fill('36');page.locator('#height-cm').fill('30');page.locator('#apply-size').click()
        page.wait_for_function("current()?.plan?.sheet.rotation===90&&!document.querySelector('#review-photo').disabled")
        page.locator('#zoom-number').fill('2');page.locator('#zoom-number').press('Tab')
        page.wait_for_function("!current().planning")
        box=page.locator('#tile-frame').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+1500,y,steps=5)
        before=page.evaluate('current().settings.cy')
        page.mouse.move(x+1490,y,steps=2)
        after=page.evaluate('current().settings.cy')
        assert after<before,'The rotated crop must respond immediately after reversing at an edge'
        page.mouse.up();page.wait_for_function('!current().planning')
        # Clearing failure keeps the original batch, then retry releases caches.
        page.route('**/api/clear',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Falha simulada"}'))
        page.locator('#clear-all').click();page.locator('#clear-confirm').click()
        page.wait_for_function("!document.querySelector('#clear-confirm').disabled")
        assert page.locator('#count').inner_text()=='1';assert page.locator('#clear-dialog').is_visible()
        page.locator('#clear-cancel').click();page.unroute('**/api/clear')
        # A real maximum-sheet export can be cancelled through the UI.
        page.locator('#fit-mode').select_option('contain');page.wait_for_function('!current().planning')
        page.locator('#width-cm').fill('61');page.locator('#height-cm').fill('250');page.locator('#apply-size').click()
        page.wait_for_function("current()?.plan?.sheet.id==='61x250'&&!current().planning&&!importing")
        page.locator('#export-photo').click();page.wait_for_function("!document.querySelector('#cancel-export').disabled")
        page.locator('#cancel-export').click()
        page.wait_for_function("document.querySelector('#job-title').textContent==='Exportação cancelada'&&!exporting",timeout=30000)
        assert page.locator('#download-result').is_hidden();assert page.locator('#count').inner_text()=='1'
        # Three explicit handoff cycles with a loaded batch.
        second=context.new_page();second.goto(url);second.wait_for_selector('#session-banner:visible')
        for _ in range(3):
            second.locator('#takeover').click();second.wait_for_function("editingAllowed&&!restoring&&photos.length===1")
            page.bring_to_front();page.wait_for_timeout(150);assert page.locator('#session-banner').is_visible()
            page.locator('#takeover').click();page.wait_for_function("editingAllowed&&!restoring&&photos.length===1")
        second.close()
        page.locator('#clear-all').click();page.locator('#clear-confirm').click()
        page.wait_for_function("photos.length===0&&!clearing")
        assert page.evaluate('sources.size===0&&urls.size===0&&oriented===null')
        assert not errors,errors
        print(json.dumps(dict(expanded_drop='OK',metadata_opt_in='OK',physical_fit_errors='OK',
            rotated_edge_reversal='OK',clear_failure_retry='OK',real_maximum_export_cancel='OK',
            repeated_tab_takeover='OK',resource_release='OK',errors=errors)))
        context.close();browser.close()


if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:18780')

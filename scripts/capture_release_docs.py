"""Capture the real current interfaces using original, synthetic demo artwork."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PRODUCTS=('bottons-editor','polaroid-editor','medidas-editor')


def load(path):
    spec=importlib.util.spec_from_file_location('redlab_demo',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def capture(product):
    sys.path.insert(0,str(ROOT/'apps'/product));import app
    server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);server.updater=None;server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    output=ROOT/'apps'/product/'docs/images';demo=ROOT/'artifacts/docs-demo'/product;demo.mkdir(parents=True,exist_ok=True)
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport=dict(width=1440,height=1000),device_scale_factor=1)
            renderer=context.new_page();files=[]
            if product=='bottons-editor':
                art=load(ROOT/'apps/bottons-editor/scripts/capture_docs.py').artwork
                for title,bg,ink,leaf in [('Memórias','#f4f0e5','#365e43','#a4b38e'),('Afeto','#e7eddf','#3e5b3f','#9ba982'),('Instantes','#365e43','#f4f0e5','#6f8d6b')]:
                    renderer.set_content('<body style="margin:0">'+art(title,bg,ink,leaf)+'</body>');path=demo/(title+'.png');renderer.locator('svg').screenshot(path=str(path));files.append(path)
            elif product=='polaroid-editor':files=load(ROOT/'apps/polaroid-editor/scripts/demo_art.py').make_demos(demo)
            else:
                for title,bg,far,near in [('Dias de luz','#f2e9dc','#d5bea2','#8b6647'),('Horizontes','#e9eee5','#bac4a4','#566f51'),('Tempo de guardar','#eee7df','#c7b6a6','#7b6455')]:
                    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="3840" height="4608" viewBox="0 0 1200 1440"><rect width="1200" height="1440" fill="{bg}"/><circle cx="880" cy="330" r="128" fill="#d29b70"/><path d="M0 910 470 340 1200 1050V1440H0Z" fill="{far}"/><path d="M0 1100 350 810 800 670 1200 930V1440H0Z" fill="{near}"/><text x="100" y="1200" fill="#fffaf0" font-family="Georgia,serif" font-size="74" font-style="italic">{title}</text><text x="105" y="1280" fill="#fffaf0" font-family="Segoe UI,Arial,sans-serif" font-size="22" letter-spacing="4">FEITO PARA GUARDAR</text></svg>'''
                    renderer.set_viewport_size(dict(width=3840,height=4608));renderer.set_content('<body style="margin:0">'+svg+'</body>');path=demo/(title+'.png');renderer.locator('svg').screenshot(path=str(path));files.append(path)
            renderer.close()
            page=context.new_page();page.emulate_media(reduced_motion='reduce');errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}');page.wait_for_function("typeof editingAllowed!=='undefined'&&editingAllowed&&!bootRecovery&&!restoring")
            page.locator('#files').set_input_files([str(path) for path in files]);page.wait_for_function('photos.length===3&&!importing')
            if product=='bottons-editor':
                for path in files[1:]:
                    page.get_by_role('button',name='Editar '+path.name,exact=True).click();page.locator('[data-template=round_p]').click()
                page.wait_for_function("pagesCurrent()&&sheetPlan.length===1&&[...document.querySelectorAll('.sheet-open')].every(b=>!b.disabled)")
                page.get_by_role('button',name='Editar '+files[1].name,exact=True).click()
            elif product=='polaroid-editor':
                for path in files:
                    page.get_by_role('button',name='Editar '+path.name,exact=True).click();page.wait_for_function("!document.querySelector('#review-photo').disabled");page.locator('#review-photo').click()
                page.get_by_role('button',name='Editar '+files[0].name,exact=True).click()
                page.wait_for_function("[...document.querySelectorAll('.sheet-card img')].every(img=>img.complete&&img.naturalWidth>0)")
            else:
                page.locator('#select-all').check();page.locator('#width-cm').fill('30');page.locator('#height-cm').fill('36');page.locator('#apply-selection').click()
                page.wait_for_function('photos.every(p=>p.plan&&!p.planning)&&!importing')
                page.locator('#select-all').uncheck()
                for path in files:
                    page.get_by_role('button',name='Editar '+path.name,exact=True).click();page.wait_for_function("!document.querySelector('#review-photo').disabled");page.locator('#review-photo').click()
                page.get_by_role('button',name='Editar '+files[0].name,exact=True).click()
                page.wait_for_function('!cardLoading&&cardQueue.length===0')
            page.wait_for_function("document.querySelector('#toast').hidden")
            page.wait_for_timeout(300)
            page.screenshot(path=str(output/'workspace.png'),full_page=True)
            page.locator('.sheet-open' if product!='medidas-editor' else '.preparation-card').first.click()
            page.locator('#sheet-dialog-image').wait_for(state='visible');page.locator('#sheet-dialog-image').evaluate('image=>image.decode()')
            page.locator('#sheet-dialog').screenshot(path=str(output/'sheet.png'));page.keyboard.press('Escape')
            page.set_viewport_size(dict(width=390,height=844));page.screenshot(path=str(output/'mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert not errors,errors
            browser.close()
        print(product+': capturas atualizadas',flush=True)
    finally:server.shutdown();server.server_close();app.CACHE.clear();app.IMAGES.clear()


if __name__=='__main__':
    if len(sys.argv)>1:capture(sys.argv[1])
    else:
        for product in PRODUCTS:subprocess.run([sys.executable,__file__,product],check=True)

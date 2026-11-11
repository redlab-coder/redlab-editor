"""Exercise montage interaction, automatic layouts and scoped session state."""
from collections import Counter
from pathlib import Path
import sys
import zipfile

from playwright.sync_api import expect, sync_playwright

from browser_check import photo_file

OUT = Path(__file__).resolve().parent / 'artifacts'


def run(url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True, has_touch=True)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url)
        expect(page.locator('#tools-home')).to_be_visible()
        page.screenshot(path=str(OUT / 'tools-home.png'))
        page.locator('#tools-home [data-tool="medidas"]').click()
        expect(page.locator('#add')).to_be_enabled()
        page.locator('#files').set_input_files(photo_file('Medidas.png'))
        expect(page.locator('#count')).to_have_text('1')
        expect(page.locator('#width-cm')).to_be_enabled()
        page.locator('#width-cm').fill('30')
        page.locator('#height-cm').fill('36')
        page.locator('#tool-nav [data-tool="montagem"]').click()
        page.locator('#montage-files').set_input_files([photo_file(f'Foto-{n:02}.png', (500, 700)) for n in range(1, 21)])
        expect(page.locator('#montage-count')).to_have_text('20', timeout=30000)
        expect(page.locator('#montage-export')).to_be_disabled()
        cards = page.locator('#montage-list .montage-photo')
        center = page.locator('#montage-preview-image')
        selection = page.locator('#montage-selection-count')
        expect(page.locator('#montage-list input')).to_have_count(0)
        expect(center).to_be_visible()
        cards.nth(1).click()
        expect(cards.nth(1)).to_have_attribute('aria-pressed', 'true')
        expect(page.locator('#montage-photo-title')).to_have_text('Foto-02.png')
        expect(page.locator('#montage-photo-size')).to_have_text('Sem tamanho')
        expect(center).to_have_attribute('alt', 'Foto-02.png')
        center.evaluate('image => image.decode()')
        assert center.evaluate('image => [image.naturalWidth, image.naturalHeight]') == [500, 700]
        page.evaluate("document.addEventListener('dragstart', () => window.montageNativeDrag = true)")
        image_box = center.bounding_box()
        page.mouse.move(image_box['x'] + 70, image_box['y'] + 70)
        page.mouse.down()
        page.mouse.move(image_box['x'] + 110, image_box['y'] + 110, steps=6)
        page.mouse.up()
        assert not page.evaluate('window.montageNativeDrag')
        expect(page.locator('#montage-count')).to_have_text('20')
        page.locator('#montage-all').check()
        expect(selection).to_have_text('(20)')
        page.locator('#montage-all').uncheck()
        expect(selection).to_have_text('')

        first, third = cards.nth(0).bounding_box(), cards.nth(2).bounding_box()
        x = first['x'] + 66
        page.mouse.move(x, first['y'] + first['height'] / 2)
        page.mouse.down()
        page.mouse.move(x, third['y'] + third['height'] - 4, steps=10)
        expect(page.locator('#montage-list .drop-before')).to_have_count(1)
        page.mouse.up()
        expect(cards.nth(0)).to_contain_text('Foto-02.png')
        expect(cards.nth(2)).to_contain_text('Foto-01.png')
        expect(selection).to_have_text('')
        assert page.evaluate('getSelection().toString()') == ''
        cards.nth(2).press('Alt+ArrowUp')
        expect(cards.nth(1)).to_contain_text('Foto-01.png')
        expect(cards.nth(1)).to_be_focused()
        order = cards.locator('strong').all_text_contents()

        def assign(first, last, size):
            cards.nth(first - 1).click()
            if first != last:
                cards.nth(last - 1).click(modifiers=['Shift'])
            expect(selection).to_have_text(f'({last - first + 1})')
            page.locator(f'#montage-sizes [data-size="{size}"]').click()
            expect(selection).to_have_text('')

        assign(1, 15, '7x10')
        assign(16, 20, '3x4')
        expect(page.locator('#montage-sheet-count')).to_have_text('13')
        expect(page.locator('#montage-photo-size')).to_have_text('3×4')
        page.wait_for_function("document.querySelector('#montage-preview-image').naturalWidth === 354")
        expect(page.locator('#montage-export')).to_be_enabled()
        with page.expect_download(timeout=60000) as download:
            page.locator('#montage-export').click()
        with zipfile.ZipFile(download.value.path()) as archive:
            assert Counter(name.split('/')[0] for name in archive.namelist()) == {'10x15 (7x10)': 8, '10x15 (3x4)': 5}
        expect(page.locator('#montage-export')).to_be_enabled()

        assign(1, 3, '5x7')
        sheets = page.locator('#montage-sheets')
        expect(sheets.get_by_role('button', name='Ampliar folha 6, 10×15 (5×7)', exact=True)).to_be_visible()
        assign(4, 4, '5x7')
        large_sheet = sheets.get_by_role('button', name='Ampliar folha 6, 15×21 (5×7)', exact=True)
        expect(large_sheet).to_be_visible()
        assign(1, 12, '5x7')
        expect(page.locator('#montage-sheet-count')).to_have_text('9')
        first_preview = sheets.locator('.preparation-card img').first
        expect(first_preview).to_be_visible()
        assert first_preview.evaluate('async image => { await image.decode(); return image.naturalWidth; }') == 320
        page.screenshot(path=str(OUT / 'montage-workspace.png'), full_page=True)
        large_sheet.click()
        dialog = page.locator('#montage-sheet-dialog')
        expect(dialog).to_be_visible()
        page.wait_for_function("document.querySelector('#montage-dialog-image').naturalHeight === 1000")
        expect(page.locator('#montage-dialog-image')).to_have_attribute('draggable', 'false')
        page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        with page.expect_download(timeout=60000) as download:
            page.locator('#montage-export').click()
        with zipfile.ZipFile(download.value.path()) as archive:
            assert Counter(name.split('/')[0] for name in archive.namelist()) == {
                '10x15 (3x4)': 5, '15x21 (5x7)': 1, '10x15 (5x7)': 1, '10x15 (7x10)': 2}

        page.locator('#tool-nav [data-tool="medidas"]').click()
        expect(page.locator('#count')).to_have_text('1')
        expect(page.locator('#width-cm')).to_have_value('30')
        page.locator('#tool-nav [data-tool="montagem"]').click()
        expect(page.locator('#montage-count')).to_have_text('20')
        expect(page.locator('#montage-export')).to_be_enabled()
        with page.expect_download() as saved:
            page.locator('#save-project').click()
        project = OUT / 'montagem.medidas'
        saved.value.save_as(project)
        page.once('dialog', lambda dialog: dialog.accept())
        with page.expect_file_chooser() as chooser:
            page.locator('#open-project').click()
        chooser.value.set_files(project)
        expect(page.locator('#montage-export')).to_be_enabled()
        expect(page.locator('#montage-sheet-count')).to_have_text('9')
        expect(cards.locator('strong')).to_have_text(order)
        page.locator('#tool-nav [data-tool="medidas"]').click()
        expect(page.locator('#count')).to_have_text('1')
        expect(page.locator('#width-cm')).to_have_value('30')
        page.locator('#tool-nav [data-tool="montagem"]').click()
        page.reload()
        expect(page.locator('#montage-count')).to_have_text('20')
        expect(page.locator('#montage-sheet-count')).to_have_text('9')
        expect(cards.locator('strong')).to_have_text(order)
        file = photo_file('Importada.png')
        page.locator('.montage-stage').evaluate("""(stage, bytes) => {
            const data = new DataTransfer();
            data.items.add(new File([new Uint8Array(bytes)], 'Importada.png', {type: 'image/png'}));
            for (const type of ['dragenter', 'dragover', 'drop']) {
                stage.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: data}));
            }
        }""", list(file['buffer']))
        expect(page.locator('#montage-count')).to_have_text('21')
        expect(page.locator('#montage-export')).to_be_disabled()
        page.get_by_role('button', name='Remover Importada.png', exact=True).click()
        expect(page.locator('#montage-count')).to_have_text('20')
        expect(page.locator('#montage-export')).to_be_enabled()
        for width in (740, 390, 320):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        grip = cards.first.locator('.montage-grip')
        grip.scroll_into_view_if_needed()
        first, second = grip.bounding_box(), cards.nth(1).bounding_box()
        touch = context.new_cdp_session(page)
        x, y = first['x'] + first['width'] / 2, first['y'] + first['height'] / 2
        touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
        y = second['y'] + second['height'] - 4
        touch.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y}]})
        touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        expect(cards.nth(0)).to_contain_text(order[1])
        expect(selection).to_have_text('')
        page.screenshot(path=str(OUT / 'montage-mobile.png'), full_page=True)
        assert not errors, errors
        print('Montagem · seleção, reordenação, prévias, ZIP e recuperação da sessão OK', flush=True)
        context.close()
        browser.close()


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:18780')

"""Exercise real bulk assignment, automatic layouts and scoped session state."""
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
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
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

        def assign(first, last, size):
            boxes = page.locator('#montage-list input')
            boxes.nth(first - 1).check()
            if first != last:
                boxes.nth(last - 1).click(modifiers=['Shift'])
            expect(page.locator('#montage-selection-count')).to_have_text(f'({last - first + 1})')
            page.locator(f'#montage-sizes [data-size="{size}"]').click()
            expect(page.locator('#montage-selection-count')).to_have_text('')

        assign(1, 15, '7x10')
        assign(16, 20, '3x4')
        expect(page.locator('#montage-sheet-count')).to_have_text('13')
        expect(page.locator('#montage-export')).to_be_enabled()
        with page.expect_download(timeout=60000) as download:
            page.locator('#montage-export').click()
        with zipfile.ZipFile(download.value.path()) as archive:
            assert Counter(name.split('/')[0] for name in archive.namelist()) == {'10x15 (7x10)': 8, '10x15 (3x4)': 5}
        expect(page.locator('#montage-export')).to_be_enabled()

        assign(1, 3, '5x7')
        expect(page.locator('#montage-sheets').get_by_role('button', name='Ver folha 6, 10×15 (5×7)', exact=True)).to_be_visible()
        assign(4, 4, '5x7')
        expect(page.locator('#montage-sheets').get_by_role('button', name='Ver folha 6, 15×21 (5×7)', exact=True)).to_be_visible()
        assign(1, 12, '5x7')
        expect(page.locator('#montage-sheet-count')).to_have_text('9')
        page.locator('#montage-sheets').get_by_role('button', name='Ver folha 6, 15×21 (5×7)', exact=True).click()
        expect(page.locator('#montage-preview-image')).to_be_visible()
        page.wait_for_function("document.querySelector('#montage-preview-image').naturalHeight === 1000")
        page.screenshot(path=str(OUT / 'montage-workspace.png'), full_page=True)
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
        page.locator('#tool-nav [data-tool="medidas"]').click()
        expect(page.locator('#count')).to_have_text('1')
        expect(page.locator('#width-cm')).to_have_value('30')
        page.locator('#tool-nav [data-tool="montagem"]').click()
        page.reload()
        expect(page.locator('#montage-count')).to_have_text('20')
        expect(page.locator('#montage-sheet-count')).to_have_text('9')
        for width in (740, 390, 320):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        page.screenshot(path=str(OUT / 'montage-mobile.png'), full_page=True)
        assert not errors, errors
        print('Montagem · seleção de 15 e 5, quatro pastas, troca de ferramenta e recarga OK', flush=True)
        context.close()
        browser.close()


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:18780')

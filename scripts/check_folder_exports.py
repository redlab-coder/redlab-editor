"""Exercise native-selection integration with real local files and JPEG exports."""
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
from unittest.mock import patch

from PIL import Image
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def service(app):
    class QuietHandler(app.Handler):
        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler) as server:
        server.daemon_threads = True
        server.updater = None
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown()
            worker.join()
            if hasattr(app, 'EXPORTS'):
                app.EXPORTS.close()
            app.CACHE.clear()
            app.IMAGES.clear()


def assert_jpeg(path, size):
    with Image.open(path) as jpeg:
        assert jpeg.format == 'JPEG' and jpeg.size == size, (path, jpeg.size)
        assert jpeg.info.get('dpi') == (300, 300), (path, jpeg.info)


def run(product):
    sys.path.insert(0, str(ROOT / 'apps' / product))
    import app
    import local_files

    with TemporaryDirectory(prefix='RedLab-pastas-') as temporary, sync_playwright() as play, service(app) as url:
        root = Path(temporary)
        source, other, manual = [root / name for name in ('Pedido São João', 'Outro pedido', 'Destino escolhido')]
        for directory in (source, other, manual):
            directory.mkdir()
        paths = []
        for index in range(5):
            path = source / f'Foto {index+1:02d}.png'
            with Image.new('RGB', (600, 840), ('red', 'green', 'blue', 'purple', 'yellow')[index]) as image:
                image.save(path)
            paths.append(path)
        unknown = other / 'Foto sem origem.png'
        unknown.write_bytes(paths[0].read_bytes())
        originals = {path: path.read_bytes() for path in paths}
        browser = play.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        selections = []
        chooser = []

        def choose(*, folder=False):
            if folder:
                chooser.append('folder')
            return selections.pop(0)

        medidas = product == 'medidas-editor'
        with patch.object(local_files, 'choose_paths', side_effect=choose), patch.object(local_files.os, 'startfile') as explorer:
            page.goto(url + ('/montagem' if medidas else ''))
            count = page.locator('#montage-count' if medidas else '#count')
            add = page.locator('#montage-add' if medidas else '#add')
            save = page.locator('#montage-save-folder' if medidas else '#save-folder')
            download = page.locator('#montage-export' if medidas else '#export')
            notice = page.locator('#folder-result')
            dismiss = notice.get_by_role('button', name='Fechar aviso')
            selected = paths if medidas else paths[:1]
            selections.append(selected)
            add.click()
            expect(count).to_have_text(str(len(selected)), timeout=30000)
            if medidas:
                page.locator('#montage-all').check()
                page.locator('#montage-sizes [data-size="5x7"]').click()
                folder, size = '15x21 (5x7)', (1795, 2551)
            elif product == 'bottons-editor':
                folder, size = 'Bottons 10x15', (1795, 1205)
            else:
                folder, size = 'Polaroid', (1500, 1063)

            save.click()
            expect(notice.get_by_role('status')).to_contain_text(f'1 JPEG salvo em {folder}', timeout=30000)
            files = list((source / folder).glob('*.jpg'))
            assert len(files) == 1 and not chooser, (files, chooser)
            first = files[0]
            assert_jpeg(first, size)
            first_bytes = first.read_bytes()
            expect(save).to_be_enabled()
            with page.expect_response(lambda response: '/api/files/open' in response.url):
                notice.get_by_role('button', name='Abrir pasta').click()
            assert Path(explorer.call_args.args[0]) == source / folder
            dismiss.click()
            save.click()
            expect(notice).to_be_visible(timeout=30000)
            assert first.read_bytes() == first_bytes
            assert first.with_stem(first.stem + ' (2)').is_file()
            assert not list(source.rglob('*.zip')) and not list(source.rglob('*.part'))
            dismiss.click()
            expect(download).to_have_attribute('aria-label', 'Baixar JPEG')
            with page.expect_download(timeout=30000) as saved:
                download.click()
            assert_jpeg(saved.value.path(), size)

            if medidas:
                page.locator('#montage-list input').last.check()
                page.locator('#montage-sizes [data-size="3x4"]').click()
                save.click()
                expect(notice.get_by_role('status')).to_contain_text('2 JPEGs salvos', timeout=30000)
                assert len(list((source / '10x15 (3x4)').glob('*.jpg'))) == 1
                assert len(list((source / folder).glob('*.jpg'))) == 3
                assert Path(local_files.RECENT_FOLDERS[next(reversed(local_files.RECENT_FOLDERS))]) == source
                dismiss.click()
                page.locator('#montage-list input').last.check()
                page.locator('#montage-sizes [data-size="5x7"]').click()
            if medidas:
                selections.append([unknown])
                add.click()
            else:
                page.locator('#files').set_input_files(unknown)
            expect(count).to_have_text(str(len(selected)+1), timeout=30000)
            if medidas:
                page.locator('#montage-list input').last.check()
                page.locator('#montage-sizes [data-size="5x7"]').click()
            selections.append([])
            save.click()
            expect(save).to_be_enabled()
            assert chooser == ['folder'] and not list(manual.iterdir())
            selections.append([manual])
            save.click()
            expect(notice).to_be_visible(timeout=30000)
            assert (manual / folder).is_dir() and chooser == ['folder', 'folder']
            assert not list(manual.rglob('*.zip')) and not list(manual.rglob('*.part'))
            dismiss.click()

            if medidas:
                page.locator('#tool-nav [data-tool="medidas"]').click()
                selections.append([paths[0]])
                page.locator('#add').click()
                expect(page.locator('#count')).to_have_text('1')
                page.locator('#width-cm').fill('30')
                page.locator('#height-cm').fill('36')
                page.locator('#apply-size').click()
                page.locator('#fit-mode').select_option('contain')
                page.wait_for_function('current()?.plan && !current().planning')
                page.locator('#save-folder').click()
                expect(notice.get_by_role('status')).to_contain_text('30x40 (30x36)', timeout=30000)
                assert_jpeg(next((source / '30x40 (30x36)').glob('*.jpg')), (3602, 4724))

            assert all(path.read_bytes() == content for path, content in originals.items())
            assert not selections and not errors, (selections, errors)
            for width in (820, 600, 521, 520, 320):
                page.set_viewport_size({'width': width, 'height': 900})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                assert page.evaluate("""() => document.querySelector('#save-folder').getBoundingClientRect().bottom
                    <= document.querySelector('.app-header').getBoundingClientRect().bottom"""), width
            browser.close()
        print(f'{product}: seletor integrado, pasta de origem, duplicatas, destino manual e download OK', flush=True)


if __name__ == '__main__':
    run(sys.argv[1])

'use strict';

const nativeFiles = document.querySelector('meta[name="native-files"]').content === 'true';

function createLocalFiles(api, toast) {
  document.querySelectorAll('[data-save-folder]').forEach(button => { button.hidden = !nativeFiles; });

  const notice = document.getElementById('folder-result');
  const summary = notice.querySelector('[role="status"]');
  const open = notice.querySelector('.folder-open');
  notice.querySelector('.folder-dismiss').onclick = () => { notice.hidden = true; };

  function label(button, count) {
    const text = count > 1 ? 'Baixar ZIP' : 'Baixar JPEG';
    button.lastElementChild.textContent = text;
    button.title = text;
    button.setAttribute('aria-label', text);
  }

  function saved({folder, success, errors = [], error, state}) {
    if (!folder) {
      toast(errors[0] || error || 'Nenhum JPEG foi salvo. Confira a pasta de destino.');
      return;
    }
    const count = success === 1 ? '1 JPEG salvo' : `${success} JPEGs salvos`;
    const issue = state === 'cancelled' ? 'Exportação interrompida.' : errors[0] || error;
    document.getElementById('toast').hidden = true;
    notice.hidden = false;
    summary.textContent = `${count} em ${folder.name}.${issue ? ` ${issue}` : ''}`;
    open.onclick = async () => {
      try { await api('files/open', {token: folder.token}); }
      catch (failure) { toast(failure.message); }
    };
  }

  async function* photos(files, errors, progress, tool) {
    if (files === null) {
      progress('Adicionar fotos…');
      const result = await (await api('files/import', tool ? {tool} : {})).json();
      errors.push(...result.errors);
      files = result.photos;
      for (const [index, photo] of files.entries()) {
        progress(`Importando ${index + 1} de ${files.length}`);
        yield photo;
      }
      return;
    }
    const list = files.filter(file => !['thumbs.db', '.ds_store', 'desktop.ini'].includes(file.name.toLowerCase()));
    for (const [index, file] of list.entries()) {
      progress(`Importando ${index + 1} de ${list.length}`);
      try {
        if (!/\.(jpe?g|png|webp|bmp|tiff?)$/i.test(file.name)) throw new Error('Formato não aceito.');
        if (file.size > 50 * 1024**2) throw new Error('O arquivo excede 50 MB.');
        const path = tool === 'montagem' ? 'montagem/upload' : 'upload';
        yield await (await api(path, file, true, file.name)).json();
      } catch (error) {
        errors.push(`${file.name}: ${error.message}`);
      }
    }
  }

  return {photos, saved, label};
}

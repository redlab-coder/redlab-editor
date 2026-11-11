'use strict';

function createMontage({api, canEdit, active, busy, operation, startJob, save, toast}) {
  const el = id => document.getElementById(`montage-${id}`);
  const sizes = [...el('sizes').querySelectorAll('[data-size]')];
  const textSize = size => size?.replace('x', '×') || 'Sem tamanho';
  let photos = [], checked = new Set(), focused = null, anchor = null;
  let plan = null, sheetIndex = 0, generation = 0, timer, planError = '';
  let previewUrl = null, previewRequest = 0, previewLoading = false, pendingPreview = null;
  const thumbs = new Map();
  const items = () => photos.map(photo => ({
    id: photo.id, name: photo.name, tool: 'montagem', settings: {size: photo.settings.size},
    selected: photo.id === focused, checked: checked.has(photo.id)
  }));

  function targets() {
    return photos.filter(photo => checked.size ? checked.has(photo.id) : photo.id === focused);
  }

  function refresh() {
    const editable = canEdit();
    el('count').textContent = photos.length;
    el('all').checked = !!photos.length && checked.size === photos.length;
    el('all').indeterminate = checked.size > 0 && checked.size < photos.length;
    el('all').disabled = !editable || !photos.length;
    el('range-hint').hidden = photos.length < 2;
    el('selection-count').textContent = checked.size ? `(${checked.size})` : '';
    el('add').disabled = el('empty-add').disabled = !editable;
    el('clear').hidden = !photos.length;
    el('clear').disabled = !editable;
    const selected = targets();
    el('target').textContent = checked.size ? `Aplicar a ${checked.size} ${checked.size === 1 ? 'foto marcada' : 'fotos marcadas'}`
      : selected[0]?.name || 'Selecione uma foto ou marque várias.';
    el('target').title = el('target').textContent;
    for (const button of sizes) {
      button.disabled = !editable || !selected.length;
      button.setAttribute('aria-pressed', String(!!selected.length && selected.every(photo => photo.settings.size === button.dataset.size)));
    }
    for (const row of el('list').children) {
      const id = row.dataset.id;
      row.classList.toggle('active', id === focused);
      row.querySelector('input').checked = checked.has(id);
      row.querySelector('.montage-photo').setAttribute('aria-pressed', String(id === focused));
      for (const control of row.querySelectorAll('button, input')) control.disabled = !editable;
    }
    const count = plan?.sheets.length || 0;
    el('export').disabled = !editable || !count || !!plan?.pending;
    if (!busy()) el('export-label').textContent = count > 1 ? 'Exportar ZIP' : 'Exportar JPEG';
  }

  function renderRows() {
    const list = el('list');
    const scroll = list.scrollTop;
    const previous = document.activeElement;
    const previousId = previous?.closest('.montage-row')?.dataset.id;
    const previousClass = previous?.className;
    list.replaceChildren();
    for (const photo of photos) {
      const row = document.createElement('div');
      row.className = 'montage-row';
      row.dataset.id = photo.id;
      const check = document.createElement('input');
      check.type = 'checkbox';
      check.setAttribute('aria-label', `Marcar ${photo.name}`);
      check.onclick = event => {
        const start = photos.findIndex(item => item.id === anchor);
        const end = photos.indexOf(photo);
        const range = event.shiftKey && start >= 0 ? photos.slice(Math.min(start, end), Math.max(start, end) + 1) : [photo];
        for (const item of range) check.checked ? checked.add(item.id) : checked.delete(item.id);
        anchor = photo.id;
        refresh();
        save();
      };
      const button = document.createElement('button');
      button.className = 'montage-photo';
      button.type = 'button';
      button.title = [photo.name, ...(photo.metadata?.warnings || [])].join('\n');
      button.onclick = () => {
        focused = photo.id;
        refresh();
        save();
      };
      const detail = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = photo.name;
      const size = document.createElement('small');
      size.textContent = textSize(photo.settings.size);
      detail.append(title, size);
      if (thumbs.has(photo.id)) {
        const thumb = document.createElement('img');
        thumb.src = thumbs.get(photo.id);
        thumb.alt = '';
        button.append(thumb);
      }
      button.append(detail);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'icon-button montage-remove';
      remove.setAttribute('aria-label', `Remover ${photo.name}`);
      remove.innerHTML = MedidasEditorIcons.svg('remove');
      remove.onclick = () => operation(async () => {
        await api('delete', {id: photo.id, tool: 'montagem'});
        const index = photos.indexOf(photo);
        photos.splice(index, 1);
        checked.delete(photo.id);
        if (thumbs.has(photo.id)) URL.revokeObjectURL(thumbs.get(photo.id));
        thumbs.delete(photo.id);
        if (focused === photo.id) focused = photos[Math.min(index, photos.length - 1)]?.id || null;
        renderRows();
        planChanged();
      });
      row.append(check, button, remove);
      list.append(row);
      if (photo.id === previousId) [...row.children].find(child => child.className === previousClass)?.focus({preventScroll: true});
    }
    list.scrollTop = scroll;
    refresh();
  }

  function clearPreview() {
    previewRequest++;
    pendingPreview = null;
    el('preview-image').removeAttribute('src');
    el('preview-image').hidden = true;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    el('empty').hidden = false;
  }

  async function loadPreview() {
    if (previewLoading) return;
    previewLoading = true;
    try {
      while (pendingPreview) {
        const request = pendingPreview;
        pendingPreview = null;
        try {
          const blob = await (await api('montagem/preview', {items: request.items, index: request.index})).blob();
          if (request.id !== previewRequest) continue;
          previewUrl = URL.createObjectURL(blob);
          el('preview-image').src = previewUrl;
          el('preview-image').hidden = false;
          el('empty').hidden = true;
        } catch (error) {
          if (request.id === previewRequest) el('stage-message').textContent = error.message;
        }
      }
    } finally {
      previewLoading = false;
    }
  }

  function renderSheets() {
    clearPreview();
    const scroll = el('sheets').scrollLeft;
    const sheets = plan?.sheets || [];
    const sheet = sheets[sheetIndex];
    el('sheet-count').textContent = sheets.length;
    el('empty-add').hidden = !!photos.length;
    el('sheet-details').hidden = !sheet;
    el('sheets').replaceChildren();
    const pending = photos.filter(photo => !photo.settings.size).length;
    el('pending').hidden = !pending || !sheets.length;
    el('pending').textContent = pending === 1 ? '1 foto ainda precisa de tamanho.' : `${pending} fotos ainda precisam de tamanho.`;
    el('stage-message').textContent = planError || (sheet ? 'Carregando prévia…' : !photos.length ? 'Adicione ou arraste as fotos.'
      : pending === photos.length ? 'Escolha o tamanho das fotos para montar as folhas.' : 'Organizando as folhas…');
    if (sheet) {
      const model = sheet.model.replaceAll('x', '×');
      el('sheet-title').textContent = `Folha ${sheetIndex + 1} · ${model}`;
      const format = values => values.map(value => value.replace('.', ',')).join(' × ');
      el('sheet-spec').textContent = `${format(sheet.paper_cm)} cm · ${sheet.print_count} ${sheet.print_count === 1 ? 'foto' : 'fotos'} · 300 dpi`;
      el('preview-image').alt = `Prévia da folha ${sheetIndex + 1}, ${model}`;
      sheets.forEach((entry, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'secondary';
        button.textContent = `${index + 1} · ${entry.model.replaceAll('x', '×')}`;
        button.setAttribute('aria-label', `Ver folha ${index + 1}, ${entry.model.replaceAll('x', '×')}`);
        button.setAttribute('aria-pressed', String(index === sheetIndex));
        button.onclick = () => {
          sheetIndex = index;
          renderSheets();
          el('sheets').children[index]?.focus({preventScroll: true});
          save();
        };
        el('sheets').append(button);
      });
      pendingPreview = {id: previewRequest, index: sheetIndex, items: items()};
      if (active()) loadPreview();
    }
    el('sheets').scrollLeft = scroll;
    refresh();
  }

  function planChanged() {
    const request = ++generation;
    clearTimeout(timer);
    plan = null;
    planError = '';
    renderSheets();
    if (!photos.length) return;
    const snapshot = items();
    timer = setTimeout(async () => {
      try {
        const next = await (await api('montagem/plan', {items: snapshot})).json();
        if (request !== generation) return;
        plan = next;
        sheetIndex = Math.min(sheetIndex, Math.max(0, plan.sheets.length - 1));
      } catch (error) {
        if (request !== generation) return;
        planError = error.message;
      }
      renderSheets();
    }, 75);
  }

  async function addPhoto(data) {
    photos.push({...data, settings: {size: data.settings?.size || null}});
    try {
      const image = await (await api('thumbnail', {id: data.id})).blob();
      thumbs.set(data.id, URL.createObjectURL(image));
    } catch {
      // A missing thumbnail is independent from the original upload.
    }
  }

  function importFiles(files) {
    if (!active() || document.querySelector('dialog[open]') || !files.length) return;
    operation(async () => {
      const errors = [];
      let first = null;
      for (const [index, file] of files.entries()) {
        el('activity').textContent = `Importando ${index + 1} de ${files.length}`;
        try {
          if (!/\.(jpe?g|png|webp|bmp|tiff?)$/i.test(file.name)) throw new Error('Formato não aceito.');
          const data = await (await api('montagem/upload', file, true, file.name)).json();
          await addPhoto(data);
          first ??= data.id;
        } catch (error) {
          errors.push(`${file.name}: ${error.message}`);
        }
      }
      el('activity').textContent = '';
      el('files').value = '';
      if (first) focused = first;
      renderRows();
      planChanged();
      if (errors.length) toast(`${errors.length} arquivo(s) não importados. ${errors.slice(0, 2).join(' ')}`);
    });
  }

  function release() {
    generation++;
    clearTimeout(timer);
    clearPreview();
    for (const url of thumbs.values()) URL.revokeObjectURL(url);
    thumbs.clear();
  }

  async function restore(entries, previousSheet = 0) {
    release();
    photos = [];
    checked.clear();
    anchor = null;
    for (const photo of entries) {
      await addPhoto(photo);
      if (photo.checked) checked.add(photo.id);
    }
    focused = entries.find(photo => photo.selected)?.id || photos[0]?.id || null;
    sheetIndex = previousSheet;
    renderRows();
    planChanged();
  }

  el('all').onchange = () => {
    checked = el('all').checked ? new Set(photos.map(photo => photo.id)) : new Set();
    anchor = null;
    refresh();
    save();
  };
  for (const button of sizes) button.onclick = () => {
    if (!canEdit()) return;
    const selected = targets();
    for (const photo of selected) photo.settings.size = button.dataset.size;
    checked.clear();
    anchor = null;
    renderRows();
    planChanged();
    save();
    if (selected.length > 1) toast(`${textSize(button.dataset.size)} aplicado a ${selected.length} fotos.`);
  };
  el('clear').onclick = () => { if (canEdit()) el('clear-dialog').showModal(); };
  el('clear-confirm').onclick = () => operation(async () => {
      await api('clear', {tool: 'montagem', ids: photos.map(photo => photo.id)});
      await restore([]);
      el('clear-dialog').close();
  });
  el('add').onclick = el('empty-add').onclick = () => el('files').click();
  el('files').onchange = () => importFiles([...el('files').files]);
  el('export').onclick = () => {
    if (!plan?.sheets.length || plan.pending || !canEdit()) return;
    startJob('montagem/export', items(), {label: el('export-label'), activity: el('activity'), cancel: el('cancel')});
  };

  const drop = el('drop');
  let depth = 0;
  function endDrop() {
    depth = 0;
    drop.classList.remove('file-drop-active');
  }
  const isFile = event => Array.from(event.dataTransfer?.types || []).includes('Files');
  drop.ondragenter = event => {
    if (!isFile(event)) return;
    event.preventDefault();
    depth++;
    if (canEdit()) drop.classList.add('file-drop-active');
  };
  drop.ondragover = event => {
    if (!isFile(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = canEdit() ? 'copy' : 'none';
  };
  drop.ondragleave = event => { if (isFile(event) && --depth <= 0) endDrop(); };
  drop.ondrop = event => {
    if (!isFile(event)) return;
    event.preventDefault();
    event.stopPropagation();
    endDrop();
    importFiles([...event.dataTransfer.files]);
  };
  window.addEventListener('blur', endDrop);

  return {
    items, restore, refresh, release,
    show() { refresh(); if (active()) loadPreview(); else endDrop(); },
    count: () => photos.length,
    session: () => ({sheet: sheetIndex, photos: items().map((item, index) => ({...photos[index], ...item}))})
  };
}

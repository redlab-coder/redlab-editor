'use strict';

function createMontage({api, canEdit, active, busy, operation, startJob, save, toast}) {
  const el = id => document.getElementById(`montage-${id}`);
  const sizes = [...el('sizes').querySelectorAll('[data-size]')];
  const textSize = size => size?.replace('x', '×') || 'Sem tamanho';
  let photos = [], checked = new Set(), focused = null, anchor = null;
  let plan = null, generation = 0, timer;
  let photoKey = null, photoUrl = null, photoLoading = false, pendingPhoto = null;
  let galleryItems = [], galleryLoading = false, dialogUrl = null, dialogRequest = 0;
  const cards = new Map(), galleryUrls = new Map(), galleryQueue = new Set();
  const thumbs = new Map();
  const list = el('list');
  const dialog = el('sheet-dialog');
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
      : selected.length ? 'Tamanho da foto' : 'Selecione uma foto.';
    el('target').title = el('target').textContent;
    for (const button of sizes) {
      button.disabled = !editable || !selected.length;
      button.setAttribute('aria-pressed', String(!!selected.length && selected.every(photo => photo.settings.size === button.dataset.size)));
    }
    for (const row of list.children) {
      const id = row.dataset.id;
      row.classList.toggle('active', id === focused);
      row.classList.toggle('marked', checked.has(id));
      row.querySelector('.montage-photo').setAttribute('aria-pressed', String(checked.has(id)));
      for (const control of row.querySelectorAll('button')) control.disabled = !editable;
    }
    const count = plan?.sheets.length || 0;
    el('export').disabled = !editable || !count || !!plan?.pending;
    if (!busy()) el('export-label').textContent = count > 1 ? 'Exportar ZIP' : 'Exportar JPEG';
  }

  function renderRows() {
    const scroll = list.scrollTop;
    const previous = document.activeElement;
    const previousId = previous?.closest('.montage-row')?.dataset.id;
    const previousClass = previous?.className;
    cancelReorder();
    list.replaceChildren();
    for (const photo of photos) {
      const row = document.createElement('div');
      row.className = 'montage-row';
      row.dataset.id = photo.id;
      const button = document.createElement('button');
      button.className = 'montage-photo';
      button.type = 'button';
      button.setAttribute('aria-label', `Selecionar ${photo.name}`);
      button.setAttribute('aria-keyshortcuts', 'Alt+ArrowUp Alt+ArrowDown');
      button.title = [photo.name, ...(photo.metadata?.warnings || [])].join('\n');
      button.onclick = event => {
        if (!canEdit()) return;
        const start = photos.findIndex(item => item.id === anchor);
        const end = photos.indexOf(photo);
        if (event.shiftKey && start >= 0) {
          for (const item of photos.slice(Math.min(start, end), Math.max(start, end) + 1)) checked.add(item.id);
        } else {
          if (checked.has(photo.id)) checked.delete(photo.id);
          else checked.add(photo.id);
          anchor = photo.id;
        }
        focused = photo.id;
        refresh();
        showPhoto();
        save();
      };
      const grip = document.createElement('span');
      grip.className = 'montage-grip';
      grip.setAttribute('aria-hidden', 'true');
      button.append(grip);
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
        thumb.draggable = false;
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
      row.append(button, remove);
      list.append(row);
      if (photo.id === previousId) [...row.children].find(child => child.className === previousClass)?.focus({preventScroll: true});
    }
    list.scrollTop = scroll;
    refresh();
  }

  function clearPhoto() {
    photoKey = null;
    pendingPhoto = null;
    el('preview-image').removeAttribute('src');
    el('preview-image').hidden = true;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    photoUrl = null;
    el('empty').hidden = false;
  }

  async function loadPhoto() {
    if (photoLoading) return;
    photoLoading = true;
    try {
      while (pendingPhoto) {
        const {key, id, size} = pendingPhoto;
        pendingPhoto = null;
        try {
          const blob = await (await api(size ? 'montagem/photo-preview' : 'source', {id, size})).blob();
          if (key !== photoKey || photoUrl) continue;
          photoUrl = URL.createObjectURL(blob);
          el('preview-image').src = photoUrl;
          el('preview-image').hidden = false;
          el('empty').hidden = true;
        } catch (error) {
          if (key === photoKey) {
            photoKey = null;
            el('stage-message').textContent = error.message;
          }
        }
      }
    } finally {
      photoLoading = false;
    }
  }

  function showPhoto() {
    if (!active()) return;
    const photo = photos.find(item => item.id === focused);
    el('photo-title').textContent = photo?.name || 'Prévia da foto';
    el('photo-title').title = photo?.name || '';
    el('photo-size').textContent = photo ? textSize(photo.settings.size) : '';
    el('empty-add').hidden = !!photos.length;
    if (!photo) {
      clearPhoto();
      el('stage-message').textContent = photos.length ? 'Selecione uma foto.' : 'Adicione ou arraste as fotos.';
      return;
    }
    const size = photo.settings.size;
    const key = `${photo.id}:${size || ''}`;
    if (key === photoKey) return;
    clearPhoto();
    photoKey = key;
    el('preview-image').alt = photo.name;
    el('stage-message').textContent = 'Carregando foto…';
    pendingPhoto = {key, id: photo.id, size};
    loadPhoto();
  }

  function paintCard(card, url) {
    card.image.src = url;
    card.image.hidden = false;
    card.placeholder.hidden = true;
  }

  async function loadGallery() {
    if (galleryLoading || !active()) return;
    galleryLoading = true;
    try {
      while (galleryQueue.size && active()) {
        const [key] = galleryQueue;
        galleryQueue.delete(key);
        const card = cards.get(key);
        if (!card || galleryUrls.has(key)) continue;
        try {
          const blob = await (await api('montagem/preview', {items: galleryItems, index: card.index, maximum: 320})).blob();
          if (!cards.has(key)) continue;
          const url = URL.createObjectURL(blob);
          galleryUrls.set(key, url);
          paintCard(cards.get(key), url);
        } catch {
          if (cards.get(key) === card) card.placeholder.textContent = 'Clique para abrir a prévia';
        }
      }
    } finally {
      galleryLoading = false;
    }
  }

  const galleryObserver = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) galleryQueue.add(entry.target.dataset.key);
    loadGallery();
  }, {root: el('sheets'), rootMargin: '0px 100px'});

  async function openSheet(title, index) {
    clearDialog();
    const request = ++dialogRequest;
    el('dialog-title').textContent = title;
    el('dialog-status').textContent = 'Carregando prévia…';
    el('dialog-status').hidden = false;
    el('dialog-image').hidden = true;
    dialog.showModal();
    try {
      const blob = await (await api('montagem/preview', {items: galleryItems, index})).blob();
      if (!dialog.open || request !== dialogRequest) return;
      dialogUrl = URL.createObjectURL(blob);
      el('dialog-image').src = dialogUrl;
      el('dialog-image').alt = title;
      el('dialog-image').hidden = false;
      el('dialog-status').hidden = true;
    } catch (error) {
      if (request === dialogRequest) el('dialog-status').textContent = error.message;
    }
  }

  function clearDialog() {
    dialogRequest++;
    el('dialog-image').removeAttribute('src');
    if (dialogUrl) URL.revokeObjectURL(dialogUrl);
    dialogUrl = null;
  }
  dialog.addEventListener('close', () => { if (!dialog.open) clearDialog(); });

  function renderGallery(message = '') {
    galleryObserver.disconnect();
    galleryQueue.clear();
    cards.clear();
    const gallery = el('sheets');
    const scroll = gallery.scrollLeft;
    gallery.replaceChildren();
    const sheets = plan?.sheets || [];
    el('sheet-count').textContent = sheets.length || '';
    const pending = plan?.pending || 0;
    el('pending').hidden = !pending || !sheets.length;
    el('pending').textContent = pending === 1 ? '1 foto ainda precisa de tamanho.' : `${pending} fotos ainda precisam de tamanho.`;
    if (!sheets.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-sheet';
      empty.textContent = message || 'As folhas aparecem aqui depois de definir o tamanho das fotos.';
      gallery.append(empty);
    }
    for (const [index, sheet] of sheets.entries()) {
      const model = sheet.model.replaceAll('x', '×');
      const title = `Folha ${index + 1} · ${model}`;
      const key = JSON.stringify([sheet.model, ...sheet.indices.map(i => galleryItems[i].id)]);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'preparation-card';
      button.dataset.key = key;
      button.setAttribute('aria-label', `Ampliar folha ${index + 1}, ${model}`);
      button.onclick = () => openSheet(title, index);
      const preview = document.createElement('span');
      preview.className = 'card-preview';
      const image = document.createElement('img');
      image.alt = '';
      image.draggable = false;
      image.hidden = true;
      const placeholder = document.createElement('span');
      placeholder.className = 'card-placeholder';
      placeholder.textContent = 'Carregando prévia…';
      preview.append(image, placeholder);
      const label = document.createElement('strong');
      label.textContent = title;
      const measure = document.createElement('span');
      measure.className = 'card-measure';
      measure.textContent = `${sheet.paper_cm.join(' × ').replaceAll('.', ',')} cm · ${sheet.print_count} ${sheet.print_count === 1 ? 'foto' : 'fotos'}`;
      button.append(preview, label, measure);
      const card = {index, image, placeholder};
      cards.set(key, card);
      gallery.append(button);
      if (galleryUrls.has(key)) paintCard(card, galleryUrls.get(key));
      else galleryObserver.observe(button);
    }
    if (plan || !photos.length) {
      for (const [key, url] of galleryUrls) if (!cards.has(key)) {
        URL.revokeObjectURL(url);
        galleryUrls.delete(key);
      }
    }
    gallery.scrollLeft = scroll;
    refresh();
  }

  function planChanged() {
    const request = ++generation;
    clearTimeout(timer);
    plan = null;
    const hasSizes = photos.some(photo => photo.settings.size);
    renderGallery(hasSizes ? 'Organizando as folhas…' : '');
    showPhoto();
    if (!photos.length) return;
    const snapshot = items();
    timer = setTimeout(async () => {
      try {
        const next = await (await api('montagem/plan', {items: snapshot})).json();
        if (request !== generation) return;
        galleryItems = snapshot;
        plan = next;
      } catch (error) {
        if (request !== generation) return;
        renderGallery(error.message);
        return;
      }
      renderGallery();
    }, 75);
  }

  let reorder = null, reorderFrame = 0, suppressClick = false;

  function movePhoto(id, to) {
    const from = photos.findIndex(photo => photo.id === id);
    if (from < 0 || to === from || to < 0 || to >= photos.length) return;
    const [photo] = photos.splice(from, 1);
    photos.splice(to, 0, photo);
    renderRows();
    planChanged();
    save();
    el('order-status').textContent = `${photo.name} movida para a posição ${to + 1}.`;
  }

  function clearDropIndicator(gesture) {
    gesture.indicator?.classList.remove('drop-before', 'drop-after');
    gesture.indicator = null;
  }

  function updateDropTarget(gesture) {
    clearDropIndicator(gesture);
    const rect = list.getBoundingClientRect();
    const {x, y, id} = gesture;
    gesture.valid = x >= rect.left && x <= rect.right && y >= rect.top - 24 && y <= rect.bottom + 24;
    if (!gesture.valid) return;
    const rows = [...list.children].filter(row => row.dataset.id !== id);
    const before = rows.find(row => {
      const box = row.getBoundingClientRect();
      return y < box.top + box.height / 2;
    });
    gesture.before = before?.dataset.id || null;
    gesture.indicator = before || rows.at(-1);
    gesture.indicator?.classList.add(before ? 'drop-before' : 'drop-after');
  }

  function autoScroll() {
    if (!reorder?.moving) return;
    const {x, y} = reorder;
    const rect = list.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top - 24 && y <= rect.bottom + 24) {
      const delta = y < rect.top + 28 ? -9 : y > rect.bottom - 28 ? 9 : 0;
      if (delta) {
        const previous = list.scrollTop;
        list.scrollTop += delta;
        if (list.scrollTop !== previous) updateDropTarget(reorder);
      }
    }
    reorderFrame = requestAnimationFrame(autoScroll);
  }

  function cancelReorder() {
    if (!reorder) return;
    const gesture = reorder;
    reorder = null;
    cancelAnimationFrame(reorderFrame);
    clearDropIndicator(gesture);
    gesture.row.classList.remove('reordering');
    if (gesture.moving) suppressClick = true;
    if (list.hasPointerCapture(gesture.pointer)) list.releasePointerCapture(gesture.pointer);
  }

  list.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.button !== 0) return;
    suppressClick = false;
    const row = event.target.closest('.montage-photo')?.closest('.montage-row');
    if (!row || !canEdit() || photos.length < 2) return;
    if (event.pointerType === 'touch' && !event.target.closest('.montage-grip')) return;
    reorder = {id: row.dataset.id, row, pointer: event.pointerId, startY: event.clientY, moving: false};
  });
  window.addEventListener('pointermove', event => {
    if (reorder?.pointer !== event.pointerId) return;
    if (!active() || !canEdit()) { cancelReorder(); return; }
    reorder.x = event.clientX;
    reorder.y = event.clientY;
    if (!reorder.moving) {
      if (Math.abs(reorder.y - reorder.startY) < 7) return;
      reorder.moving = true;
      reorder.row.classList.add('reordering');
      list.setPointerCapture(event.pointerId);
      reorderFrame = requestAnimationFrame(autoScroll);
    }
    updateDropTarget(reorder);
  });
  window.addEventListener('pointerup', event => {
    if (reorder?.pointer !== event.pointerId) return;
    const gesture = reorder;
    if (gesture.moving) {
      gesture.x = event.clientX;
      gesture.y = event.clientY;
      updateDropTarget(gesture);
    }
    cancelReorder();
    if (!gesture.moving || !gesture.valid || !active() || !canEdit()) return;
    const remaining = photos.filter(photo => photo.id !== gesture.id);
    const to = gesture.before ? remaining.findIndex(photo => photo.id === gesture.before) : remaining.length;
    movePhoto(gesture.id, to);
  });
  window.addEventListener('pointercancel', event => { if (reorder?.pointer === event.pointerId) cancelReorder(); });
  list.addEventListener('lostpointercapture', event => { if (event.target === list) cancelReorder(); });
  list.addEventListener('click', event => {
    if (!suppressClick || !event.detail) return;
    suppressClick = false;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
  list.addEventListener('keydown', event => {
    const id = event.target.closest('.montage-photo')?.closest('.montage-row')?.dataset.id;
    if (!id || !event.altKey || !canEdit() || !['ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    movePhoto(id, photos.findIndex(photo => photo.id === id) + (event.key === 'ArrowUp' ? -1 : 1));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && reorder) { event.preventDefault(); cancelReorder(); }
  });

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
    cancelReorder();
    clearPhoto();
    galleryObserver.disconnect();
    galleryQueue.clear();
    cards.clear();
    for (const url of galleryUrls.values()) URL.revokeObjectURL(url);
    galleryUrls.clear();
    if (dialog.open) dialog.close();
    clearDialog();
    for (const url of thumbs.values()) URL.revokeObjectURL(url);
    thumbs.clear();
  }

  async function restore(entries) {
    release();
    photos = [];
    checked.clear();
    anchor = null;
    for (const photo of entries) {
      await addPhoto(photo);
      if (photo.checked) checked.add(photo.id);
    }
    focused = entries.find(photo => photo.selected)?.id || photos[0]?.id || null;
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
  window.addEventListener('blur', () => { endDrop(); cancelReorder(); });
  for (const area of [el('tool'), dialog]) area.addEventListener('dragstart', event => event.preventDefault());
  renderGallery();

  return {
    items, restore, refresh, release,
    show() {
      refresh();
      if (active()) { showPhoto(); loadGallery(); }
      else { endDrop(); cancelReorder(); }
    },
    count: () => photos.length,
    session: () => ({photos: items().map((item, index) => ({...photos[index], ...item}))})
  };
}

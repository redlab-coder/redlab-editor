'use strict';
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name="medidas-editor-token"]').content;
const formats=JSON.parse($('formats-data').textContent);
const defaults=()=>({width_cm:null,height_cm:null,mode:'cover',cx:.5,cy:.5,zoom:1,rotation:0,sheet:'auto',position:'top_left'});
const cm=n=>Number(n).toLocaleString('pt-BR',{maximumFractionDigits:6});
const dimensions=(w,h)=>`${cm(w)} × ${cm(h)} cm`;
const sessionKey='medidas-editor-session';
const positionNames={top_left:'Canto superior esquerdo',top_right:'Canto superior direito',bottom_left:'Canto inferior esquerdo',bottom_right:'Canto inferior direito',center:'Centro'};
let photos=[],selected=null,checked=new Set(),filterReview=false,importing=false,exporting=false,restoring=false,clearing=false,closed=false;
let editingAllowed=false,acquiring=false,releaseOwnership=null,passiveAfterYield=false,sessionRevision=0,pendingRestore=null;
let revision=0,drag=null,frame=null,planTimer=null,toastTimer=null,draftDirty=false,lastJob=null,pendingExport=[];
let oriented=null,restoreTask=null;
const sources=new Map(),urls=new Map();
const canEdit=()=>editingAllowed&&!closed&&!importing&&!exporting&&!restoring&&!clearing;
const current=()=>photos.find(photo=>photo.id===selected);
const item=photo=>({id:photo.id,name:photo.name,settings:{...photo.settings},reviewed:photo.reviewed});
const pending=photo=>!!photo.planning||!photo.plan||!!photo.error||((photo.plan.needs_review||photo.metadata.warnings.length)&&!photo.reviewed);
const visible=()=>filterReview?photos.filter(pending):photos;
const channel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel('medidas-editor:'+token):null;
const tabId=crypto.randomUUID();

async function api(path,data={},raw=false,name=''){
  const response=await fetch('/api/'+path,{method:'POST',headers:{'X-MedidasEditor-Token':token,'Content-Type':raw?'application/octet-stream':'application/json',...(name?{'X-Filename':encodeURIComponent(name)}:{})},body:raw?data:JSON.stringify(data)});
  if(!response.ok){const body=await response.json();throw new Error(body.error||'Não foi possível concluir.');}return response;
}
function toast(message){if(closed)return;clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,6500);}
function replaceUrl(key,blob){if(urls.has(key))URL.revokeObjectURL(urls.get(key));const url=URL.createObjectURL(blob);urls.set(key,url);return url;}
function releaseImages(){revision++;cancelAnimationFrame(frame);frame=null;clearTimeout(planTimer);drag=null;oriented=null;for(const promise of sources.values())promise.then(bitmap=>bitmap.close()).catch(()=>{});sources.clear();for(const url of urls.values())URL.revokeObjectURL(url);urls.clear();}
function saveSession(){if(!canEdit())return;try{const old=readSession();if(old?.token===token&&(old.sessionRevision||0)>sessionRevision){pendingRestore=old;flushRestore();return;}localStorage.setItem(sessionKey,JSON.stringify({token,sessionRevision:++sessionRevision,selected,filterReview,photos:photos.map(photo=>({...item(photo),width:photo.width,height:photo.height,metadata:photo.metadata}))}));}catch(error){toast('Não foi possível guardar os ajustes nesta aba. Salve o lote antes de fechar.');}}
function readSession(){try{return JSON.parse(localStorage.getItem(sessionKey));}catch{return null;}}

function statusText(photo){if(photo.error)return photo.error;if(!photo.plan)return 'Defina as medidas';if(pending(photo))return 'Recorte a conferir';return photo.plan.effective_ppi<299.9?'Pronta · resolução baixa':'Pronta para exportar';}
function renderLibrary(){
  $('count').textContent=photos.length;$('photo-list').replaceChildren();
  for(const photo of visible()){
    const row=document.createElement('div');row.className='photo-row'+(photo.id===selected?' active':'');row.dataset.id=photo.id;
    const check=document.createElement('input');check.type='checkbox';check.checked=checked.has(photo.id);check.disabled=!canEdit();check.setAttribute('aria-label','Selecionar '+photo.name);check.onchange=()=>{check.checked?checked.add(photo.id):checked.delete(photo.id);refreshSelection();};
    const button=document.createElement('button');button.type='button';button.className='photo-select';button.setAttribute('aria-label','Editar '+photo.name);button.disabled=!canEdit();button.onclick=()=>select(photo.id);
    const thumb=document.createElement('img');thumb.alt='';if(photo.thumb)thumb.src=photo.thumb;else thumb.hidden=true;
    const detail=document.createElement('span');detail.className='photo-detail';const name=document.createElement('strong');name.textContent=photo.name;const info=document.createElement('small');info.textContent=photo.plan?`${cm(photo.settings.width_cm)} × ${cm(photo.settings.height_cm)} → ${photo.plan.sheet.name}`:'Medidas pendentes';const state=document.createElement('small');state.className=pending(photo)?'pending-state':'ready-state';state.textContent=photo.error?'Confira o aviso':pending(photo)?'A conferir':'Pronta';detail.append(name,info,state);button.append(thumb,detail);
    const remove=document.createElement('button');remove.className='remove-photo icon-button';remove.title='Remover esta foto';remove.setAttribute('aria-label','Remover '+photo.name);remove.disabled=!canEdit();remove.innerHTML=MedidasEditorIcons.svg('remove');remove.onclick=()=>removePhoto(photo);
    row.append(check,button,remove);$('photo-list').append(row);
  }
  if(photos.length&&!visible().length){const p=document.createElement('p');p.className='review-empty';p.textContent='Nenhuma foto pendente.';$('photo-list').append(p);}
  refreshSelection();refreshControls();
}
function refreshSelection(){
  const count=photos.filter(p=>checked.has(p.id)).length;$('selection-count').textContent=count?`(${count})`:'';
  $('select-all').checked=!!photos.length&&count===photos.length;$('select-all').indeterminate=count>0&&count<photos.length;$('select-all').disabled=!photos.length||!canEdit();
  $('apply-selection').textContent=count?`Aplicar às selecionadas (${count})`:'Aplicar às selecionadas';$('apply-selection').disabled=!count||!canEdit();
}
function refreshControls(){
  const photo=current(),active=!!photo&&canEdit();
  for(const id of ['width-cm','height-cm','apply-size','fit-mode','sheet','position','reset','rotate'])$(id).disabled=!active;
  $('center').disabled=!active||!photo?.plan||photo.settings.mode==='contain';
  for(const id of ['zoom','zoom-number'])$(id).disabled=!active||!photo?.plan||photo.settings.mode==='contain';
  for(const id of ['add','drop','empty-add','open-project'])$(id).disabled=!canEdit();
  $('save-project').disabled=!photos.length||!canEdit();$('clear-all').hidden=!photos.length;$('clear-all').disabled=!photos.length||!canEdit();
  $('export').disabled=!photos.length||!canEdit();$('export-photo').disabled=!photo?.plan||!canEdit();
  $('review-photo').disabled=!photo?.plan||!!photo?.planning||!!photo?.error||!canEdit()||draftDirty||!oriented||oriented.id!==photo.id;
  $('review-photo').setAttribute('aria-pressed',String(!!photo?.reviewed));$('review-photo').lastElementChild.textContent=photo?.reviewed?'Conferida':'Conferir recorte';
  $('use-metadata').disabled=!active||!photo?.metadata.size_cm;
  $('filter-review').setAttribute('aria-pressed',String(filterReview));$('filter-review').textContent=filterReview?'Mostrando a conferir':'Todas as fotos';
  $('session-banner').hidden=editingAllowed;$('selected-name').textContent=photo?.name||'Escolha uma foto';
  $('export-label').textContent=photos.length>1?'Exportar lote':'Exportar JPEG';
}
function renderSettings(){
  const photo=current(),settings=photo?.settings||defaults();draftDirty=false;
  $('width-cm').value=settings.width_cm?cm(settings.width_cm):'';$('height-cm').value=settings.height_cm?cm(settings.height_cm):'';
  $('dimension-hint').textContent='Deixe uma medida vazia para calcular pela proporção original.';
  $('fit-mode').value=settings.mode;$('position').value=settings.position;$('zoom').value=settings.zoom;$('zoom-number').value=settings.zoom.toFixed(2);$('zoom-value').textContent=settings.zoom.toFixed(2).replace('.',',')+'×';
  $('sheet').replaceChildren(new Option('Automática — menor compatível','auto'));
  const options=photo?.plan?.options||formats;
  for(const spec of options)$('sheet').add(new Option(`${spec.name} — ${dimensions(spec.width_cm,spec.height_cm)}`,spec.id));
  $('sheet').value=settings.sheet;
  $('fit-hint').textContent=settings.mode==='contain'?'Preserva todo o conteúdo. Pode haver branco dentro da área solicitada.':'Preenche a área solicitada sem deformar. Arraste para ajustar.';
  $('metadata-text').textContent=photo?`${photo.width} × ${photo.height} px · ${photo.metadata.profile}. ${photo.metadata.size_cm?'Referência do arquivo: '+dimensions(...photo.metadata.size_cm)+'.':'O arquivo não tem resolução física válida registrada.'}`:'Escolha uma foto.';
  renderSummary();refreshControls();
}
function renderSummary(){
  const photo=current();$('output-summary').replaceChildren();$('resolution').hidden=true;$('photo-error').hidden=!photo?.error;
  if(photo?.error)$('photo-error').textContent=photo.error;
  if(!photo?.plan){$('output-summary').textContent='Defina a medida da foto para sugerir a folha.';return;}
  const plan=photo.plan,s=photo.settings,sheet=plan.sheet;
  for(const text of [`Foto: ${dimensions(s.width_cm,s.height_cm)}`,`Folha: ${sheet.name} — arquivo de ${dimensions(sheet.width_cm,sheet.height_cm)}`,`Posição: ${positionNames[s.position]}`,sheet.rotation?'Foto girada 90° para acomodar na folha.':'Foto acomodada sem giro adicional.',`Saída: JPEG · 300 dpi · ${sheet.size_px[0]} × ${sheet.size_px[1]} px`]){const p=document.createElement('p');p.textContent=text;$('output-summary').append(p);}
  const warnings=[...photo.metadata.warnings,...plan.warnings];
  $('resolution').hidden=!warnings.length;$('resolution').textContent=warnings.join(' ');
}
function renderCards(){
  $('sheet-summary').textContent=photos.length?`${photos.length} fotos · ${photos.filter(p=>!pending(p)).length} prontas`:'';$('sheets').replaceChildren();
  if(!photos.length){$('sheets').innerHTML='<div class="empty-sheet">Cada foto gera seu próprio JPEG.</div>';return;}
  for(const photo of photos){const card=document.createElement('button');card.className='preparation-card';card.disabled=!canEdit();card.onclick=()=>select(photo.id);const title=document.createElement('strong');title.textContent=photo.name;const line=document.createElement('span');line.textContent=photo.plan?`Foto ${dimensions(photo.settings.width_cm,photo.settings.height_cm)} · folha ${photo.plan.sheet.name}`:'Informe as medidas';const state=document.createElement('small');state.textContent=statusText(photo);state.className=pending(photo)?'pending-state':'ready-state';card.append(title,line,state);$('sheets').append(card);}
}
async function sourceFor(photo){
  if(!sources.has(photo.id)){const promise=(async()=>createImageBitmap(await(await api('source',{id:photo.id})).blob()))();sources.set(photo.id,promise);promise.catch(()=>{if(sources.get(photo.id)===promise)sources.delete(photo.id);});}
  const source=await sources.get(photo.id);
  for(const [id,promise] of sources){if(sources.size<=3)break;if(id!==selected){sources.delete(id);promise.then(bitmap=>bitmap.close()).catch(()=>{});}}
  return source;
}
function cropGeometry(photo){
  const settings=photo.settings,plan=photo.plan,[pw,ph]=plan.photo_px;
  const [iw,ih]=settings.rotation%180?[photo.height,photo.width]:[photo.width,photo.height];
  if(settings.mode==='contain')return {iw,ih,left:0,top:0,cw:iw,ch:ih,cx:iw/2,cy:ih/2};
  const scale=Math.min(iw/pw,ih/ph)/settings.zoom,cw=pw*scale,ch=ph*scale;
  const cx=Math.max(cw/2,Math.min(iw-cw/2,settings.cx*iw)),cy=Math.max(ch/2,Math.min(ih-ch/2,settings.cy*ih));
  return {iw,ih,left:cx-cw/2,top:cy-ch/2,cw,ch,cx,cy};
}
function fitPreview(){const photo=current();if(!photo?.plan)return;const [w,h]=photo.plan.sheet.size_px,area=$('canvas-area');const scale=Math.min((area.clientWidth-48)/w,(area.clientHeight-38)/h);$('tile-frame').style.width=Math.max(1,w*scale)+'px';$('tile-frame').style.height=Math.max(1,h*scale)+'px';}
function drawLive(){
  if(frame||closed)return;frame=requestAnimationFrame(async()=>{
    frame=null;const photo=current(),requested=revision;
    if(!photo?.plan||photo.error){$('tile-frame').hidden=true;$('empty-editor').hidden=false;$('empty-hint').textContent=photo?'Informe as medidas ao lado para preparar esta foto.':'Adicione as imagens e informe o tamanho desejado.';$('empty-add').hidden=!!photo;return;}
    try{
      const source=await sourceFor(photo);if(requested!==revision||current()?.id!==photo.id||closed)return;
      const s=photo.settings,p=photo.plan;
      if(oriented?.id!==photo.id||oriented.rotation!==s.rotation){const canvas=document.createElement('canvas');canvas.width=s.rotation%180?source.height:source.width;canvas.height=s.rotation%180?source.width:source.height;const ctx=canvas.getContext('2d');ctx.translate(canvas.width/2,canvas.height/2);ctx.rotate(s.rotation*Math.PI/180);ctx.drawImage(source,-source.width/2,-source.height/2);oriented={id:photo.id,rotation:s.rotation,canvas};}
      const geometry=cropGeometry(photo),[sw,sh]=p.sheet.size_px,[pw,ph]=p.photo_px,scale=Math.min(1000/sw,1000/sh,1),canvas=$('tile-image');canvas.width=Math.max(1,Math.round(sw*scale));canvas.height=Math.max(1,Math.round(sh*scale));
      const area=document.createElement('canvas');area.width=Math.max(1,Math.round(pw*scale));area.height=Math.max(1,Math.round(ph*scale));const ac=area.getContext('2d');ac.fillStyle='white';ac.fillRect(0,0,area.width,area.height);ac.imageSmoothingQuality='high';
      let content=[0,0,area.width,area.height];
      if(s.mode==='contain'){const [cx,cy,right,bottom]=p.content_box;content=[cx*scale,cy*scale,(right-cx)*scale,(bottom-cy)*scale];}
      ac.drawImage(oriented.canvas,geometry.left*oriented.canvas.width/geometry.iw,geometry.top*oriented.canvas.height/geometry.ih,geometry.cw*oriented.canvas.width/geometry.iw,geometry.ch*oriented.canvas.height/geometry.ih,...content);
      const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.save();const [x,y]=p.position_px;ctx.translate(x*scale,y*scale);if(p.sheet.rotation){ctx.translate(area.height,0);ctx.rotate(Math.PI/2);}ctx.drawImage(area,0,0);ctx.restore();
      const [placedW,placedH]=p.placed_photo_px;setOutline($('photo-outline'),x,y,placedW,placedH,sw,sh);
      let [cx,cy,cw,ch]=p.content_box;cw-=cx;ch-=cy;if(p.sheet.rotation)[cx,cy,cw,ch]=[ph-cy-ch,cx,ch,cw];setOutline($('content-outline'),x+cx,y+cy,cw,ch,sw,sh);$('content-outline').hidden=s.mode!=='contain';
      $('tile-frame').hidden=false;$('empty-editor').hidden=true;fitPreview();refreshControls();
    }catch(error){if(requested!==revision)return;$('photo-error').hidden=false;$('photo-error').textContent='Não foi possível carregar a prévia. Selecione a foto novamente para tentar.';toast(error.message);}
  });
}
function setOutline(el,x,y,w,h,sw,sh){el.style.left=(100*x/sw)+'%';el.style.top=(100*y/sh)+'%';el.style.width=(100*w/sw)+'%';el.style.height=(100*h/sh)+'%';}
async function updatePlan(photo){
  photo.planning=true;const request=photo.request=(photo.request||0)+1;const settings={...photo.settings};
  try{const plan=await(await api('plan',{id:photo.id,settings})).json();if(photo.request!==request||!photos.includes(photo))return;photo.plan=plan;photo.error=null;}
  catch(error){if(photo.request!==request||!photos.includes(photo))return;photo.plan=null;photo.error=error.message;}
  photo.planning=false;if(photo.id===selected){revision++;if(!draftDirty)renderSettings();else renderSummary();drawLive();}renderLibrary();renderCards();saveSession();
}
async function select(id){if(!canEdit())return;if(draftDirty)toast('As medidas digitadas não foram aplicadas.');drag=null;revision++;selected=id;draftDirty=false;renderSettings();renderLibrary();drawLive();saveSession();}
function changed(){const photo=current();if(!photo||!canEdit())return;photo.reviewed=false;photo.error=null;photo.planning=true;revision++;drawLive();refreshControls();clearTimeout(planTimer);planTimer=setTimeout(()=>updatePlan(photo),130);saveSession();}
async function applySize(targets,override){
  if(!canEdit()||!targets.length)return;const width=override?.[0]??$('width-cm').value,height=override?.[1]??$('height-cm').value;
  importing=true;refreshControls();refreshSelection();let failures=0;
  for(const photo of targets){photo.request=(photo.request||0)+1;try{const plan=await(await api('measure',{id:photo.id,width_cm:width,height_cm:height,settings:photo.settings})).json();photo.settings=plan.settings;photo.plan=plan;photo.error=null;photo.planning=false;photo.reviewed=false;}catch(error){failures++;toast(`${photo.name}: ${error.message}`);}}
  importing=false;draftDirty=false;revision++;renderSettings();renderLibrary();renderCards();drawLive();saveSession();if(targets.length>1)toast(failures?`${failures} foto(s) não foram alteradas. Confira as medidas.`:`Medidas aplicadas a ${targets.length} fotos. Confira os recortes pendentes.`);
}
async function hydrate(data){const photo={...data,settings:data.settings||defaults(),reviewed:!!data.reviewed,plan:null,error:null};photos.push(photo);try{photo.thumb=replaceUrl('thumb-'+photo.id,await(await api('thumbnail',{id:photo.id})).blob());}catch{photo.thumb=null;}if(photo.settings.width_cm&&photo.settings.height_cm){try{photo.plan=await(await api('plan',{id:photo.id,settings:photo.settings})).json();}catch(error){photo.error=error.message;}}return photo;}
async function importFiles(files){
  if(!canEdit()||document.querySelector('dialog[open]'))return;
  files=files.filter(file=>!['thumbs.db','desktop.ini','.ds_store'].includes(file.name.toLowerCase()));if(!files.length)return;
  importing=true;renderLibrary();let errors=[];let first=null;
  try{for(let index=0;index<files.length;index++){
    const file=files[index];$('activity').textContent=`Importando ${index+1} de ${files.length}`;
    try{if(!/\.(jpe?g|png|webp|bmp|tiff?)$/i.test(file.name))throw new Error('Formato não aceito. Use JPG, PNG, WebP, BMP ou TIFF.');if(file.size>50*1024**2)throw new Error('O arquivo excede 50 MB.');const data=await(await api('upload',file,true,file.name)).json();const photo=await hydrate(data);if(!first)first=photo.id;renderLibrary();}catch(error){errors.push(`${file.name}: ${error.message}`);}
  }}finally{importing=false;$('files').value='';$('activity').textContent='';if(first)selected=first;revision++;renderSettings();renderLibrary();renderCards();drawLive();saveSession();flushRestore();}
  if(errors.length)toast(`${errors.length} arquivo(s) não importados. ${errors.slice(0,2).join(' ')}`);
}
async function removePhoto(photo){if(!canEdit())return;try{await api('delete',{id:photo.id});const index=photos.indexOf(photo);photos=photos.filter(p=>p!==photo);checked.delete(photo.id);if(selected===photo.id)selected=photos[Math.min(index,photos.length-1)]?.id||null;const key='thumb-'+photo.id;if(urls.has(key)){URL.revokeObjectURL(urls.get(key));urls.delete(key);}const source=sources.get(photo.id);sources.delete(photo.id);source?.then(bitmap=>bitmap.close()).catch(()=>{});oriented=null;revision++;renderSettings();renderLibrary();renderCards();drawLive();saveSession();}catch(error){toast(error.message);}}

for(const id of ['add','drop','empty-add'])$(id).onclick=()=>$('files').click();$('files').onchange=event=>importFiles(Array.from(event.target.files));
$('select-all').onchange=()=>{checked=$('select-all').checked?new Set(photos.map(p=>p.id)):new Set();renderLibrary();};
const importArea=$('import-area');let dragDepth=0;
const fileDrag=e=>Array.from(e.dataTransfer?.types||[]).includes('Files');
const acceptsDrop=()=>canEdit()&&!document.querySelector('dialog[open]');
function clearFileDrag(){dragDepth=0;importArea.classList.remove('file-drop-active');}
importArea.addEventListener('dragenter',e=>{if(!fileDrag(e))return;e.preventDefault();dragDepth++;if(acceptsDrop())importArea.classList.add('file-drop-active');});
importArea.addEventListener('dragover',e=>{if(!fileDrag(e))return;e.preventDefault();e.dataTransfer.dropEffect=acceptsDrop()?'copy':'none';});
importArea.addEventListener('dragleave',e=>{if(fileDrag(e)&&--dragDepth<=0)clearFileDrag();});
importArea.addEventListener('drop',e=>{if(!fileDrag(e))return;e.preventDefault();e.stopPropagation();clearFileDrag();if(acceptsDrop())importFiles(Array.from(e.dataTransfer.files));});
for(const type of ['dragover','drop'])document.addEventListener(type,e=>{if(fileDrag(e)){e.preventDefault();if(type==='drop'||!importArea.contains(e.target)){clearFileDrag();e.dataTransfer.dropEffect='none';}}});
document.addEventListener('dragend',clearFileDrag);window.addEventListener('blur',clearFileDrag);
$('dimensions-form').onsubmit=e=>{e.preventDefault();if(current())applySize([current()]);};
$('apply-selection').onclick=()=>applySize(photos.filter(p=>checked.has(p.id)));
for(const id of ['width-cm','height-cm'])$(id).oninput=()=>{draftDirty=true;$('dimension-hint').textContent='Aplique as medidas para atualizar a foto e a folha.';refreshControls();};
$('use-metadata').onclick=()=>{const photo=current();if(photo?.metadata.size_cm)applySize([photo],photo.metadata.size_cm.map(n=>n.toFixed(6)));};
for(const [id,key] of [['fit-mode','mode'],['sheet','sheet'],['position','position']])$(id).onchange=()=>{const photo=current();if(!photo||!canEdit())return;photo.settings[key]=$(id).value;if(key==='mode')Object.assign(photo.settings,{zoom:1,cx:.5,cy:.5});changed();};
function setZoom(value){const photo=current(),number=Number(value);if(!photo||!canEdit()||!Number.isFinite(number)||number<1||number>10){renderSettings();return;}photo.settings.zoom=number;$('zoom').value=number;$('zoom-number').value=number.toFixed(2);$('zoom-value').textContent=number.toFixed(2).replace('.',',')+'×';changed();}
$('zoom').oninput=e=>setZoom(e.target.value);$('zoom-number').onchange=e=>setZoom(e.target.value);
$('center').onclick=()=>{if(current()&&canEdit()){Object.assign(current().settings,{cx:.5,cy:.5});changed();}};
$('rotate').onclick=()=>{if(current()&&canEdit()){const s=current().settings;s.rotation=(s.rotation+90)%360;s.cx=.5;s.cy=.5;changed();}};
$('reset').onclick=()=>{if(current()&&canEdit()){Object.assign(current().settings,{cx:.5,cy:.5,zoom:1,rotation:0});changed();}};
$('tile-frame').onpointerdown=e=>{const photo=current();if(e.button!==0||drag||!photo?.plan||photo.settings.mode!=='cover'||!canEdit())return;e.preventDefault();$('tile-frame').focus({preventScroll:true});drag={id:photo.id,pointerId:e.pointerId,x:e.clientX,y:e.clientY,moved:false};$('tile-frame').setPointerCapture(e.pointerId);$('tile-frame').classList.add('dragging');};
$('tile-frame').onpointermove=e=>{if(!drag||e.pointerId!==drag.pointerId)return;const photo=current();if(!photo?.plan||photo.id!==drag.id)return;const scale=$('tile-frame').clientWidth/photo.plan.sheet.size_px[0];let dx=(e.clientX-drag.x)/scale,dy=(e.clientY-drag.y)/scale;drag.x=e.clientX;drag.y=e.clientY;if(photo.plan.sheet.rotation)[dx,dy]=[dy,-dx];const g=cropGeometry(photo),[pw,ph]=photo.plan.photo_px;const cx=Math.max(g.cw/2,Math.min(g.iw-g.cw/2,g.cx-dx*g.cw/pw)),cy=Math.max(g.ch/2,Math.min(g.ih-g.ch/2,g.cy-dy*g.ch/ph));if(cx!==g.cx||cy!==g.cy){photo.settings.cx=cx/g.iw;photo.settings.cy=cy/g.ih;photo.reviewed=false;revision++;drag.moved=true;drawLive();refreshControls();}};
for(const type of ['pointerup','pointercancel','lostpointercapture'])$('tile-frame').addEventListener(type,e=>{if(!drag||e.pointerId!==drag.pointerId)return;const moved=drag.moved;drag=null;$('tile-frame').classList.remove('dragging');if(moved)changed();flushRestore();});
function reviewPhoto(){const photo=current();if(!photo?.plan||$('review-photo').disabled)return;photo.reviewed=!photo.reviewed;const before=photos.indexOf(photo);if(filterReview&&photo.reviewed)selected=photos.slice(before+1).concat(photos.slice(0,before)).find(pending)?.id||null;revision++;renderSettings();renderLibrary();renderCards();drawLive();saveSession();}
$('review-photo').onclick=reviewPhoto;
$('filter-review').onclick=()=>{filterReview=!filterReview;if(filterReview&&current()&&!pending(current()))selected=visible()[0]?.id||null;revision++;renderSettings();renderLibrary();drawLive();saveSession();};
document.addEventListener('keydown',e=>{if(document.querySelector('dialog[open]')||/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)||e.target.isContentEditable||!canEdit())return;if(e.key.toLowerCase()==='f'&&!e.repeat&&!e.ctrlKey&&!e.metaKey&&!e.altKey){e.preventDefault();reviewPhoto();}if(e.target.closest('#photo-list')&&['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const list=visible(),index=list.findIndex(p=>p.id===selected);const next=list[Math.max(0,Math.min(list.length-1,index+(e.key==='ArrowDown'?1:-1)))];if(next)select(next.id);}});
new ResizeObserver(fitPreview).observe($('canvas-area'));

async function downloadBlob(response,name){const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
function requestExport(targets){if(!canEdit())return;if(draftDirty){toast('Aplique as medidas digitadas antes de exportar.');return;}const ready=targets.filter(p=>!pending(p));if(ready.length!==targets.length){pendingExport=ready;$('export-message').textContent=`${targets.length-ready.length} foto(s) ainda precisam de medidas ou revisão. ${ready.length} estão prontas. As pendentes ficarão fora desta exportação.`;$('export-ready').disabled=!ready.length;$('export-dialog').showModal();}else startExport(ready);}
$('export').onclick=()=>requestExport(photos);$('export-photo').onclick=()=>{if(current())requestExport([current()]);};$('export-ready').onclick=()=>{$('export-dialog').close();startExport(pendingExport);};
async function startExport(targets){
  if(!canEdit()||!targets.length)return;const snapshot=targets.map(item);saveSession();exporting=true;renderLibrary();renderCards();$('job-panel').hidden=false;$('job-errors').replaceChildren();$('download-result').hidden=true;$('cancel-export').hidden=false;$('cancel-export').disabled=true;
  try{const {job}=await(await api('export/start',{items:snapshot})).json();lastJob=job;$('cancel-export').disabled=false;
    while(!closed){const state=await(await api('export/status',{job})).json();$('job-title').textContent=state.state==='running'?'Preparando arquivos':state.state==='ready'?'Arquivos prontos':state.state==='cancelled'?'Exportação cancelada':'Confira os arquivos';$('job-progress').value=(state.done+(state.state==='running'?state.percent/100:0))/state.total*100;$('job-status').textContent=`${state.done} de ${state.total} processadas · ${state.success} JPEG(s) gerados${state.error?' · '+state.error:''}`;
      if(state.state!=='running'){$('cancel-export').hidden=true;for(const result of state.items){if(result.error){const li=document.createElement('li');li.textContent=`${result.name}: ${result.error}`;$('job-errors').append(li);}}if(state.state==='ready'){$('download-result').hidden=false;$('download-result').dataset.filename=state.filename;await downloadBlob(await api('export/download',{job}),state.filename);toast(state.success===state.total?'Download iniciado.':'Download iniciado com os JPEGs válidos e um relatório das falhas.');}break;}
      await new Promise(resolve=>setTimeout(resolve,400));
    }
  }catch(error){toast(error.message);$('job-status').textContent=error.message;$('cancel-export').hidden=true;}finally{exporting=false;renderLibrary();renderCards();saveSession();flushRestore();}
}
$('cancel-export').onclick=async()=>{if(!lastJob)return;$('cancel-export').disabled=true;try{await api('export/cancel',{job:lastJob});$('job-status').textContent='Cancelando e liberando os recursos…';}catch(error){toast(error.message);$('cancel-export').disabled=false;}};
$('download-result').onclick=async()=>{try{await downloadBlob(await api('export/download',{job:lastJob}),$('download-result').dataset.filename);}catch(error){toast(error.message);}};

$('clear-all').onclick=()=>{if(canEdit())$('clear-dialog').showModal();};
$('clear-confirm').onclick=async()=>{if(!canEdit())return;clearing=true;refreshControls();$('clear-confirm').disabled=true;$('clear-cancel').disabled=true;try{await api('clear',{ids:photos.map(p=>p.id)});releaseImages();photos=[];selected=null;checked.clear();$('clear-dialog').close();}catch(error){toast(error.message);}finally{clearing=false;$('clear-confirm').disabled=false;$('clear-cancel').disabled=false;renderSettings();renderLibrary();renderCards();drawLive();saveSession();flushRestore();}};
$('clear-dialog').addEventListener('cancel',e=>{if(clearing)e.preventDefault();});
$('save-project').onclick=async()=>{if(!canEdit()||!photos.length)return;const snapshot=photos.map(item);saveSession();importing=true;refreshControls();try{await downloadBlob(await api('project/save',{items:snapshot}),'Meu lote.medidas');}catch(error){toast(error.message);}finally{importing=false;refreshControls();saveSession();flushRestore();}};
$('open-project').onclick=()=>{if(!canEdit())return;if(photos.length&&!confirm('Abrir outro lote substitui as fotos desta sessão. Você já salvou ou exportou o trabalho?'))return;$('project-file').click();};
$('project-file').onchange=async e=>{const file=e.target.files[0];if(!file||!canEdit())return;importing=true;refreshControls();try{const data=await(await api('project/open',file,true)).json();releaseImages();photos=[];checked.clear();for(const photo of data.photos)await hydrate(photo);selected=photos[0]?.id||null;filterReview=false;}catch(error){toast(error.message);}finally{importing=false;e.target.value='';revision++;renderSettings();renderLibrary();renderCards();drawLive();saveSession();flushRestore();}};
$('help').onclick=()=>$('help-dialog').showModal();document.querySelectorAll('[data-close-dialog]').forEach(button=>button.onclick=()=>button.closest('dialog').close());
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',e=>{if(e.target!==dialog||clearing)return;const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}));
$('quit').onclick=async()=>{if(!canEdit()){toast('Aguarde a operação terminar antes de encerrar.');return;}if(photos.length&&!confirm('Salvou o lote ou exportou os JPEGs? Encerrar descarta esta sessão.'))return;try{await api('quit');closed=true;releaseImages();releaseOwnership?.();channel?.close();localStorage.removeItem(sessionKey);clearInterval(heartbeat);document.body.innerHTML='<main class="goodbye"><h1>Até a próxima impressão.</h1><p>O Medidas Editor foi encerrado. Você pode fechar esta aba.</p></main>';}catch(error){toast(error.message);}};
async function refreshStatus(){const state=await(await api('heartbeat')).json();const update=state.update||{};$('update-status').hidden=!['available','downloading','ready'].includes(update.state);$('update-label').textContent=update.state==='downloading'?'Baixando atualização':'Atualização disponível';}
const heartbeat=setInterval(()=>{refreshStatus().catch(()=>{clearInterval(heartbeat);toast('A sessão foi encerrada. Abra o Medidas Editor novamente.');});},20000);

function restoreSession(saved){
  if(!saved||saved.token!==token||!Array.isArray(saved.photos))return Promise.resolve();
  if(restoreTask){pendingRestore=saved;return restoreTask;}
  const work=async()=>{
    restoring=true;releaseImages();photos=[];checked.clear();refreshControls();
    try{for(const data of saved.photos.slice(0,100)){try{await hydrate(data);}catch{toast('Uma foto não está mais disponível. Importe-a novamente.');}}selected=photos.some(p=>p.id===saved.selected)?saved.selected:photos[0]?.id||null;filterReview=!!saved.filterReview;sessionRevision=saved.sessionRevision||0;}
    finally{restoring=false;revision++;renderSettings();renderLibrary();renderCards();drawLive();}
  };
  restoreTask=work().finally(()=>{restoreTask=null;flushRestore();});return restoreTask;
}
function flushRestore(){if(!pendingRestore||drag||importing||exporting||restoring||clearing||closed)return;const saved=pendingRestore;pendingRestore=null;if((saved.sessionRevision||0)>sessionRevision)restoreSession(saved).catch(error=>toast(error.message));}
function tryAcquireEditor(wait=false){
  if(acquiring||editingAllowed||closed||!wait&&passiveAfterYield)return;if(wait)passiveAfterYield=false;
  if(!navigator.locks){editingAllowed=true;renderLibrary();return;}
  acquiring=true;const controller=wait?new AbortController():null;const timeout=controller?setTimeout(()=>controller.abort(),5000):null;
  navigator.locks.request('medidas-editor:editing:'+token,controller?{signal:controller.signal}:{ifAvailable:true},async lock=>{
    clearTimeout(timeout);acquiring=false;if(!lock){refreshControls();return;}editingAllowed=true;const hold=new Promise(resolve=>releaseOwnership=resolve),saved=readSession();
    if(saved?.token===token&&(saved.sessionRevision||0)>sessionRevision)await restoreSession(saved);renderLibrary();await hold;releaseOwnership=null;editingAllowed=false;
  }).catch(error=>{clearTimeout(timeout);acquiring=false;toast(error.name==='AbortError'?'A outra aba está ocupada. Aguarde a operação terminar.':'Não foi possível ativar a edição nesta aba.');});
}
function yieldEditor(){if(!canEdit())return false;saveSession();passiveAfterYield=true;editingAllowed=false;drag=null;clearTimeout(planTimer);renderLibrary();renderCards();releaseOwnership?.();return true;}
function fulfillYield(deadline=Date.now()+4500){if(closed||!editingAllowed)return;if(!yieldEditor()&&Date.now()<deadline)setTimeout(()=>fulfillYield(deadline),100);}
if(channel)channel.onmessage=e=>{if(closed)return;if(e.data.type==='yield'&&editingAllowed)fulfillYield();};
$('takeover').onclick=()=>{if(acquiring)return;channel?.postMessage({type:'yield',from:tabId});tryAcquireEditor(true);};
window.addEventListener('storage',e=>{if(e.key===sessionKey&&e.newValue&&!closed){try{pendingRestore=JSON.parse(e.newValue);flushRestore();}catch{}}});
window.addEventListener('focus',()=>{if(!editingAllowed)tryAcquireEditor();});
window.addEventListener('pagehide',()=>{saveSession();editingAllowed=false;releaseOwnership?.();});
window.addEventListener('pageshow',e=>{if(e.persisted){pendingRestore=readSession();flushRestore();tryAcquireEditor();}});
renderSettings();renderLibrary();drawLive();tryAcquireEditor();refreshStatus().catch(()=>{});

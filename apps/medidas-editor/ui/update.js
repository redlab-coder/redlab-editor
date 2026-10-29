/* Shared update flow: owner-only checkpoint, verified restart and recovery. */
'use strict';
window.RedLabUpdate=options=>{
  const badge=document.getElementById('update-status'),label=document.getElementById('update-label');
  let state={},queued=false,applying=false,recovered=false;
  function paint(){
    badge.hidden=!['available','downloading','ready'].includes(state.state)&&!queued&&!applying;
    label.textContent=applying?'Salvando lote…':queued?'Aguardando operação…':state.state==='ready'?'Atualizar e reiniciar':state.state==='downloading'?'Baixando atualização':'Atualização disponível';
    badge.disabled=state.state!=='ready'||queued||applying||!options.canActivate();
    badge.title=`Versão ${state.version||''}. `+(state.state==='ready'?'Salva o lote, atualiza e reabre o editor.':'O download será concluído automaticamente.');
    badge.setAttribute('aria-label',label.textContent+'. '+badge.title);
  }
  function finish(){
    options.setApplying(false);applying=false;options.refresh();paint();
  }
  async function attempt(){
    if(!queued||applying||!options.canActivate()||options.busy())return;
    applying=true;options.setApplying(true);options.refresh();paint();
    try{
      await options.api('update/apply',options.snapshot());
      queued=false;options.onRestart();
    }catch(error){
      if(error.status===409){finish();return;}
      queued=false;finish();options.toast(error.message);
    }
  }
  badge.onclick=()=>{if(state.state!=='ready'||!options.canActivate())return;queued=true;paint();attempt();};
  const timer=setInterval(()=>{if(options.closed()){clearInterval(timer);return;}if(queued)attempt();},500);
  async function bootstrap(){
    try{
      const data=await(await options.api('update/recovery')).json();
      // Startup restores a same-process browser session before checking a checkpoint.
      const deadline=Date.now()+30000;
      while(options.starting()&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,30));
      if(data.error){document.getElementById('recovery-error-text').textContent=data.error;document.getElementById('recovery-error-dialog').showModal();}
      else if(Array.isArray(data.photos)&&options.owner()){
        await options.restore(data);recovered=true;
      }
      options.setBootBusy(false);options.refresh();options.afterRestore();const saved=options.save();paint();
      if(recovered&&saved!==false){
        try{await options.api('update/ack',{generation:data.generation});options.toast('Lote recuperado após a atualização.');}
        catch{options.toast('Lote recuperado. A cópia de segurança foi mantida.');}
      }else if(recovered)options.toast('Lote recuperado. A cópia de segurança foi mantida.');
    }catch(error){options.setBootBusy(false);options.refresh();options.toast('Não foi possível consultar a recuperação. '+error.message);paint();}
  }
  return {setState(value){state=value||{};paint();},paint,bootstrap};
};

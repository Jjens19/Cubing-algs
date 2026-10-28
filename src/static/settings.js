let resetBusy=false;
function updateResetSummary(){
  const all=$('reset-scope').value==='all',subset=$('reset-subset').value;
  const cases=library.cases.filter(c=>all||c.alg_set===subset);
  const changed=cases.filter(c=>c.learned||c.learning).length;
  $('reset-subset-label').hidden=all;
  $('reset-shared').hidden=all||subset!=='Anti PLL';
  $('reset-summary').textContent=`${changed} of ${cases.length} cases ${all?'in the entire library':'in '+subset} will return to Not learned.`;
  $('review-reset').disabled=!changed||resetBusy;
  $('reset-confirmation').hidden=true;
  $('review-reset').hidden=false;
  $('settings-status').textContent='';
}
$('open-settings').onclick=()=>{
  options($('reset-subset'),library.sets,set);
  $('reset-scope').value='subset';
  updateResetSummary();$('settings').showModal();
};
$('reset-scope').onchange=updateResetSummary;$('reset-subset').onchange=updateResetSummary;
$('review-reset').onclick=()=>{
  $('reset-confirmation-text').textContent=$('reset-summary').textContent+' This cannot be undone. Continue?';
  $('reset-confirmation').hidden=false;$('review-reset').hidden=true;$('confirm-reset').focus();
};
$('cancel-reset').onclick=()=>{updateResetSummary();$('review-reset').focus();};
$('confirm-reset').onclick=async()=>{
  if(resetBusy)return;
  resetBusy=true;
  for(const id of ['confirm-reset','cancel-reset','reset-scope','reset-subset','close-settings'])$(id).disabled=true;
  try{
    const result=await api('reset-progress',{scope:$('reset-scope').value,alg_set:$('reset-subset').value,confirmed:true});
    await load();
    updateResetSummary();
    $('settings-status').textContent=`Progress reset for ${result.reset} ${result.reset===1?'case':'cases'}.`;
  }catch(error){$('settings-status').textContent='Could not reset progress: '+error.message;}
  finally{
    resetBusy=false;
    for(const id of ['confirm-reset','cancel-reset','reset-scope','reset-subset','close-settings'])$(id).disabled=false;
  }
};
$('close-settings').onclick=()=>{if(!resetBusy)$('settings').close();};
$('settings').addEventListener('cancel',event=>{if(resetBusy)event.preventDefault();});

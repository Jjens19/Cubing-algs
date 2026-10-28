'use strict';
const timerElement=id=>document.getElementById(id);
const sessionKey='cube-library-timer-v2';
let sessions=[],activeSessionId,solves=[],state='idle',held=null,started=0,frame=0,scramble='';
let sessionAction='new',analyticsSolve=null,analyticsDismissed=false;
let timerMode='click',bluetoothConnected=false,previousTimerMode='click';
const scrambleHistory=[];
try{if(localStorage.getItem('cube-library-timer-mode')==='type')timerMode='type';}catch{}
function timerDialogOpen(){return timerElement('session-dialog').open||timerElement('timer-settings').open||timerElement('cube-mac-dialog').open||timerElement('local-cube-dialog').open;}
function idleInstruction(){if(timerMode==='bluetooth')return bluetoothConnected?'Apply the displayed scramble to your cube. Waiting for the correct state…':'Connect a Bluetooth cube to begin.';return timerMode==='type'?'Enter your completed solve time and press Enter to save.':'Hold Space, then release to start. Press any key to stop.';}
function updateTimerControls(){
  const busy=['loading','running','armed','settling'].includes(state);
  timerElement('last-scramble').disabled=busy||!scrambleHistory.length;
  timerElement('save-typed-time').disabled=busy||!scramble;
  timerElement('timer-settings-button').disabled=['running','armed','settling'].includes(state);
  const reset=timerElement('reset-bluetooth-cube');if(reset){reset.dataset.timerLocked=String(['running','settling'].includes(state));reset.disabled=reset.dataset.timerLocked==='true';}
}
function renderTimerMode(){
  timerElement('timer-mode').value=timerMode;
  timerElement('timer-clock').hidden=timerMode==='type';
  timerElement('click-timer-help').hidden=timerMode!=='click';
  timerElement('typed-time-form').hidden=timerMode!=='type';
  if(state==='idle')timerElement('timer-instruction').textContent=idleInstruction();
  updateTimerControls();
}
timerElement('timer-settings-button').onclick=()=>{if(state==='running'||state==='armed')return;timerElement('timer-settings').showModal();};
timerElement('close-timer-settings').onclick=()=>timerElement('timer-settings').close();
timerElement('timer-mode').onchange=()=>{
  timerMode=timerElement('timer-mode').value;
  try{localStorage.setItem('cube-library-timer-mode',timerMode);}catch{}
  renderTimerMode();syncBluetoothTimer();
};
function parseTypedTime(value){
  const text=value.trim();
  if(!/^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(text))throw Error('Enter a positive time using digits and at most one comma or dot.');
  const ms=Number(text.replace(',','.'))*(/[.,]/.test(text)?1000:10);
  if(!Number.isFinite(ms)||ms<=0||ms>Number.MAX_SAFE_INTEGER)throw Error('Enter a positive, valid time.');
  return Math.round(ms);
}
timerElement('typed-time-form').onsubmit=event=>{
  event.preventDefault();
  if(timerMode!=='type'||state!=='idle'||!scramble||timerDialogOpen())return;
  try{
    const ms=parseTypedTime(timerElement('typed-time').value);
    timerElement('typed-time-error').textContent='';
    saveSolve(ms);timerElement('typed-time').value='';timerElement('typed-time').focus();
  }catch(error){timerElement('typed-time-error').textContent=error.message;}
};
timerElement('typed-time').oninput=()=>{timerElement('typed-time-error').textContent='';};
timerElement('last-scramble').onclick=()=>{
  if(state!=='idle'||!scrambleHistory.length)return;
  scramble=scrambleHistory.pop();timerElement('timer-scramble').textContent=scramble;
  timerElement('timer-instruction').textContent=idleInstruction();updateTimerControls();syncBluetoothTimer();
};

function validSolves(value){return Array.isArray(value)?value.filter(s=>s&&Number.isFinite(s.ms)&&s.ms>=0&&typeof s.scramble==='string'&&['OK','+2','DNF'].includes(s.penalty)):[];}
try{
  const saved=JSON.parse(localStorage.getItem(sessionKey)||'null');
  if(saved&&Array.isArray(saved.sessions)){
    const ids=new Set();
    sessions=saved.sessions.filter(s=>{
      if(!s||typeof s.id!=='string'||ids.has(s.id)||typeof s.name!=='string'||!s.name.trim())return false;
      ids.add(s.id);return true;
    }).map(s=>({id:s.id,name:s.name,solves:validSolves(s.solves)}));
    activeSessionId=saved.activeSessionId;
  }
  if(!sessions.length){
    const legacy=JSON.parse(localStorage.getItem('cube-library-timer-v1')||'[]');
    sessions=[{id:crypto.randomUUID(),name:'Default session',solves:validSolves(legacy)}];
  }
}catch{timerElement('timer-storage').textContent='Could not read the saved sessions. Export new solves to keep them.';}
if(!sessions.length)sessions=[{id:crypto.randomUUID(),name:'Default session',solves:[]}];
activeSessionId=sessions.some(s=>s.id===activeSessionId)?activeSessionId:sessions[0].id;
function activeSession(){return sessions.find(s=>s.id===activeSessionId);}
solves=activeSession().solves;
function renderSessions(){
  const select=timerElement('timer-session');
  select.replaceChildren(...sessions.map(session=>{const option=document.createElement('option');option.value=session.id;option.textContent=session.name;return option;}));
  select.value=activeSessionId;
}
function lockSessions(locked){for(const id of ['timer-session','new-session','rename-session'])timerElement(id).disabled=locked;}
function openSessionDialog(action){
  if(state==='running'||state==='armed')return;
  sessionAction=action;
  timerElement('session-dialog-title').textContent=action==='new'?'New session':'Rename session';
  timerElement('session-name').value=action==='new'?'':activeSession().name;
  timerElement('session-error').textContent='';
  timerElement('session-dialog').showModal();timerElement('session-name').focus();
}
timerElement('new-session').onclick=()=>openSessionDialog('new');
timerElement('rename-session').onclick=()=>openSessionDialog('rename');
timerElement('cancel-session').onclick=()=>timerElement('session-dialog').close();
timerElement('session-form').onsubmit=event=>{
  event.preventDefault();
  const name=timerElement('session-name').value.trim();
  if(!name){timerElement('session-error').textContent='Enter a session name.';return;}
  if(sessionAction==='new'){
    const session={id:crypto.randomUUID(),name,solves:[]};sessions.push(session);activeSessionId=session.id;solves=session.solves;
    if(state==='idle')cancel();hideSolveAnalytics();
  }else activeSession().name=name;
  persist();renderSessions();renderHistory();timerElement('session-dialog').close();syncBluetoothTimer();
};
timerElement('timer-session').onchange=()=>{
  if(state==='running'||state==='armed'){timerElement('timer-session').value=activeSessionId;return;}
  hideSolveAnalytics();
  activeSessionId=timerElement('timer-session').value;solves=activeSession().solves;
  if(state==='idle')cancel();
  persist();renderHistory();syncBluetoothTimer();
};
function formatTime(ms){
  if(!Number.isFinite(ms))return 'DNF';
  const centiseconds=Math.floor(ms/10),seconds=Math.floor(centiseconds/100);
  return (seconds>=60?Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0'):String(seconds))+'.'+String(centiseconds%100).padStart(2,'0');
}
function solveTime(s){return s.penalty==='DNF'?Infinity:s.ms+(s.penalty==='+2'?2000:0);}
function averageValue(window){
  // Trim 5% from each end, rounding up (one solve for ao5/ao12, five for ao100).
  const trim=Math.ceil(window.length*.05);
  const times=window.map(solveTime).sort((a,b)=>a-b).slice(trim,-trim);
  return times.reduce((sum,time)=>sum+time,0)/times.length;
}
function average(size){
  return solves.length<size?'—':formatTime(averageValue(solves.slice(-size)));
}
function bestAverage(size){
  if(solves.length<size)return '—';
  let best=Infinity;
  for(let end=size;end<=solves.length;end++)best=Math.min(best,averageValue(solves.slice(end-size,end)));
  return formatTime(best);
}
function persist(){
  try{localStorage.setItem(sessionKey,JSON.stringify({activeSessionId,sessions}));timerElement('timer-storage').textContent='Your sessions are saved in this browser.';}
  catch{timerElement('timer-storage').textContent='Browser storage is unavailable or full. Export your solves to keep them.';}
}
async function newScramble(){
  if(['running','armed','loading','settling'].includes(state))return;
  const previousScramble=scramble;
  state='loading';scramble='';bluetoothTimer.configure(false,'');updateTimerControls();
  timerElement('next-scramble').disabled=true;
  timerElement('timer-scramble').textContent='Generating a TNoodle scramble…';timerElement('scramble-guidance').hidden=true;
  timerElement('timer-instruction').textContent='Preparing your scramble…';
  try{
    const response=await fetch('/api/timer-scramble',{cache:'no-store'});
    const data=await response.json();
    if(!response.ok)throw Error(data.error||'Could not generate a scramble.');
    if(typeof data.scramble!=='string'||!data.scramble.trim())throw Error('No scramble was returned.');
    if(previousScramble)scrambleHistory.push(previousScramble);
    scramble=data.scramble;timerElement('timer-scramble').textContent=scramble;
    timerElement('timer-instruction').textContent=idleInstruction();
  }catch(error){
    timerElement('timer-scramble').textContent='Scramble unavailable';
    timerElement('timer-instruction').textContent=error.message+' Use New scramble to retry.';
  }finally{state='idle';timerElement('next-scramble').disabled=false;updateTimerControls();syncBluetoothTimer();}
}
function renderHistory(){
  timerElement('stat-count').textContent=solves.length;
  timerElement('stat-best').textContent=solves.length?formatTime(solves.reduce((best,s)=>Math.min(best,solveTime(s)),Infinity)):'—';
  timerElement('stat-mean').textContent=solves.length?formatTime(solves.reduce((sum,s)=>sum+solveTime(s),0)/solves.length):'—';
  for(const size of [5,12,100]){
    timerElement('stat-ao'+size).textContent=average(size);
    timerElement('stat-best-ao'+size).textContent=bestAverage(size);
  }
  timerElement('no-solves').hidden=!!solves.length;
  const rows=solves.map((solve,index)=>{
    const row=document.createElement('tr');
    const cell=text=>{const td=document.createElement('td');td.textContent=text;row.append(td);return td;};
    cell(index+1);cell(formatTime(solveTime(solve))+(solve.penalty==='+2'?'+':''));
    const select=document.createElement('select');select.setAttribute('aria-label',`Penalty for solve ${index+1}`);
    for(const value of ['OK','+2','DNF']){const option=document.createElement('option');option.value=value;option.textContent=value;select.append(option);}select.value=solve.penalty;
    select.onchange=()=>{solve.penalty=select.value;persist();renderHistory();};cell('').append(select);
    cell(solve.scramble);
    const remove=document.createElement('button');remove.type='button';remove.textContent='Delete';remove.setAttribute('aria-label',`Delete solve ${index+1}`);
    remove.onclick=()=>{if(analyticsSolve===solve)hideSolveAnalytics();solves.splice(index,1);persist();renderHistory();};
    const actions=cell('');actions.className='solve-actions';
    if(solve.source==='bluetooth'){const analytics=document.createElement('button');analytics.type='button';analytics.textContent='Analytics';analytics.setAttribute('aria-label',`Analytics for solve ${index+1}`);analytics.onclick=()=>showSolveAnalytics(solve,true);actions.append(analytics);}
    actions.append(remove);return row;
  });
  timerElement('solve-list').replaceChildren(...rows.reverse());
  if(analyticsSolve&&!timerElement('solve-analytics').hidden)showSolveAnalytics(analyticsSolve);
}
function tick(){timerElement('timer-clock').textContent=formatTime(performance.now()-started);frame=requestAnimationFrame(tick);}
function arm(source){if(timerMode!=='click'||state!=='idle'||held||!scramble||timerDialogOpen())return;lockSessions(true);held=source;state='armed';updateTimerControls();timerElement('timer-clock').classList.add('armed');timerElement('timer-instruction').textContent='Release to start.';}
function release(source){
  if(held!==source)return;held=null;
  if(state!=='armed')return;
  state='running';started=performance.now();timerElement('timer-clock').className='running';
  timerElement('next-scramble').disabled=true;timerElement('timer-instruction').textContent='Solving… Press any key or touch the timer to stop.';tick();
}
function stop(){
  const ms=performance.now()-started;cancelAnimationFrame(frame);state='idle';lockSessions(false);timerElement('timer-clock').className='';timerElement('timer-clock').textContent=formatTime(ms);
  saveSolve(ms);
}
function saveSolve(ms){
  solves.push({ms,penalty:'OK',scramble,date:new Date().toISOString()});persist();renderHistory();newScramble();
}
function cancel(){if(state==='loading')return;cancelAnimationFrame(frame);state='idle';lockSessions(false);held=null;timerElement('timer-clock').className='';timerElement('timer-clock').textContent='0.00';timerElement('next-scramble').disabled=false;timerElement('timer-instruction').textContent=idleInstruction();updateTimerControls();}
function interactive(event){return event.target.closest('input,select,textarea,a,button')&&event.target!==timerElement('timer-clock');}
document.addEventListener('keydown',event=>{
  if(timerDialogOpen()||timerMode==='type')return;
  if(event.key==='Escape'){if(timerMode==='bluetooth')syncBluetoothTimer();else cancel();return;}
  if(timerMode==='bluetooth')return;
  if(event.repeat)return;
  if(state==='running'){event.preventDefault();held=event.code;stop();return;}
  if(event.code!=='Space'||interactive(event))return;
  event.preventDefault();arm(event.code);
});
document.addEventListener('keyup',event=>{if(event.code===held){event.preventDefault();release(event.code);}});
const clock=timerElement('timer-clock');
clock.addEventListener('pointerdown',event=>{if(timerMode==='bluetooth'||event.button!==0)return;event.preventDefault();clock.setPointerCapture(event.pointerId);if(state==='running'){held='pointer';stop();}else arm('pointer');});
clock.addEventListener('pointerup',()=>release('pointer'));
clock.addEventListener('pointercancel',()=>{if(state==='armed')cancel();held=null;});
window.addEventListener('blur',()=>{if(state==='armed')cancel();held=null;});
timerElement('next-scramble').onclick=()=>{if(state==='idle')newScramble();};
timerElement('clear-solves').onclick=()=>{if(solves.length&&confirm('Clear all solves from this timer session?')){solves.splice(0);hideSolveAnalytics();persist();renderHistory();}};
timerElement('export-solves').onclick=()=>{
  const url=URL.createObjectURL(new Blob([JSON.stringify({puzzle:'3x3',session:activeSession().name,solves},null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='cube-library-solves.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
function hideSolveAnalytics(){timerElement('solve-analytics').hidden=true;analyticsSolve=null;}
function showSolveAnalytics(solve,scroll=false){
  analyticsSolve=solve;
  timerElement('analytics-method').value=['CFOP','CFCE','Roux'].includes(solve.analyticsMethod)?solve.analyticsMethod:'auto';
  const analysis=SolveAnalytics.analyze(solve),widget=timerElement('solve-analytics');
  widget.hidden=false;
  const summary=timerElement('analytics-summary');summary.replaceChildren();
  const stats=[['Method',analysis.method],['Solve time',formatTime(solve.ms)],['Result',formatTime(solveTime(solve))+(solve.penalty==='+2'?' (+2)':'')],['Moves',analysis.moves.length?String(analysis.moves.length):'—'],['TPS',solve.ms>0&&analysis.moves.length?(analysis.moves.length/(solve.ms/1000)).toFixed(2):'—']];
  for(const [label,value] of stats){const item=document.createElement('div'),title=document.createElement('span'),number=document.createElement('strong');title.textContent=label;number.textContent=value;item.append(title,number);summary.append(item);}
  timerElement('analytics-selection-status').textContent=solve.analyticsMethod?`Using ${solve.analyticsMethod} for this solve · saved`:'Using automatic method detection';
  timerElement('analytics-method-note').textContent=analysis.note;
  const rows=analysis.rows.map(step=>{
    const tr=document.createElement('tr');if(step.child)tr.className='analytics-pair';if(step.group)tr.className='analytics-group';
    for(const text of [step.name,formatTime(step.ms),formatTime(step.endMs)]){const td=document.createElement('td');td.textContent=text;tr.append(td);}
    const sequence=document.createElement('td');sequence.className='analytics-step-moves';
    const moves=SolveAnalytics.groupMoves(Number.isInteger(step.startIndex)?SolveAnalytics.solutionMoves(solve,analysis.moves,step.startIndex,step.endIndex):step.moves.map(move=>({move,ms:null})));
    if(!moves.length)sequence.textContent='Already solved / skipped';
    else for(const item of moves){
      const move=document.createElement('span');move.textContent=item.move;
      if(item.rotation){move.className='analytics-rotation';move.title='Cube rotation';}
      sequence.append(move,' ');
    }
    tr.append(sequence);return tr;
  });
  timerElement('analytics-steps').replaceChildren(...rows);
  timerElement('analytics-scramble').textContent=solve.scramble||'No scramble saved for this solve.';
  timerElement('analytics-rotation-note').textContent=solve.trace?.gyroAvailable?'Rotations are estimated from the gyro. Initial rotations show the starting orientation; later rotations appear where they occurred. Face-turn counts and TPS exclude rotations.':'Rotation data is unavailable for this recording; rotations cannot be reconstructed from face turns alone.';
  const solution=timerElement('analytics-solution');solution.replaceChildren();
  if(!analysis.moves.length)solution.textContent='No move recording is available for this solve.';
  else for(const item of SolveAnalytics.groupMoves(SolveAnalytics.solutionMoves(solve,analysis.moves))){
    const move=document.createElement('span');move.textContent=item.move;if(item.rotation)move.className='analytics-rotation';
    const label=item.count>1?`Moves ${item.firstIndex+1}–${item.lastIndex+1}`:`Move ${item.firstIndex+1}`;
    move.title=Number.isFinite(item.startMs)?`${label} · ${formatTime(item.startMs)}${item.count>1?'–'+formatTime(item.endMs):''} s`:`${label} · timing unavailable`;solution.append(move,' ');
  }
  if(scroll)widget.scrollIntoView({behavior:'smooth',block:'start'});
}
function changeAnalyticsMethod(){
  if(!analyticsSolve)return;
  const method=timerElement('analytics-method').value;
  if(method==='auto')delete analyticsSolve.analyticsMethod;else analyticsSolve.analyticsMethod=method;
  persist();showSolveAnalytics(analyticsSolve);
}
timerElement('analytics-method').addEventListener('input',changeAnalyticsMethod);
timerElement('analytics-method').addEventListener('change',changeAnalyticsMethod);
timerElement('close-solve-analytics').onclick=()=>{analyticsDismissed=true;hideSolveAnalytics();};
const scrambleGuide=new BluetoothScrambleGuide();
function renderScrambleGuidance(){
  const display=timerElement('timer-scramble'),help=timerElement('scramble-guidance');
  help.hidden=true;
  if(!scramble)return;
  if(!bluetoothConnected){display.textContent=scramble;return;}
  const correcting=scrambleGuide.undo.length>0&&!['running','settling'].includes(state);
  const tokens=correcting?scrambleGuide.undo:scrambleGuide.tokens;
  const spans=tokens.map((move,index)=>{
    const span=document.createElement('span');span.textContent=move;
    if(correcting)span.className='scramble-undo';
    else if(index<scrambleGuide.index)span.className='scramble-done';
    if(!correcting&&index===scrambleGuide.index)span.classList.add('scramble-next');
    return span;
  });
  display.replaceChildren(...spans.flatMap((span,index)=>index?[' ',span]:[span]));
  if(correcting){help.hidden=false;help.textContent='Undo these moves to return to your scramble.';}
  else if(scrambleGuide.unknown){help.hidden=false;help.textContent='Start with a solved cube to track scramble moves. Reset its Bluetooth state if the physical cube is already solved.';}
}
const bluetoothTimer=new BluetoothSolveTimer({
  ready(){
    if(timerMode!=='bluetooth'||state==='loading')return;
    timerElement('timer-clock').textContent='READY';timerElement('timer-clock').className='armed';
    timerElement('timer-instruction').textContent='Scramble matched. Turn a face to start.';
  },
  wait(){
    if(timerMode==='bluetooth'&&state==='idle'){
      timerElement('timer-clock').textContent='0.00';timerElement('timer-clock').className='';
      timerElement('timer-instruction').textContent=idleInstruction();
    }
  },
  start(){
    state='running';started=performance.now();held=null;lockSessions(true);
    timerElement('timer-clock').className='running';timerElement('next-scramble').disabled=true;
    timerElement('timer-instruction').textContent='Solving… Timer stops when the cube is solved.';
    updateTimerControls();tick();
  },
  stop(result){
    analyticsDismissed=false;
    state='settling';cancelAnimationFrame(frame);timerElement('timer-clock').className='';
    timerElement('timer-clock').textContent=formatTime(result.ms);
    timerElement('timer-instruction').textContent='Solved. Checking for a turn within 0.3 seconds…';
    updateTimerControls();
  },
  finish(result){
    result.scramble=scramble;result.date=new Date().toISOString();result.source='bluetooth';
    solves.push(result);persist();renderHistory();
    if(!analyticsDismissed)showSolveAnalytics(result);
    state='idle';lockSessions(false);
    timerElement('timer-clock').textContent=formatTime(solveTime(result))+(result.penalty==='+2'?'+':'');
    newScramble();
  },
  penalty(result){
    persist();renderHistory();
    if(timerMode==='bluetooth'){
      timerElement('timer-clock').textContent=formatTime(solveTime(result))+'+';
      timerElement('timer-instruction').textContent='+2: a turn was detected within 0.3 seconds of solving.';
    }
  },
  cancel(){
    if(state==='running'){cancel();}
    if(timerElement('timer-clock').textContent==='READY'){
      timerElement('timer-clock').textContent='0.00';timerElement('timer-clock').className='';
    }
  }
});
function syncBluetoothTimer(){
  bluetoothTimer.configure(timerMode==='bluetooth'&&bluetoothConnected&&state!=='loading',scramble);
  scrambleGuide.configure(scramble);renderScrambleGuidance();
}
document.addEventListener('bluetooth-cube-connected',()=>{
  bluetoothConnected=true;previousTimerMode=timerMode==='bluetooth'?'click':timerMode;
  cancel();timerMode='bluetooth';renderTimerMode();syncBluetoothTimer();
});
document.addEventListener('bluetooth-cube-disconnected',()=>{
  bluetoothConnected=false;bluetoothTimer.reset();scrambleGuide.reset();renderScrambleGuidance();
  if(timerMode==='bluetooth'){timerMode=previousTimerMode;cancel();renderTimerMode();}
});
document.addEventListener('bluetooth-cube-reset',()=>{bluetoothTimer.reset();scrambleGuide.reset();renderScrambleGuidance();});
document.addEventListener('bluetooth-cube-event',event=>{
  bluetoothTimer.enabled=timerMode==='bluetooth'&&bluetoothConnected&&state!=='loading'&&!timerDialogOpen();
  if(event.detail.type==='MOVE'){analyticsDismissed=true;hideSolveAnalytics();}
  scrambleGuide.event(event.detail);
  bluetoothTimer.event(event.detail);if(event.detail.type!=='GYRO')renderScrambleGuidance();
});
renderSessions();renderTimerMode();newScramble();renderHistory();

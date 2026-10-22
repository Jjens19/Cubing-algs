// Timing uses a monotonic clock; stopping Space never arms the next solve.
let practicePool=[],practiceCase=null,practiceState='loading';
let practiceHeld=false,practiceStart=0,practiceFrame=0,practiceSession=0,solveCount=0;
let lastPracticeSolve=null,dnfSaving=false;
const seconds=ms=>(ms/1000).toFixed(2);
async function nextPracticeCase(){
  const alternatives=practicePool.filter(item=>item.id!==practiceCase?.id);
  const choices=alternatives.length?alternatives:practicePool;
  const chosen=choices[Math.floor(Math.random()*choices.length)];
  const session=practiceSession;
  practiceState='loading';
  $('practice-scramble').textContent='Generating a new scramble…';
  $('practice-instruction').textContent='Preparing the next case…';
  try{
    const {setup}=await api('practice-scramble',{algorithm:chosen.algorithm});
    if(session!==practiceSession)return;
    practiceCase=chosen;
    $('practice-scramble').textContent=setup;
    practiceState='ready';
    $('practice-instruction').textContent='Press and release Space to start.';
  }catch(error){
    if(session!==practiceSession)return;
    practiceState='empty';
    $('practice-scramble').textContent='Could not generate a practice scramble.';
    $('practice-instruction').textContent=error.message==='Not found'?'Restart the Python app to enable the new practice scrambler.':error.message;
  }
}

function practiceTick(){
  if(practiceState!=='running')return;
  $('practice-time').textContent=seconds(performance.now()-practiceStart);
  practiceFrame=requestAnimationFrame(practiceTick);
}

function closePractice(){
  practiceSession++;
  cancelAnimationFrame(practiceFrame);
  practiceState='closed';practiceHeld=false;
  $('practice-time').classList.remove('armed');
  $('practice').close();
}

$('start-practice').onclick=async()=>{
  const selected=visibleCases.filter(c=>(c.learning||c.learned)&&c.algorithm.trim());
  const session=++practiceSession;
  practiceState='loading';practiceHeld=false;practiceCase=null;solveCount=0;lastPracticeSolve=null;$('practice-dnf').disabled=true;
  $('practice-title').textContent='Practice · '+set;
  $('practice-scope').textContent=$('progress-scope').textContent;
  $('practice-time').textContent='0.00';
  $('practice-time').classList.remove('armed');
  $('practice-last').textContent='No solves yet.';$('practice-promotion').textContent='';
  $('practice-scramble').textContent='Loading scrambles…';
  $('practice-instruction').textContent='Preparing your selected cases…';
  $('practice').showModal();
  const results=await Promise.all(selected.map(async c=>{
    try{const {setup}=await api('inverse',{algorithm:c.algorithm});return setup?{id:c.id,name:c.name,algorithm:c.algorithm}:null;}
    catch{return null;}
  }));
  if(session!==practiceSession)return;
  practicePool=results.filter(Boolean);
  if(!practicePool.length){
    practiceState='empty';
    $('practice-scramble').textContent='No usable algorithms in this selection.';
    $('practice-instruction').textContent='Mark cases as Learning or Learned, add valid algorithms, or change your filters.';
    return;
  }
  $('practice-scope').textContent+=` · ${practicePool.length} practice cases`+(visibleCases.length!==practicePool.length?' (not learned, blank or unsupported cases skipped)':'');
  nextPracticeCase();
};

document.addEventListener('keydown',event=>{
  if(!$('practice').open)return;
  if(practiceState!=='running'&&event.code!=='Space')return;
  event.preventDefault();
  if(dnfSaving||event.repeat||practiceHeld||!['ready','stopped','running'].includes(practiceState))return;
  practiceHeld=event.code==='Space';
  if(practiceState==='running'){
    const elapsed=performance.now()-practiceStart;
    practiceState='stopped';cancelAnimationFrame(practiceFrame);
    $('practice-time').textContent=seconds(elapsed);
    solveCount++;
    $('practice-last').textContent=`Solve ${solveCount}: ${seconds(elapsed)} s · ${practiceCase.name}`;
    const record={case:practiceCase,elapsed,session:practiceSession,solve:solveCount,dnf:false};
    lastPracticeSolve=record;
    record.saved=savePracticeResult(practiceCase,elapsed,practiceSession,solveCount);
    $('practice-dnf').disabled=false;
    nextPracticeCase();

  }else{
    practiceState='armed';
    $('practice-time').classList.add('armed');
    $('practice-instruction').textContent='Release Space to start.';
  }
},true);

document.addEventListener('keyup',event=>{
  if(!$('practice').open||event.code!=='Space')return;
  event.preventDefault();
  if(!practiceHeld)return;
  practiceHeld=false;
  if(practiceState==='armed'){
    practiceState='running';practiceStart=performance.now();lastPracticeSolve=null;$('practice-dnf').disabled=true;
    $('practice-time').classList.remove('armed');
    $('practice-instruction').textContent='Solving… Press any key to stop.';
    practiceTick();
  }
},true);

window.addEventListener('blur',()=>{
  practiceHeld=false;
  if(practiceState==='armed'){
    practiceState='ready';$('practice-time').classList.remove('armed');
    $('practice-instruction').textContent='Press and release Space to start.';
  }
});
$('close-practice').onclick=closePractice;
$('practice').addEventListener('cancel',event=>{event.preventDefault();closePractice();});

async function savePracticeResult(solved,elapsed,session,solve){
  $('practice-promotion').textContent='';
  try{
    const result=await api('practice-result',{id:solved.id,elapsed_ms:elapsed});
    if(result.promoted){
      const c=library.cases.find(c=>c.id===solved.id);
      if(c){c.learned=1;c.learning=0;render();}
      if(session===practiceSession&&solve===solveCount)$('practice-promotion').textContent=`${solved.name} is now Learned — under 3 seconds!`;
    }
  }catch(error){
    if(session===practiceSession&&solve===solveCount)$('practice-promotion').textContent='Could not save practice progress: '+error.message;
  }
}

$('practice-dnf').onclick=async()=>{
  const record=lastPracticeSolve;
  if(!record||record.dnf||dnfSaving)return;
  dnfSaving=true;$('practice-dnf').disabled=true;
  try{
    // Wait for any under-three-second promotion before overriding it with DNF.
    await record.saved;
    const result=await api('progress',{id:record.case.id,state:'learning'});
    record.dnf=true;
    const c=library.cases.find(c=>c.id===record.case.id);
    if(c){Object.assign(c,result);render();}
    if(record.session===practiceSession&&record===lastPracticeSolve){
      $('practice-time').textContent='DNF';
      $('practice-last').textContent=`Solve ${record.solve}: DNF (${seconds(record.elapsed)} s) · ${record.case.name}`;
      $('practice-promotion').textContent=`${record.case.name} marked as Learning.`;
    }
  }catch(error){
    if(record.session===practiceSession&&record===lastPracticeSolve){
      $('practice-promotion').textContent='Could not save DNF: '+error.message;
      $('practice-dnf').disabled=false;
    }
  }finally{dnfSaving=false;}
};

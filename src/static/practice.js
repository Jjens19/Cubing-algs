// Timing uses a monotonic clock; stopping Space never arms the next solve.
let practicePool=[],practiceCase=null,practiceState='loading';
let practiceHeld=false,practiceStart=0,practiceFrame=0,practiceSession=0,solveCount=0;
const seconds=ms=>(ms/1000).toFixed(2);
function practiceScramble(setup){
  const replacements={y:'U',"y'":"U'",y2:'U2',"y2'":'U2'};
  return setup.split(/\s+/).map(move=>replacements[move]||move).join(' ');
}

function nextPracticeCase(){
  const alternatives=practicePool.filter(item=>item.id!==practiceCase?.id);
  const choices=alternatives.length?alternatives:practicePool;
  practiceCase=choices[Math.floor(Math.random()*choices.length)];
  $('practice-scramble').textContent=practiceCase.setup;
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
  practiceState='loading';practiceHeld=false;practiceCase=null;solveCount=0;
  $('practice-title').textContent='Practice · '+set;
  $('practice-scope').textContent=$('progress-scope').textContent;
  $('practice-time').textContent='0.00';
  $('practice-time').classList.remove('armed');
  $('practice-last').textContent='No solves yet.';$('practice-promotion').textContent='';
  $('practice-scramble').textContent='Loading scrambles…';
  $('practice-instruction').textContent='Preparing your selected cases…';
  $('practice').showModal();
  const results=await Promise.all(selected.map(async c=>{
    try{const {setup}=await api('inverse',{algorithm:c.algorithm});return setup?{id:c.id,name:c.name,setup:practiceScramble(setup)}:null;}
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
  nextPracticeCase();practiceState='ready';
  $('practice-instruction').textContent='Press and release Space to start.';
};

document.addEventListener('keydown',event=>{
  if(!$('practice').open||event.code!=='Space')return;
  event.preventDefault();
  if(event.repeat||practiceHeld||!['ready','stopped','running'].includes(practiceState))return;
  practiceHeld=true;
  if(practiceState==='running'){
    const elapsed=performance.now()-practiceStart;
    practiceState='stopped';cancelAnimationFrame(practiceFrame);
    $('practice-time').textContent=seconds(elapsed);
    solveCount++;
    $('practice-last').textContent=`Solve ${solveCount}: ${seconds(elapsed)} s · ${practiceCase.name}`;
    savePracticeResult(practiceCase,elapsed,practiceSession,solveCount);
    nextPracticeCase();
    $('practice-instruction').textContent='Next scramble is ready. Press and release Space for your next solve.';
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
    practiceState='running';practiceStart=performance.now();
    $('practice-time').classList.remove('armed');
    $('practice-instruction').textContent='Solving… Press Space to stop.';
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

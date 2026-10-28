// Facelets use the same URFDLB coordinate system as the server and GAN library.
const CubeFacelets=(()=>{
  const faces='URFDLB',solved=[...faces].map(face=>face.repeat(9)).join('');
  const geometry=[];
  for(const face of faces)for(let row=0;row<3;row++)for(let col=0;col<3;col++){
    const a=col-1,b=1-row;
    const values={U:[[a,1,-b],[0,1,0]],R:[[1,b,-a],[1,0,0]],F:[[a,b,1],[0,0,1]],D:[[a,-1,b],[0,-1,0]],L:[[-1,b,a],[-1,0,0]],B:[[-a,b,-1],[0,0,-1]]};
    geometry.push(values[face]);
  }
  const key=([p,n])=>p.join(',')+'|'+n.join(',');
  const index=new Map(geometry.map((value,i)=>[key(value),i]));
  const rotate=([x,y,z],axis)=>[[x,-z,y],[z,y,-x],[-y,x,z]][axis];
  const permutations={};
  for(const face of faces){
    const [axis,layer,sign]={R:[0,1,-1],L:[0,-1,1],U:[1,1,-1],D:[1,-1,1],F:[2,1,-1],B:[2,-1,1]}[face];
    permutations[face]=geometry.map(([p,n],i)=>{
      if(p[axis]!==layer)return i;
      for(let turn=0;turn<(sign+4)%4;turn++){p=rotate(p,axis);n=rotate(n,axis);}
      return index.get(key([p,n]));
    });
  }
  function apply(state,algorithm){
    let result=[...state];
    for(const move of algorithm.trim().split(/\s+/).filter(Boolean)){
      if(!/^[URFDLB](?:2|')?$/.test(move))throw Error('Unsupported cube move: '+move);
      const turns=move.endsWith('2')?2:move.endsWith("'")?3:1;
      for(let t=0;t<turns;t++){const next=result.slice();permutations[move[0]].forEach((dest,source)=>{next[dest]=result[source];});result=next;}
    }
    return result.join('');
  }
  return {solved,apply,geometry,faces};
})();

// Use one clock for a whole solve. Recovered GAN moves may lack timestamps.
const BluetoothMoveTiming={
  interpolate(values,duration){
    const times=values.slice();let estimated=false;
    if(times.length===1)return {times:[0],estimated:values[0]!==0};
    times[0]=0;times[times.length-1]=duration;
    let next=duration;
    for(let i=times.length-2;i>0;i--){
      if(!Number.isFinite(times[i])||times[i]<0||times[i]>next){times[i]=null;estimated=true;}
      else next=times[i];
    }
    let left=0;
    for(let right=1;right<times.length;right++){
      if(times[right]===null)continue;
      for(let i=left+1;i<right;i++)times[i]=times[left]+(times[right]-times[left])*(i-left)/(right-left);
      left=right;
    }
    if(values.some((value,i)=>!Number.isFinite(value)||Math.abs(value-times[i])>.001))estimated=true;
    return {times,estimated};
  },
  fromMoves(moves){
    let offset=0,previous=null;
    const cube=moves.map(move=>{
      const value=move.cubeTimestamp;
      if(!Number.isFinite(value))return null;
      if(previous!==null&&value+offset<previous-0x80000000)offset+=0x100000000;
      const unwrapped=value+offset;
      if(previous!==null&&unwrapped<previous)return null;
      previous=unwrapped;return unwrapped;
    });
    const cubeClock=Number.isFinite(cube[0])&&Number.isFinite(cube.at(-1));
    const values=cubeClock?cube:moves.map(move=>Number.isFinite(move.localTimestamp)?move.localTimestamp:null);
    const start=values[0]??moves[0].receivedTimestamp;
    const end=values.at(-1)??moves.at(-1).receivedTimestamp;
    const duration=Math.max(0,end-start);
    const relative=values.map(value=>value===null?null:value-start);
    const fitted=this.interpolate(relative,duration);
    return {ms:duration,clock:cubeClock?'cube':'host',estimated:fitted.estimated,
      moves:moves.map((move,i)=>({...move,ms:fitted.times[i]}))};
  }
};

class BluetoothSolveTimer{
  constructor(callbacks={},clock={now:()=>performance.now(),later:(fn,ms)=>setTimeout(fn,ms),clear:id=>clearTimeout(id)}){
    this.callbacks=callbacks;this.clock=clock;this.enabled=false;this.phase='waiting';
    this.rotation=new CubeRotationTracker();this.facelets=null;this.serial=null;this.snapshot=null;this.target=null;this.lastMove=null;this.lastFinish=null;this.pending=null;
  }
  configure(enabled,scramble){
    this.abort();this.enabled=enabled;
    this.target=scramble?CubeFacelets.apply(CubeFacelets.solved,scramble):null;
    this.checkReady();
  }
  abort(){
    if(this.pending)this.finish();
    this.phase='waiting';this.startMove=null;this.rotation.end();
    this.callbacks.cancel?.();
  }
  reset(){this.abort();this.rotation.reset();this.facelets=null;this.serial=null;this.snapshot=null;this.lastMove=null;}
  checkReady(){
    if(!this.enabled||!this.target||this.phase==='running'||this.phase==='settling')return;
    if(this.facelets===this.target){
      if(this.phase!=='ready'){this.phase='ready';this.callbacks.ready?.();}
    }else if(this.phase==='ready'){this.phase='waiting';this.callbacks.wait?.();}
  }
  elapsed(first,last){
    if(Number.isFinite(first?.cube)&&Number.isFinite(last?.cube)&&last.cube>=first.cube)return last.cube-first.cube;
    return Math.max(0,(last?.host??this.clock.now())-(first?.host??this.clock.now()));
  }
  event(event){
    if(event.type==='GYRO'){this.rotation.update(event.quaternion,Number.isFinite(event.timestamp)?event.timestamp:this.clock.now(),this.recording?.length||0);return;}
    if(!this.enabled&&this.phase==='ready'){this.phase='waiting';this.callbacks.wait?.();}
    if(event.type==='MOVE'){
      const serial=Number.isInteger(event.serial)?event.serial&255:null;
      if(serial!==null&&this.serial!==null){
        const difference=(serial-this.serial+256)%256;
        if(difference===0||difference>128)return; // Duplicate or stale packet.
        if(difference!==1){this.facelets=null;this.abort();}
      }
      const received=this.clock.now();
      const at={host:Number.isFinite(event.localTimestamp)?event.localTimestamp:received,local:Number.isFinite(event.localTimestamp)?event.localTimestamp:null,received,cube:Number.isFinite(event.cubeTimestamp)?event.cubeTimestamp:null};
      if(this.lastFinish){
        const stop=this.lastFinish.at;
        const delta=Number.isFinite(stop.cube)&&Number.isFinite(at.cube)?at.cube-stop.cube:at.host-stop.host;
        if(delta>=0&&delta<=300&&this.lastFinish.result.penalty!=='+2'){
          this.lastFinish.result.penalty='+2';this.callbacks.penalty?.(this.lastFinish.result);
        }
      }
      if(this.enabled&&this.phase==='ready'&&this.facelets===this.target){
        this.phase='running';this.startMove=at;this.recording=[];this.rotation.begin(at.host);this.initialFacelets=this.facelets;this.callbacks.start?.();
      }
      this.lastMove=at;this.serial=serial;
      if(this.facelets)this.facelets=CubeFacelets.apply(this.facelets,event.move);
      if(this.snapshot&&serial===this.snapshot.serial){
        this.facelets=this.snapshot.facelets;this.snapshot=null;
      }
      if(this.phase==='running')this.recording.push({move:event.move,displayMove:this.rotation.faceMove(event.move,at.host,this.recording.length),cubeTimestamp:at.cube,localTimestamp:at.local,receivedTimestamp:at.received});
      this.checkSolved(at);this.checkReady();
    }else if(event.type==='FACELETS'){
      if(typeof event.facelets!=='string'||!/^[URFDLB]{54}$/.test(event.facelets))return;
      const serial=Number.isInteger(event.serial)?event.serial&255:null;
      if(serial!==null&&this.serial!==null&&(serial-this.serial+256)%256>128)return;
      // State replies can overtake the matching MOVE notifications. Keep timing
      // from the ordered move stream, and apply the snapshot when it catches up.
      if(['ready','running','settling'].includes(this.phase)){
        if(serial===null||this.serial===null)return;
        if(serial!==this.serial){
          if(!this.snapshot||(serial-this.snapshot.serial+256)%256<128)this.snapshot={serial,facelets:event.facelets};
          return;
        }
      }
      this.facelets=event.facelets;this.serial=serial;
      this.checkSolved(this.lastMove);this.checkReady();
    }
  }
  checkSolved(at){
    if(!this.enabled||this.phase!=='running'||this.facelets!==CubeFacelets.solved)return;
    const timing=BluetoothMoveTiming.fromMoves(this.recording);
    const result={ms:timing.ms,penalty:'OK',trace:{initialFacelets:this.initialFacelets,moves:timing.moves,timingEstimated:timing.estimated,clock:timing.clock,gyroAvailable:!!this.rotation.baseline&&this.rotation.samples>0,rotations:this.rotation.timedEvents(this.recording,timing.ms)}};
    this.rotation.end();
    this.phase='settling';this.lastFinish={result,at:at||{host:this.clock.now(),cube:null}};
    this.pending=this.clock.later(()=>this.finish(),500);
    this.callbacks.stop?.(result);
  }
  finish(){
    if(!this.pending)return;
    this.clock.clear(this.pending);this.pending=null;this.phase='waiting';
    this.callbacks.finish?.(this.lastFinish.result);
  }
}

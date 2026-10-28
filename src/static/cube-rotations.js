// GAN gyro axes: +X red, +Y blue, +Z white. Convert to the URFDLB frame.
class CubeRotationTracker{
  static multiply(a,b){return {w:a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z,x:a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,y:a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,z:a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w};}
  static inverse(q){return {w:q.w,x:-q.x,y:-q.y,z:-q.z};}
  static rotate(q,v){const p=this.multiply(this.multiply(q,{w:0,x:v[0],y:v[1],z:v[2]}),this.inverse(q));return [p.x,p.y,p.z];}
  static distance(a,b){return 2*Math.acos(Math.min(1,Math.abs(a.w*b.w+a.x*b.x+a.y*b.y+a.z*b.z)));}
  static key(q){return [[1,0,0],[0,1,0],[0,0,1]].flatMap(v=>this.rotate(q,v).map(Math.round)).join(',');}
  constructor(){
    this.identity={w:1,x:0,y:0,z:0};this.orientations=[{q:this.identity,path:[]}];
    const turns=[];
    for(const axis of ['x','y','z'])for(const [suffix,angle] of [['',-Math.PI/2],["'",Math.PI/2],['2',Math.PI]]){
      const q={w:Math.cos(angle/2),x:0,y:0,z:0};q[axis]=Math.sin(angle/2);turns.push({q,move:axis+suffix});
    }
    const seen=new Set([CubeRotationTracker.key(this.identity)]);
    for(let i=0;i<this.orientations.length;i++)for(const turn of turns){
      const item=this.orientations[i],q=CubeRotationTracker.multiply(item.q,turn.q),key=CubeRotationTracker.key(q);
      if(!seen.has(key)){seen.add(key);this.orientations.push({q,path:[...item.path,turn.move]});}
    }
    this.latest=null;this.active=false;this.events=[];this.orientation=this.identity;this.pending=null;
  }
  nearest(q){return this.orientations.reduce((best,item)=>CubeRotationTracker.distance(item.q,q)<CubeRotationTracker.distance(best.q,q)?item:best);}
  startingOrientation(time){
    // Keep the canonical URFDLB frame instead of treating the first pose as identity.
    this.baseline=this.identity;
    const start=this.nearest(this.latest);
    this.orientation=start.q;
    for(const move of start.path)this.events.push({move,localTimestamp:time,afterMoveIndex:0,ms:0,initial:true});
  }
  begin(time=0){this.active=true;this.baseline=null;this.events=[];this.samples=0;this.orientation=this.identity;this.pending=null;if(this.latest)this.startingOrientation(time);}
  end(){this.active=false;}
  reset(){this.end();this.latest=null;this.events=[];this.pending=null;}
  update(value,time,afterMoveIndex){
    if(!value||!['w','x','y','z'].every(key=>Number.isFinite(value[key])))return;
    const length=Math.hypot(value.w,value.x,value.y,value.z);if(length<.5)return;
    this.latest={w:value.w/length,x:value.x/length,y:value.z/length,z:-value.y/length};
    if(!this.active)return;
    this.samples++;
    if(!this.baseline){this.startingOrientation(time);return;}
    const relative=CubeRotationTracker.multiply(CubeRotationTracker.inverse(this.baseline),this.latest);
    const nearest=this.orientations.reduce((best,item)=>CubeRotationTracker.distance(item.q,relative)<CubeRotationTracker.distance(best.q,relative)?item:best);
    if(CubeRotationTracker.distance(nearest.q,relative)>Math.PI/9){this.pending=null;return;}
    if(CubeRotationTracker.distance(nearest.q,this.orientation)<.01){this.pending=null;return;}
    const key=CubeRotationTracker.key(nearest.q);
    if(this.pending?.key!==key)this.pending={key,q:nearest.q,since:time,time};
    else this.pending.time=time;
    if(time-this.pending.since>=40)this.commit(time,afterMoveIndex);
  }
  commit(time,afterMoveIndex){
    if(!this.pending)return;
    const delta=CubeRotationTracker.multiply(CubeRotationTracker.inverse(this.orientation),this.pending.q);
    const transition=this.orientations.reduce((best,item)=>CubeRotationTracker.distance(item.q,delta)<CubeRotationTracker.distance(best.q,delta)?item:best);
    for(const move of transition.path)this.events.push({move,localTimestamp:time,afterMoveIndex});
    this.orientation=this.pending.q;this.pending=null;
  }
  faceMove(move,time,index){
    this.commit(time,index);
    const normals={U:[0,1,0],R:[1,0,0],F:[0,0,1],D:[0,-1,0],L:[-1,0,0],B:[0,0,-1]};
    const vector=CubeRotationTracker.rotate(this.orientation,normals[move[0]]);
    const face=Object.keys(normals).find(face=>normals[face].every((value,i)=>value===Math.round(vector[i])));
    return (face||move[0])+move.slice(1);
  }
  timedEvents(moves,duration){
    const first=moves[0],last=moves.at(-1),start=first.localTimestamp??first.receivedTimestamp,end=last.localTimestamp??last.receivedTimestamp;
    return this.events.map(event=>({...event,ms:event.initial?0:Math.max(0,Math.min(duration,end>start?(event.localTimestamp-start)*duration/(end-start):0))}));
  }
}

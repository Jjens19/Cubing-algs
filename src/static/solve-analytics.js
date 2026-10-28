// Infer method milestones from actual replayed states; equivalent methods remain ambiguous.
const SolveAnalytics=(()=>{
  const {geometry,faces,solved,apply}=CubeFacelets;
  const dot=(a,b)=>a.reduce((sum,value,i)=>sum+value*b[i],0);
  const magnitude=vector=>vector.reduce((sum,value)=>sum+Math.abs(value),0);
  const indices=predicate=>geometry.flatMap(([position,normal],i)=>predicate(position,normal)?[i]:[]);
  const exact=(state,stickers)=>stickers.every(i=>state[i]===solved[i]);
  function analyzeTrace(solve){
    const selected=['CFOP','CFCE','Roux'].includes(solve.analyticsMethod)?solve.analyticsMethod:null;
    const trace=solve.trace;
    if(!trace||typeof trace.initialFacelets!=='string'||!/^[URFDLB]{54}$/.test(trace.initialFacelets)||!Array.isArray(trace.moves)||!trace.moves.length){
      return {method:'Unavailable',note:'This solve has no recorded move history. Step analytics are available for new Bluetooth solves.',rows:[],moves:[]};
    }
    let state=trace.initialFacelets,previous=0;
    const states=[state],moves=[];
    for(const item of trace.moves){
      if(!item||typeof item.move!=='string'||!Number.isFinite(item.ms)||item.ms<previous||item.ms>solve.ms+1){
        return {method:'Unavailable',note:'The recorded move timing is incomplete; step times cannot be reconstructed reliably.',rows:[],moves:trace.moves.filter(move=>move&&typeof move.move==='string')};
      }
      try{state=apply(state,item.move);}catch{return {method:'Unavailable',note:'The move history contains an unsupported move.',rows:[],moves:[]};}
      previous=item.ms;states.push(state);moves.push(item);
    }
    const total=moves.length,time=index=>index===0?0:moves[index-1].ms;
    if(state!==solved)return {method:'Uncertain',note:'The recorded moves do not reconstruct a solved cube. Step times are unavailable.',rows:[],moves};
    const first=(predicate,start=0)=>{for(let i=start;i<states.length;i++)if(predicate(states[i]))return i;return total;};
    const rows=[];
    function row(name,start,end,extra={}){return {name,ms:Math.max(0,time(end)-time(start)),endMs:time(end),startIndex:start,endIndex:end,moves:moves.slice(start,end).map(item=>item.move),timedMoves:moves.slice(start,end),...extra};}
    const layers=Array.from(faces,(bottom,bottomIndex)=>{
      const down=geometry[bottomIndex*9+4][1],topIndex=geometry.findIndex(([,normal])=>dot(normal,down)===-1),top=faces[Math.floor(topIndex/9)];
      const cross=indices(position=>dot(position,down)===1&&magnitude(position)===2);
      const corners=indices(position=>dot(position,down)===-1&&magnitude(position)===3);
      const topFace=indices((_,normal)=>dot(normal,down)===-1);
      const crossSolved=state=>exact(state,cross);
      const slots=geometry.filter(([position])=>dot(position,down)===1&&magnitude(position)===3)
        .map(([position])=>position).filter((position,i,list)=>list.findIndex(p=>p.join()===position.join())===i).map(corner=>{
          const edge=corner.map((value,i)=>value-down[i]);
          const stickers=indices(position=>position.join()===corner.join()||position.join()===edge.join());
          const label=Array.from(faces).filter((face,i)=>dot(geometry[i*9+4][1],down)===0&&dot(geometry[i*9+4][1],corner)===1).join('');
          return {label,solved:state=>exact(state,stickers)};
        });
      const f2l=state=>crossSolved(state)&&slots.every(slot=>slot.solved(state));
      const cornersSolved=state=>['',top,top+'2',top+"'"].some(move=>exact(move?apply(state,move):state,corners));
      const oriented=state=>topFace.every(i=>state[i]===top);
      const f2lEnd=first(f2l),crossEnd=first(crossSolved),ollEnd=first(state=>f2l(state)&&oriented(state),f2lEnd),cornersEnd=first(state=>f2l(state)&&cornersSolved(state),f2lEnd);
      return {bottom,down,top,crossSolved,slots,f2l,cornersSolved,oriented,f2lEnd,crossEnd,ollEnd,cornersEnd};
    });
    const blocks=[];
    for(const layer of layers)for(let side=0;side<6;side++){
      const normal=geometry[side*9+4][1];
      if(dot(normal,layer.down)!==0)continue;
      const opposite=geometry.findIndex(([,n])=>dot(n,normal)===-1),other=faces[Math.floor(opposite/9)];
      if(faces[side]>other)continue;
      const left=indices(position=>dot(position,normal)===1&&dot(position,layer.down)>=0);
      const right=indices(position=>dot(position,normal)===-1&&dot(position,layer.down)>=0);
      const both=state=>exact(state,left)&&exact(state,right),end=first(both);
      const cmll=first(state=>both(state)&&layer.cornersSolved(state),end);
      // The remaining M-slice edges distinguish a Roux finish from solved F2L.
      if(selected==='Roux'||(end<layer.f2lEnd&&end<total&&cmll<total))blocks.push({layer,left,right,end,cmll,side:faces[side],other});
    }
    if(blocks.length&&(!selected||selected==='Roux')){
      blocks.sort((a,b)=>a.end-b.end||a.cmll-b.cmll);
      const block=blocks[0];
      const completion=stickers=>{let lastFalse=-1;for(let i=0;i<=block.end;i++)if(!exact(states[i],stickers))lastFalse=i;return lastFalse+1;};
      const leftEnd=completion(block.left),rightEnd=completion(block.right),firstEnd=Math.min(leftEnd,rightEnd);
      rows.push(row('First block ('+(leftEnd<=rightEnd?block.side:block.other)+')',0,firstEnd),row('Second block',firstEnd,block.end),row('CMLL',block.end,block.cmll),row('LSE',block.cmll,total));
      return {method:'Roux',note:selected?'Roux selected manually. Splits use detected block and corner completion; skipped stages can have zero duration.':'Inferred from two opposite 1×2×3 blocks, solved corners, and a last-six-edges finish.',rows,moves,bottom:block.layer.bottom};
    }
    layers.sort((a,b)=>a.f2lEnd-b.f2lEnd||a.crossEnd-b.crossEnd);
    const layer=layers[0];
    if(layer.f2lEnd===total&&!selected)return {method:'Unclassified',note:'No distinct CFOP, CFCE, or Roux stages could be identified from this move sequence.',rows:[row('Full solution',0,total)],moves};
    const crossEnd=Math.min(layer.crossEnd,layer.f2lEnd);
    rows.push(row('Cross ('+layer.bottom+')',0,crossEnd),row('F2L — combined',crossEnd,layer.f2lEnd,{group:true}));
    const pairs=layer.slots.map(slot=>{
      let lastUnsolved=crossEnd-1;
      for(let i=crossEnd;i<=layer.f2lEnd;i++)if(layer.crossSolved(states[i])&&!slot.solved(states[i]))lastUnsolved=i;
      let end=Math.max(crossEnd,lastUnsolved+1);
      while(end<layer.f2lEnd&&(!layer.crossSolved(states[end])||!slot.solved(states[end])))end++;
      return {label:slot.label,end};
    }).sort((a,b)=>a.end-b.end);
    let previousPair=crossEnd;
    pairs.forEach((pair,i)=>{rows.push(row('Pair '+(i+1)+' · '+pair.label,previousPair,pair.end,{child:true}));previousPair=pair.end;});
    let method,note;
    if(selected==='CFCE'||(!selected&&layer.cornersEnd<layer.ollEnd&&layer.cornersEnd>layer.f2lEnd)){
      method='CFCE';note='Inferred from F2L, solved last-layer corners, then the remaining edges.';
      rows.push(row('CLL',layer.f2lEnd,layer.cornersEnd),row('ELL',layer.cornersEnd,total));
    }else if(selected==='CFOP'||(!selected&&layer.ollEnd<layer.cornersEnd&&layer.ollEnd>layer.f2lEnd)){
      method='CFOP';note='Inferred from cross/F2L, last-layer orientation, then permutation.';
      rows.push(row('OLL',layer.f2lEnd,layer.ollEnd),row('PLL',layer.ollEnd,total));
    }else{
      method='CFOP / CFCE';note='Ambiguous: this finish, including possible skipped steps, fits both methods. OLL/PLL or CLL/ELL cannot be separated reliably.';
      rows.push(row('Last layer',layer.f2lEnd,total));
    }
    if(selected)note=selected+' selected manually. Splits use detected cube-state milestones; skipped or combined stages can have zero duration.';
    return {method,note,rows,moves,bottom:layer.bottom};
  }
  function solutionMoves(solve,moves,start=0,end=moves.length){
    const rotations=Array.isArray(solve.trace?.rotations)?solve.trace.rotations.filter(item=>item&&/^[xyz](?:2|')?$/.test(item.move)&&Number.isInteger(item.afterMoveIndex)&&Number.isFinite(item.ms)):[];
    const result=[];
    for(let i=start;i<end;i++){
      for(const rotation of rotations)if(rotation.afterMoveIndex===i)result.push({...rotation,rotation:true});
      const item=moves[i];result.push({...item,move:/^[URFDLB](?:2|')?$/.test(item.displayMove||'')?item.displayMove:item.move});
    }
    return result;
  }
  function groupMoves(moves){
    const groups=[];
    moves.forEach((item,index)=>{
      const previous=groups.at(-1),gap=previous?item.ms-previous.endMs:Infinity;
      if(previous&&previous.originalMove===item.move&&Number.isFinite(item.ms)&&Number.isFinite(previous.endMs)&&gap>=0&&gap<=200){
        previous.count++;previous.endMs=item.ms;previous.lastIndex=index;
        const match=/^([URFDLBxyz])(\d+)?('?)$/.exec(item.move);
        previous.move=match?match[1]+(Number(match[2]||1)*previous.count)+match[3]:Array(previous.count).fill(item.move).join(' ');
      }else groups.push({move:item.move,originalMove:item.move,rotation:!!item.rotation,count:1,startMs:item.ms,endMs:item.ms,firstIndex:index,lastIndex:index});
    });
    return groups;
  }
  function analyze(solve){
    let prepared=solve;
    const trace=solve.trace;
    if(Array.isArray(trace?.moves)&&trace.moves.length&&Number.isFinite(solve.ms)&&solve.ms>=0&&trace.moves.every(move=>move&&typeof move.move==='string')){
      const values=trace.moves.map(move=>move.ms);
      const invalid=values.some((value,i)=>!Number.isFinite(value)||value<0||value>solve.ms+1||(i>0&&value<values[i-1]));
      if(invalid&&values.some(Number.isFinite)){
        const timing=BluetoothMoveTiming.interpolate(values,solve.ms);
        prepared={...solve,trace:{...trace,timingEstimated:true,moves:trace.moves.map((move,i)=>({...move,ms:timing.times[i]}))}};
      }
    }
    let analysis=analyzeTrace(prepared);
    if(prepared.trace?.timingEstimated)analysis={...analysis,note:analysis.note+' Some move timestamps were interpolated; step times are estimates.',timingEstimated:true};
    const selected=['CFOP','CFCE','Roux'].includes(solve.analyticsMethod)?solve.analyticsMethod:null;
    if(selected&&analysis.method!==selected){
      return {...analysis,method:selected,note:selected+' selected manually. '+analysis.note};
    }
    return analysis;
  }
  return {analyze,groupMoves,solutionMoves};
})();

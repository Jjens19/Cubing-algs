// Track the prescribed scramble separately from solve timing.
class BluetoothScrambleGuide{
  constructor(){this.facelets=null;this.serial=null;this.travel=[];this.travelKnown=false;this.configure('');}
  static append(path,move){
    const face=move[0],turns=move.endsWith('2')?2:move.endsWith("'")?3:1;
    const previous=path.at(-1);
    if(previous?.[0]===face){
      path.pop();const count=(turns+(previous.endsWith('2')?2:previous.endsWith("'")?3:1))%4;
      if(count)path.push(face+(count===2?'2':count===3?"'":''));
    }else path.push(move);
  }
  static inverse(path){return [...path].reverse().map(move=>move.endsWith('2')?move:move.endsWith("'")?move.slice(0,-1):move+"'");}
  configure(scramble){
    this.tokens=scramble.trim().split(/\s+/).filter(Boolean);this.prefix=[CubeFacelets.solved];
    for(const move of this.tokens)this.prefix.push(CubeFacelets.apply(this.prefix.at(-1),move));
    this.index=0;this.wrong=[];this.partial=[];this.unknown=false;
    this.synchronize();
  }
  reset(){this.facelets=null;this.serial=null;this.travel=[];this.travelKnown=false;this.configure(this.tokens.join(' '));}
  synchronize(){
    if(!this.facelets){this.unknown=true;return;}
    const index=this.prefix.lastIndexOf(this.facelets);
    if(index>=0){this.index=index;this.wrong=[];this.partial=[];this.unknown=false;return;}
    this.index=0;this.partial=[];
    if(this.travelKnown){this.wrong=this.travel.slice();this.unknown=false;}
    else{this.wrong=[];this.unknown=true;}
  }
  event(event){
    const serial=Number.isInteger(event.serial)?event.serial&255:null;
    if(event.type==='FACELETS'){
      if(typeof event.facelets!=='string'||!/^[URFDLB]{54}$/.test(event.facelets))return;
      // Do not let a future snapshot skip the ordered move guidance.
      if(this.facelets&&this.serial!==null&&(serial===null||serial!==this.serial))return;
      if(this.facelets===event.facelets)return;
      this.facelets=event.facelets;this.serial=serial;
      this.travel=[];this.travelKnown=this.facelets===CubeFacelets.solved;this.synchronize();
      return;
    }
    if(event.type!=='MOVE')return;
    if(serial!==null&&this.serial!==null){
      const difference=(serial-this.serial+256)%256;
      if(difference===0||difference>128)return;
      if(difference!==1){this.facelets=null;this.travelKnown=false;this.wrong=[];this.unknown=true;}
    }
    this.serial=serial;
    if(!this.facelets)return;
    this.facelets=CubeFacelets.apply(this.facelets,event.move);
    if(this.travelKnown)BluetoothScrambleGuide.append(this.travel,event.move);
    if(this.facelets===CubeFacelets.solved){this.travel=[];this.travelKnown=true;}
    if(this.unknown){this.synchronize();return;}
    // Once the scramble is complete, following turns belong to the solve.
    if(this.index===this.tokens.length)return;
    if(this.wrong.length){
      BluetoothScrambleGuide.append(this.wrong,event.move);
      if(this.facelets===this.prefix[this.index]){this.wrong=[];this.partial=[];}
      return;
    }
    if(this.facelets===this.prefix[this.index+1]){this.index++;this.partial=[];return;}
    if(this.facelets===this.prefix[this.index]){this.partial=[];return;}
    const expected=this.tokens[this.index];
    const quarter=expected?.endsWith('2')?[expected[0],expected[0]+"'"].find(move=>CubeFacelets.apply(this.prefix[this.index],move)===this.facelets):null;
    if(quarter){this.partial=[quarter];return;}
    this.wrong=this.partial.slice();this.partial=[];BluetoothScrambleGuide.append(this.wrong,event.move);
  }
  get undo(){return BluetoothScrambleGuide.inverse(this.wrong);}
}

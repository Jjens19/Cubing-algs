// Sticker geometry and move conventions mirror src/scrambler.py.
const NOTATION_MOVES={
  U:[1,1,-1,'Upper face','Turn the upper layer clockwise when looking directly at the U face.'],
  D:[1,-1,1,'Down face','Turn the bottom layer clockwise when looking directly at the D face.'],
  R:[0,1,-1,'Right face','Turn the right layer clockwise when looking directly at the R face.'],
  L:[0,-1,1,'Left face','Turn the left layer clockwise when looking directly at the L face.'],
  F:[2,1,-1,'Front face','Turn the front layer clockwise when looking directly at the F face.'],
  B:[2,-1,1,'Back face','Turn the back layer clockwise when looking directly at the B face.'],
  M:[0,0,1,'Middle slice','Turn the slice between L and R in the same direction as L. The outer layers stay still.'],
  E:[1,0,1,'Equatorial slice','Turn the slice between U and D in the same direction as D. The outer layers stay still.'],
  S:[2,0,-1,'Standing slice','Turn the slice between F and B in the same direction as F. The outer layers stay still.'],
  x:[0,null,-1,'Whole-cube x rotation','Rotate the entire cube in the same direction as R.'],
  y:[1,null,-1,'Whole-cube y rotation','Rotate the entire cube in the same direction as U.'],
  z:[2,null,-1,'Whole-cube z rotation','Rotate the entire cube in the same direction as F.'],
};
function notationRotate(vector,axis,angle){
  const c=Math.cos(angle),s=Math.sin(angle),[x,y,z]=vector;
  return axis===0?[x,y*c-z*s,y*s+z*c]:axis===1?[x*c+z*s,y,-x*s+z*c]:[x*c-y*s,x*s+y*c,z];
}
function notationGeometry(){
  const stickers=[];
  for(const face of 'URFDLB')for(let row=0;row<3;row++)for(let col=0;col<3;col++){
    const a=col-1,b=1-row;
    const [position,normal]=({U:[[a,1,-b],[0,1,0]],R:[[1,b,-a],[1,0,0]],F:[[a,b,1],[0,0,1]],D:[[a,-1,b],[0,-1,0]],L:[[-1,b,a],[-1,0,0]],B:[[-a,b,-1],[0,0,-1]]})[face];
    const axis=normal.findIndex(n=>n!==0),plane=[0,1,2].filter(i=>i!==axis);
    const center=position.map((v,i)=>i===axis?normal[i]*1.5:v);
    const corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(offset=>center.map((v,i)=>v+(i===plane[0]?offset[0]*.46:i===plane[1]?offset[1]*.46:0)));
    stickers.push({face,position,normal,center,corners,isCenter:row===1&&col===1});
  }
  return stickers;
}
function renderNotationGuide(container){
  const ns='http://www.w3.org/2000/svg';
  const heading=document.createElement('h3');heading.textContent='Reading cube notation';container.append(heading);
  wikiParagraph(container,'Clockwise and counterclockwise are viewed directly from the face being turned. U/D are upper/down, L/R left/right, and F/B front/back. A prime (\u2032) reverses the turn, 2 means a half turn, and 3 means three quarter turns.');
  wikiParagraph(container,'M follows L, E follows D, and S follows F. Lowercase x, y, and z rotate the whole cube like R, U, and F respectively. These are rotations, not single-layer turns.');
  const panel=document.createElement('section');panel.className='notation-guide';panel.setAttribute('aria-label','Interactive cube notation guide');
  function selectControl(labelText,id,values){
    const label=document.createElement('label');label.htmlFor=id;label.textContent=labelText;
    const select=document.createElement('select');select.id=id;
    for(const [value,text] of values){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option);}
    label.append(select);return [label,select];
  }
  const controls=document.createElement('div');controls.className='notation-controls';
  const [moveLabel,move]=selectControl('Move','notation-move',Object.entries(NOTATION_MOVES).map(([key,data])=>[key,key+' — '+data[3]]));
  const [suffixLabel,suffix]=selectControl('Turn','notation-suffix',[['','Quarter turn'],["'",'Prime — reverse'],['2','Half turn'],['3','Three quarter turns']]);
  const [viewLabel,view]=selectControl('View','notation-view',[['auto','Automatic'],['front','Front / right / top'],['back','Back / left / top'],['bottom','Front / right / bottom']]);
  controls.append(moveLabel,suffixLabel,viewLabel);panel.append(controls);
  const description=document.createElement('p');description.id='notation-description';panel.append(description);
  const svg=document.createElementNS(ns,'svg');svg.id='notation-cube';svg.setAttribute('viewBox','0 0 360 300');svg.setAttribute('role','img');svg.setAttribute('aria-describedby','notation-description');panel.append(svg);
  const sliderLabel=document.createElement('label');sliderLabel.htmlFor='notation-progress';sliderLabel.textContent='Turn progress';
  const slider=document.createElement('input');slider.type='range';slider.id='notation-progress';slider.min='0';slider.max='100';slider.value='0';sliderLabel.append(slider);panel.append(sliderLabel);
  const actions=document.createElement('div');actions.className='notation-actions';
  const play=document.createElement('button');play.type='button';play.id='notation-play';play.textContent='▶ Play turn';
  const reset=document.createElement('button');reset.type='button';reset.textContent='Reset';
  const finish=document.createElement('button');finish.type='button';finish.textContent='Show finished turn';
  const status=document.createElement('output');status.id='notation-status';status.setAttribute('aria-live','polite');
  actions.append(play,reset,finish);panel.append(actions,status);
  wikiParagraph(panel,'The moving layer is outlined; the other stickers are dimmed. Face letters identify the original centers. Use the slider to inspect the turn, or change the view to see hidden layers. Animations play only when requested.');
  container.append(panel);
  const geometry=notationGeometry(),colors={U:'#ffff00',D:'#ffffff',L:'#ff0000',R:'#ff9900',F:'#00cc00',B:'#2244ff'};
  let frame=null,playing=false;
  function stop(){if(frame!==null)cancelAnimationFrame(frame);frame=null;playing=false;play.textContent='▶ Play turn';}
  function draw(){
    const [axis,layer,sign,,text]=NOTATION_MOVES[move.value];
    const turns=suffix.value==='2'?2:suffix.value==='3'?3:1;
    const degrees=90*turns*Number(slider.value)/100;
    const angle=sign*(suffix.value==="'"?-1:1)*degrees*Math.PI/180;
    const camera=view.value==='auto'?(move.value==='D'?'bottom':['L','B'].includes(move.value)?'back':'front'):view.value;
    const horizontal=camera==='back'?-1:1,vertical=camera==='bottom'?-1:1;
    const eye=[horizontal,1.3*vertical,horizontal];
    const project=([x,y,z])=>[180+horizontal*(x-z)*47,150+horizontal*(x+z)*21-vertical*y*48];
    const dot=v=>v.reduce((sum,n,i)=>sum+n*eye[i],0);
    const faces=geometry.map(sticker=>{
      const moving=layer===null||sticker.position[axis]===layer;
      const transform=v=>moving?notationRotate(v,axis,angle):v;
      return {...sticker,moving,normal:transform(sticker.normal),center:transform(sticker.center),corners:sticker.corners.map(transform)};
    }).filter(sticker=>dot(sticker.normal)>.001).sort((a,b)=>dot(a.center)-dot(b.center));
    svg.replaceChildren();svg.setAttribute('aria-label',move.value+suffix.value+' at '+Math.round(degrees)+' degrees');
    for(const sticker of faces){
      const polygon=document.createElementNS(ns,'polygon');polygon.setAttribute('points',sticker.corners.map(p=>project(p).join(',')).join(' '));
      polygon.setAttribute('fill',colors[sticker.face]);polygon.setAttribute('stroke',sticker.moving?'#172e26':'#718173');polygon.setAttribute('stroke-width',sticker.moving?'2.5':'1');polygon.setAttribute('opacity',sticker.moving?'1':'.35');polygon.dataset.moving=String(sticker.moving);svg.append(polygon);
      if(sticker.isCenter){const text=document.createElementNS(ns,'text'),[x,y]=project(sticker.center);text.setAttribute('x',x);text.setAttribute('y',y+5);text.setAttribute('text-anchor','middle');text.setAttribute('fill',sticker.face==='B'?'white':'#142d23');text.textContent=sticker.face;svg.append(text);}
    }
    description.textContent=move.value+suffix.value+' — '+text+(suffix.value==="'"?' Reverse that direction.':suffix.value==='2'?' Turn 180°.':suffix.value==='3'?' Turn 270° in the written direction.':'');
    slider.setAttribute('aria-valuetext',Math.round(degrees)+' degrees of '+90*turns);
    if(!playing)status.textContent=move.value+suffix.value+' · '+Math.round(degrees)+'° / '+90*turns+'°';
  }
  play.onclick=()=>{
    if(playing){stop();draw();return;}
    if(Number(slider.value)>=100)slider.value='0';
    playing=true;play.textContent='Pause';status.textContent='Playing '+move.value+suffix.value;
    const start=performance.now(),initial=Number(slider.value);
    function tick(now){if(!panel.isConnected){stop();return;}slider.value=String(Math.min(100,initial+(now-start)/18));draw();if(Number(slider.value)<100)frame=requestAnimationFrame(tick);else{stop();draw();}}
    frame=requestAnimationFrame(tick);
  };
  slider.oninput=()=>{stop();draw();};
  reset.onclick=()=>{stop();slider.value='0';draw();};finish.onclick=()=>{stop();slider.value='100';draw();};
  for(const select of [move,suffix,view])select.onchange=()=>{stop();slider.value='0';draw();};
  draw();
}

// Two complementary isometric views share the same face/index keys as drawings.
function fullCubeNet(container,state,mini=false){
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 250 140');svg.setAttribute('class','cube-diagram full-cube-diagram');svg.setAttribute('aria-label',mini?'Full cube recognition: top/front/right and top/back/left':'Editable upright cube: top and four side faces');
  if(mini)svg.setAttribute('role','img');
  for(const [direction,origin,label] of [[1,65,'U · F · R'],[-1,185,'U · B · L']]){
    const project=([x,y,z])=>[origin+direction*(x-z)*18,62+direction*(x+z)*8-y*20];
    const geometry=notationGeometry();
    for(const [stickerIndex,sticker] of geometry.entries()){
      if(direction*(sticker.normal[0]+sticker.normal[2])+sticker.normal[1]<=0)continue;
      const face=sticker.face,number=stickerIndex%9,key=face+number,value=state[key]||{color:'#aab2a7',highlight:false};
      const polygon=document.createElementNS(ns,'polygon');
      polygon.setAttribute('points',sticker.corners.map(p=>project(p).join(',')).join(' '));polygon.setAttribute('fill',value.color);polygon.setAttribute('stroke','#000');polygon.setAttribute('stroke-width','1');polygon.dataset.key=key;
      if(!mini){
        polygon.setAttribute('class','sticker');polygon.setAttribute('role','button');polygon.setAttribute('tabindex','0');polygon.setAttribute('aria-label',`${face} sticker ${number+1}${value.highlight?', highlighted':''}`);polygon.setAttribute('aria-pressed',String(!!value.highlight));
        const edit=()=>{drawing[key]={color:mode==='paint'?color:value.color,highlight:mode==='highlight'?!value.highlight:value.highlight};dirty=true;net(container,drawing);container.querySelector(`[data-key="${key}"]`)?.focus();};
        polygon.onclick=edit;polygon.onkeydown=event=>{if(event.key==='Enter'||event.code==='Space'){event.preventDefault();edit();}};
      }
      svg.append(polygon);
      if(value.highlight){const star=document.createElementNS(ns,'text'),[x,y]=project(sticker.center);star.setAttribute('x',x);star.setAttribute('y',y);star.setAttribute('class','recognition-star');star.setAttribute('font-size','10');star.textContent='★';svg.append(star);}
    }
    const caption=document.createElementNS(ns,'text');caption.setAttribute('x',origin);caption.setAttribute('y','134');caption.setAttribute('text-anchor','middle');caption.setAttribute('font-size','10');caption.setAttribute('class','full-cube-caption');caption.textContent=label;svg.append(caption);
  }
  container.classList.add('full-cube-view');container.replaceChildren(svg);
}

const $=id=>document.getElementById(id);
let visibleCases=[];
let library={sets:[],cases:[]},set='ELL',category='',current=null,drawing={},mode='paint',color='#ffff00',dirty=false;
// Top view: nine U stickers and three last-layer stickers on each side.
// Keep the original face/index keys so saved colors and highlights still work.
const lastLayer = [
  ...Array.from({length:9},(_,i)=>({key:'U'+i,face:'U',index:i,x:i%3+2,y:Math.floor(i/3)+2,color:'#ffff00'})),
  ...Array.from({length:3},(_,i)=>({key:'B'+(2-i),face:'B',index:2-i,x:i+2,y:1,color:'#0000ff'})),
  ...Array.from({length:3},(_,i)=>({key:'F'+i,face:'F',index:i,x:i+2,y:5,color:'#00ff00'})),
  ...Array.from({length:3},(_,i)=>({key:'L'+i,face:'L',index:i,x:1,y:i+2,color:'#ff0000'})),
  ...Array.from({length:3},(_,i)=>({key:'R'+(2-i),face:'R',index:2-i,x:5,y:i+2,color:'#ff9900'})),
];
// Sample sticker centers from either PNG or SVG last-layer diagrams.
const caseDrawingCache=new Map();
function caseDrawing(image){
  if(!image)return Promise.resolve({});
  if(!caseDrawingCache.has(image)){
    const pending=(async()=>{
      if(image.endsWith('.svg')){
        const response=await fetch(image);
        if(!response.ok)throw Error('Could not load the case image.');
        const doc=new DOMParser().parseFromString(await response.text(),'image/svg+xml');
        const metadata=doc.getElementById('cube-stickers');
        if(metadata){const stickers=JSON.parse(metadata.textContent);if(Object.keys(stickers).length===54)return stickers;}
        const polygons=[...doc.querySelectorAll('polygon[data-key]')];
        if(polygons.length===54){
          const stickers={};
          for(const polygon of polygons){const key=polygon.getAttribute('data-key');if(/^[URFDLB][0-8]$/.test(key))stickers[key]={color:polygon.getAttribute('fill'),highlight:false};}
          if(Object.keys(stickers).length===54)return stickers;
        }
      }
      return new Promise((resolve,reject)=>{
      const img=new Image();
      img.onload=()=>{
        try{
          const canvas=document.createElement('canvas');
          canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
          const ctx=canvas.getContext('2d',{willReadFrequently:true});
          ctx.drawImage(img,0,0,canvas.width,canvas.height);
          const centers=[.08,.27,.5,.73,.92];
          const stickers={};
          for(const {key,x,y} of lastLayer){
            const [r,g,b]=ctx.getImageData(Math.floor(centers[x-1]*canvas.width),Math.floor(centers[y-1]*canvas.height),1,1).data;
            stickers[key]={color:'#'+[r,g,b].map(v=>v.toString(16).padStart(2,'0')).join(''),highlight:false};
          }
          resolve(stickers);
        }catch(error){reject(error);}
      };
      img.onerror=()=>reject(Error('Could not load the case image for the recognition drawing.'));
      img.src=image;
    });
    })();
    caseDrawingCache.set(image,pending);
    pending.catch(()=>caseDrawingCache.delete(image));
  }
  return caseDrawingCache.get(image);
}
const restartNotice='The running Python server is out of date. Stop it with Ctrl+C, run python3 app.py again, then refresh this page. Your saved cases will be kept.';
async function api(path,data){if((path==='progress'||path==='practice-result'||(path==='case'&&data&&'learning' in data))&&!library.progress_states?.includes('learning'))throw Error(restartNotice);const response=await fetch('/api/'+path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const result=await response.json();if(path==='progress'&&(!response.ok&&result.error==='Learned must be true or false'||response.ok&&!('learning' in result)))throw Error(restartNotice);if(!response.ok)throw Error(path==='progress'&&response.status===404&&result.error==='Not found'?'Restart the Python app (Ctrl+C, then python3 app.py) and refresh this page to enable saved progress.':result.error||'Request failed');return result;}
function progressState(c){return c.learned?'learned':c.learning?'learning':'not-learned';}
function options(select,values,selected){select.replaceChildren(...values.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=value;return option}));select.value=selected;}
// Category paths preserve existing category values while allowing any depth.
function categoryPaths(algSet){
  const paths=new Set();
  for(const c of library.cases.filter(c=>c.alg_set===algSet)){
    const parts=c.category.split('/').map(part=>part.trim()).filter(Boolean);
    parts.forEach((_,i)=>paths.add(parts.slice(0,i+1).join(' / ')));
  }
  return [...paths].sort((a,b)=>a.localeCompare(b));
}
// Keep each set's expanded branches while browsing and updating progress.
const expandedCategories=new Set();
function renderCategories(all,categories){
  const nav=$('categories');
  nav.replaceChildren();
  function add(value,container){
    const descendants=categories.filter(path=>path&&path!==value&&path.split(' / ').slice(0,-1).join(' / ')===value);
    const row=document.createElement('div');row.className='category-row';
    const button=document.createElement('button');button.type='button';
    button.className='category-select'+(value===category?' active':'');
    button.textContent=(value?value.split(' / ').at(-1):'All cases')+' · '+all.filter(c=>withinCategory(c.category,value)).length;
    button.title=value||'All cases';
    if(value===category)button.setAttribute('aria-current','page');
    row.append(button);container.append(row);
    const key=JSON.stringify([set,value]);
    const hasChildren=!!value&&descendants.length>0;
    if(hasChildren){
      const children=document.createElement('div');children.className='category-children';
      children.id='category-branch-'+categories.indexOf(value);
      const toggle=document.createElement('button');toggle.type='button';toggle.className='category-toggle';
      function update(){
        const open=expandedCategories.has(key);
        children.hidden=!open;
        toggle.textContent=open?'▾':'▸';
        toggle.setAttribute('aria-label',`${open?'Collapse':'Expand'} ${value}`);
        for(const control of [button,toggle]){
          control.setAttribute('aria-expanded',String(open));
          control.setAttribute('aria-controls',children.id);
        }
      }
      function flip(){expandedCategories.has(key)?expandedCategories.delete(key):expandedCategories.add(key);update();}
      toggle.onclick=flip;
      row.prepend(toggle);container.append(children);update();
      for(const child of descendants)add(child,children);
      button.onclick=()=>{flip();category=value;render();};
    }else{
      button.onclick=()=>{category=value;render();};
    }
  }
  add('',nav);
  for(const value of categories.filter(path=>path&&!path.includes(' / ')))add(value,nav);
}
function withinCategory(value,parent){return !parent||value===parent||value.startsWith(parent+' / ');}
const METHODS={
  cfce:{name:'CFCE',sets:['CLL','ELL'],advanced:['Anti PLL'],summary:'Cross → F2L → CLL → ELL',description:'Build a cross and solve the first two layers, then solve last-layer corners with CLL and finish the edges with ELL.'},
  cfop:{name:'CFOP',sets:['OLL','PLL'],advanced:['WV','SV','COLL','Anti PLL'],summary:'Cross → F2L → OLL → PLL',description:'Build a cross, insert the four first-two-layer pairs, orient the last layer with OLL, then permute its pieces with PLL.'},
  roux:{name:'Roux',sets:['CMLL','LSE'],advanced:['EOLR'],summary:'First block → Second block → CMLL → LSE',description:'Build two opposite 1×2×3 blocks, solve the four upper corners with CMLL, then finish the last six edges using M and U moves.'},
};
const SUBSET_NAMES={'Anti PLL':'Permutation with flipped last-layer edges',EOLR:'Edge Orientation and Left/Right placement',CMLL:'Corners of the Last Layer, M slice free',LSE:'Last Six Edges',COLL:'Corners of the Last Layer',WV:'Winter Variation',SV:'Summer Variation',CLL:'Corners of the Last Layer',ELL:'Edges of the Last Layer',OLL:'Orientation of the Last Layer',PLL:'Permutation of the Last Layer'};
const SUBSET_DESCRIPTIONS={
  'Anti PLL':'Solve last-layer permutation when all four last-layer edges are flipped. CFCE and CFOP share this set, including its algorithms, drawings, notes, and progress.',
  CLL:'Solve the four last-layer corners in one step while preserving the first two layers. Finish the remaining edges with ELL.',
  ELL:'Solve the last-layer edges while preserving the solved corners and first two layers. Recognize edge orientation and permutation.',
  OLL:'Orient all last-layer pieces so the top face has one color, while preserving the first two layers. Permutation is solved next with PLL.',
  PLL:'Permute the oriented last-layer corners and edges into their solved positions while preserving orientation and the first two layers.',
  WV:'Insert the final F2L pair and orient the last-layer corners together when the top cross is already oriented. The final pair must be in the appropriate setup position.',
  SV:'Insert the final F2L pair and orient the last-layer corners together from the Summer Variation setup, with the top cross already oriented.',
  COLL:'Solve last-layer corner orientation and permutation while preserving edge orientation and the first two layers. Only edge permutation remains.',
  CMLL:'Solve the four upper corners while preserving both Roux blocks. The M slice and unsolved edges may change; finish with LSE.',
  EOLR:'Combine edge orientation and UL/UR placement. The algorithms place UL and UR on the bottom; insert them afterward with M2, then finish the remaining edges.',
  LSE:'Finish Roux by orienting the six remaining edges, placing the UL and UR edges, then solving the last four edges and centers with M and U moves. The bundled EO4A cases cover edge orientation. EOLR is available as an advanced Roux subset.',
};
function subsetDescription(name){return SUBSET_DESCRIPTIONS[name]||'Browse and practice your custom algorithm set.';}
function navigateSet(name){location.hash='/sets/'+encodeURIComponent(name);}
function navigationDiagram(subset){
  const drawing={};
  for(const sticker of lastLayer){
    const corner=sticker.face==='U'?[0,2,6,8].includes(sticker.index):sticker.index!==1;
    const emphasized=subset==='OLL'?sticker.face==='U':subset==='PLL'?true:['CLL','COLL','CMLL'].includes(subset)?corner:!corner;
    drawing[sticker.key]={color:emphasized?sticker.color:'#cbd2c8',highlight:false};
  }
  const diagram=document.createElement('div');diagram.className='mini-net';
  net(diagram,drawing,true);
  diagram.querySelector('svg').setAttribute('aria-label',subset==='OLL'?'Top face orientation':subset==='PLL'?'Oriented last layer with side sticker permutation':['CLL','COLL','CMLL'].includes(subset)?'Top view with last-layer corners emphasized':'Top view with last-layer edges emphasized');
  return diagram;
}
function navigationCard(title,description,sets,onClick){
  const button=document.createElement('button');button.className='navigation-card';
  const heading=document.createElement('h2');heading.textContent=title;
  const text=document.createElement('p');text.textContent=description;
  const cases=library.cases.filter(c=>sets.includes(c.alg_set));
  const count=document.createElement('span');count.textContent=`${cases.filter(c=>c.learned).length} / ${cases.length} algs learned`;
  if(['CFCE','CFOP','Roux',...Object.keys(SUBSET_NAMES)].includes(title)){
    const picture=document.createElement('div');picture.className='navigation-picture';
    if(['CFCE','CFOP','Roux'].includes(title)){
      const arrow=document.createElement('span');arrow.className='diagram-arrow';arrow.textContent='→';arrow.setAttribute('aria-hidden','true');
      picture.append(navigationDiagram(title==='CFCE'?'CLL':title==='Roux'?'CMLL':'OLL'),arrow,navigationDiagram(title==='CFCE'?'ELL':title==='Roux'?'LSE':'PLL'));
    }else picture.append(navigationDiagram(title));
    button.append(picture);
  }
  button.append(heading,text,count);button.onclick=onClick;return button;
}
let navigationMethod=null;
function renderNavigation(){
  const route=location.hash.slice(1)||'/';
  const method=route==='/advanced'?METHODS.cfop:route.startsWith('/methods/')?METHODS[route.slice(9)]:null;
  const isWiki=route==='/info'||route.startsWith('/info/');
  $('wiki-view').hidden=!isWiki;
  if(isWiki)renderWiki(route);
  const isMethod=!!method;
  if(method)navigationMethod=Object.keys(METHODS).find(key=>METHODS[key]===method);
  const isLibrary=route.startsWith('/sets/');
  if(isLibrary){
    let requested;try{requested=decodeURIComponent(route.slice(6));}catch{requested='';}
    if(library.sets.includes(requested))set=requested;
  }
  $('home-view').hidden=isMethod||isLibrary||isWiki;
  $('method-view').hidden=!isMethod;
  $('library-view').hidden=!isLibrary;
  $('categories').hidden=!isLibrary;
  options($('sets'),library.sets,set);
  const parents=Object.entries(METHODS).filter(([,method])=>[...method.sets,...method.advanced].includes(set));
  const parent=parents.find(([key])=>key===navigationMethod)||parents[0];
  $('subset-info').href='#/info/subset/'+encodeURIComponent(set);
  $('library-back').href=parent?'#/methods/'+parent[0]:'#/';
  $('library-back').textContent=parent?'← '+parent[1].name+' algorithm sets':'← Home';
  $('method-cards').replaceChildren(...Object.entries(METHODS).map(([key,method])=>navigationCard(method.name,method.summary+'. '+method.description,[...method.sets,...method.advanced],()=>{location.hash='/methods/'+key;})));
  $('method-eyebrow').textContent='3×3 METHOD';
  $('method-advanced').hidden=!method?.advanced.length;
  if(method){
    $('method-info').href='#/info/method/'+navigationMethod;
    $('method-title').textContent=method.name;
    $('method-description').textContent=method.description;
    $('subset-cards').replaceChildren(...method.sets.map(name=>navigationCard(name,SUBSET_NAMES[name]+'. '+subsetDescription(name),[name],()=>navigateSet(name))));
    $('advanced-cards').replaceChildren(...method.advanced.map(name=>navigationCard(name,SUBSET_NAMES[name]+'. '+subsetDescription(name),[name],()=>navigateSet(name))));
  }
  const supported=Object.values(METHODS).flatMap(method=>[...method.sets,...method.advanced]);
  const custom=library.sets.filter(name=>!supported.includes(name));
  $('custom-sets').hidden=!custom.length;
  $('custom-set-cards').replaceChildren(...custom.map(name=>navigationCard(name,'Your custom algorithm set',[name],()=>navigateSet(name))));
  document.title=isWiki?'Cubing Wiki · Cube Library':isLibrary?set+' · Cube Library':isMethod?method.name+' · Cube Library':'Cube Library';
}
window.addEventListener('hashchange',()=>{category='';$('search').value='';$('progress-filter').value='all';render();});
async function load(){library=await api('library');$('server-notice').hidden=!!library.progress_states?.includes('learning');$('server-notice').textContent=restartNotice;if(!library.sets.includes(set))set=library.sets[0];options($('sets'),library.sets,set);render();}
function net(container,state,mini=false){
  if(state.D4)return fullCubeNet(container,state,mini);
  container.classList.remove('full-cube-view');
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 100 100');
  svg.setAttribute('class','cube-diagram');
  svg.setAttribute('aria-label',mini?'Recognition drawing':'Editable last-layer drawing');
  if(mini)svg.setAttribute('role','img');
  for(const {key,face,index,x,y,color:defaultColor} of lastLayer){
    const sticker=state[key]||{color:defaultColor,highlight:false};
    const left=x===1?3:x===5?85:16+(x-2)*23;
    const top=y===1?3:y===5?85:16+(y-2)*23;
    const width=x===1||x===5?13:23;
    const height=y===1||y===5?13:23;
    const rect=document.createElementNS(ns,'rect');
    for(const [attr,value] of Object.entries({x:left,y:top,width,height,fill:sticker.color,stroke:'#000','stroke-width':3}))rect.setAttribute(attr,value);
    if(!mini){
      rect.setAttribute('class','sticker');
      rect.setAttribute('role','button');rect.setAttribute('tabindex','0');
      rect.setAttribute('aria-label',`${face} sticker ${index+1}${sticker.highlight?', highlighted':''}`);
      rect.setAttribute('aria-pressed',String(sticker.highlight));
      const edit=()=>{
        drawing[key]={color:mode==='paint'?color:sticker.color,highlight:mode==='highlight'?!sticker.highlight:sticker.highlight};
        dirty=true;net(container,drawing);
        const replacement=container.querySelector(`[data-key="${key}"]`);
        replacement?.focus({preventScroll:true});
      };
      rect.dataset.key=key;rect.onclick=edit;
      rect.onkeydown=event=>{if(event.key==='Enter'||event.code==='Space'){event.preventDefault();edit();}};
    }
    svg.append(rect);
    if(sticker.highlight){
      const mark=document.createElementNS(ns,'text');
      mark.setAttribute('x',left+width/2);mark.setAttribute('y',top+height/2);
      mark.setAttribute('class','recognition-star');
      mark.setAttribute('font-size',Math.min(width,height)*.75);
      mark.setAttribute('aria-hidden','true');mark.textContent='★';svg.append(mark);
    }
  }
  container.replaceChildren(svg);
}

function render(){renderNavigation();const all=library.cases.filter(c=>c.alg_set===set);$('title').textContent=set;$('subtitle').textContent=subsetDescription(set);const categories=['',...categoryPaths(set)];if(!categories.includes(category))category='';renderCategories(all,categories);const query=$('search').value.toLowerCase();const cases=all.filter(c=>withinCategory(c.category,category)&&($('progress-filter').value==='all'||progressState(c)===$('progress-filter').value)&&[c.name,c.category,c.algorithm,c.recognition,c.description].some(v=>v.toLowerCase().includes(query)));const compare=(a,b)=>a.localeCompare(b,undefined,{numeric:true,sensitivity:'base'});
cases.sort((a,b)=>compare(a.category||'\uffff',b.category||'\uffff')||compare(a.name,b.name)||a.id-b.id);
$('count').textContent=`${cases.length} shown`;
visibleCases=cases;
const learnedCount=cases.filter(c=>c.learned).length;
$('learned-count').textContent=`${learnedCount} / ${cases.length} algs learned`;
$('learned-progress').max=cases.length||1;
$('learned-progress').value=learnedCount;
$('progress-scope').textContent=[set,category].filter(Boolean).join(' / ')+(query||$('progress-filter').value!=='all'?' · Filtered cases':'');
$('grid').replaceChildren();
let previousParent=null;
for(const c of cases){
  const parent=c.category.split('/')[0].trim()||'Uncategorized';
  if(!category&&parent!==previousParent){
    const heading=document.createElement('h2');
    heading.className='category-heading';
    heading.textContent=parent;
    $('grid').append(heading);
    previousParent=parent;
  }
const card=document.createElement('article');card.className='card '+progressState(c);const preview=document.createElement('div');preview.className='preview';const state=JSON.parse(c.drawing||'{}');if($('recognition-only').checked||state.useDrawing||!c.image){const mini=document.createElement('div');mini.className='mini-net';net(mini,state.stickers||{},true);caseDrawing(c.image).then(base=>net(mini,{...base,...state.stickers},true)).catch(()=>{});preview.append(mini);}else{const img=document.createElement('img');img.src=c.image;img.alt=c.name+' cube state';preview.append(img);}const name=document.createElement('strong');name.textContent=c.name;const tag=document.createElement('small');tag.textContent=c.category||'Uncategorized';const badge=document.createElement('span');badge.className='badge';badge.textContent=c.algorithm?'ALG SAVED':'ADD ALG';const progress=document.createElement('button');progress.type='button';const nextState={'not-learned':'learning',learning:'learned',learned:'not-learned'}[progressState(c)];progress.setAttribute('aria-label',`${c.name}: ${progressState(c).replace('-',' ')}. Change to ${nextState.replace('-',' ')}`);progress.onclick=async()=>{progress.disabled=true;try{const result=await api('progress',{id:c.id,state:nextState});Object.assign(c,result);render();}catch(error){progress.disabled=false;alert('Could not save progress: '+error.message);}};progress.className='progress '+(c.learned?'is-learned':'');progress.textContent=c.learned?'✓ Learned':c.learning?'◐ Learning':'○ Not learned';const open=document.createElement('button');open.type='button';open.className='case-open';open.setAttribute('aria-label',`Open ${c.name}`);open.append(preview,badge,name,tag);open.onclick=()=>openCase(c);card.append(open,progress);$('grid').append(card);}if(!cases.length){const empty=document.createElement('p');empty.textContent='No cases here yet. Add a case or change your search.';$('grid').append(empty);}}
async function openCase(c){current=c?{...c}:{name:'',alg_set:set,category:category,algorithm:'',description:'',recognition:'',image:'',drawing:'{}'};const opened=current;const state=JSON.parse(current.drawing||'{}');let base={};let drawingError='';try{base=await caseDrawing(current.image);}catch(error){drawingError=error.message;}if(current!==opened)return;drawing=structuredClone({...base,...state.stickers});$('use-drawing').checked=!!state.useDrawing;$('learned').value=progressState(current);for(const key of ['name','algorithm','description','recognition'])$(key).value=current[key];$('category-path').value=[current.alg_set,...current.category.split('/').map(part=>part.trim()).filter(Boolean)].join('/');$('detail-title').textContent=c?c.name:'New case';$('original').replaceChildren();if(current.image){const img=document.createElement('img');img.src=current.image;img.alt=current.name+' original reference';$('original').append(img);}else $('original').textContent='Your custom cube state';$('drawing-help').textContent=drawing.D4?'Two cube views show every face: U/F/R on the left, U/B/L on the right, with U up in both views. Paint or highlight visible stickers; the Roux blocks retain their colors.':'Top view of the last layer: U in the middle, B above, F below, L left, and R right. Paint stickers or mark recognition clues.';$('status').textContent=drawingError;net($('cube'),drawing);dirty=false;updateSetup();$('detail').showModal();}
let inverseSequence=0;async function updateSetup(){$('algorithm-heading').textContent=$('algorithm').value||'No algorithm yet';const sequence=++inverseSequence;try{const result=await api('inverse',{id:current?.id,algorithm:$('algorithm').value});if(sequence===inverseSequence)$('setup').textContent=result.setup||'Enter a solution to generate its setup.';}catch(e){if(sequence===inverseSequence)$('setup').textContent=e.message;}}
$('algorithm').addEventListener('input',updateSetup);$('case-form').addEventListener('input',()=>dirty=true);
$('case-form').onsubmit=async e=>{e.preventDefault();const updated={...current};for(const key of ['name','algorithm','description','recognition'])updated[key]=$(key).value;const parts=$('category-path').value.split('/').map(part=>part.trim());if(parts.some(part=>!part)){$('status').textContent='Enter a set and category names separated by /, with no empty parts.';return;}const enteredSet=parts.shift();updated.alg_set=library.sets.find(name=>name.toLowerCase()===enteredSet.toLowerCase())||enteredSet;updated.category=parts.join(' / ');updated.learned=Number($('learned').value==='learned');updated.learning=Number($('learned').value==='learning');updated.drawing=JSON.stringify({useDrawing:$('use-drawing').checked,stickers:drawing});try{if(!library.sets.includes(updated.alg_set))await api('sets',{name:updated.alg_set});const result=await api('case',updated);current={...updated,id:result.id};dirty=false;set=updated.alg_set;navigateSet(set);category='';$('status').textContent='Saved to your library.';await load();$('detail').close();}catch(error){$('status').textContent=error.message;}};
function closeCase(){if(!dirty||confirm('Discard unsaved changes?')){$('detail').close();dirty=false;}}
$('close').onclick=closeCase;$('detail').addEventListener('cancel',e=>{e.preventDefault();closeCase()});window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
$('sets').onchange=()=>navigateSet($('sets').value);$('search').oninput=render;$('progress-filter').onchange=render;$('recognition-only').onchange=render;$('new-case').onclick=()=>openCase(null);
$('add-set').onclick=async()=>{const name=prompt('Name your algorithm set (e.g. OLL, PLL, ZBLL)');if(!name?.trim())return;try{await api('sets',{name:name.trim()});set=name.trim();navigateSet(set);category='';await load();}catch(e){alert(e.message)}};
for(const value of ['#ffff00','#ffffff','#ff0000','#ff9900','#00ff00','#0000ff','#aab2a7']){const b=document.createElement('button');b.type='button';b.className='swatch'+(value===color?' selected':'');b.style.backgroundColor=value;b.setAttribute('aria-label',({'#ffff00':'Yellow','#ffffff':'White','#ff0000':'Red','#ff9900':'Orange','#00ff00':'Green','#0000ff':'Blue','#aab2a7':'Gray'})[value]);b.onclick=()=>{color=value;document.querySelectorAll('.swatch').forEach(s=>s.classList.remove('selected'));b.classList.add('selected')};$('palette').append(b);}
for(const tool of ['paint','highlight'])$(tool).onclick=()=>{mode=tool;for(const t of ['paint','highlight'])$(t).setAttribute('aria-pressed',String(t===tool))};
$('rotate-layer').onclick=()=>{
  if(drawing.D4){
    const geometry=notationGeometry(),rotated={...drawing};
    for(const [index,sticker] of geometry.entries()){
      if(sticker.position[1]!==1)continue;
      const position=notationRotate(sticker.position,1,-Math.PI/2).map(Math.round),normal=notationRotate(sticker.normal,1,-Math.PI/2).map(Math.round);
      const target=geometry.findIndex(item=>item.position.every((v,i)=>v===position[i])&&item.normal.every((v,i)=>v===normal[i]));
      rotated[geometry[target].face+target%9]={...drawing[sticker.face+index%9]};
    }
    drawing=rotated;dirty=true;net($('cube'),drawing);return;
  }
  const rotated={...drawing};
  for(const source of lastLayer){
    const target=lastLayer.find(sticker=>sticker.x===6-source.y&&sticker.y===source.x);
    rotated[target.key]={...(drawing[source.key]||{color:source.color,highlight:false})};
  }
  drawing=rotated;dirty=true;net($('cube'),drawing);
};
$('reset').onclick=async()=>{
  if(!confirm('Reset colors to the original case state and remove highlights?'))return;
  const opened=current;
  try{const base=await caseDrawing(current.image);if(current!==opened||!$('detail').open)return;drawing=structuredClone(base);dirty=true;net($('cube'),drawing);}
  catch(error){$('status').textContent=error.message;}
};
$('copy').onclick=async()=>{try{const {setup}=await api('inverse',{id:current?.id,algorithm:$('algorithm').value});if(!setup)throw Error('Enter an algorithm first.');await navigator.clipboard.writeText(setup);$('status').textContent='Setup copied.';}catch(e){$('status').textContent=e.message}};
load().catch(e=>{$('grid').textContent='Could not load the library: '+e.message});

// Explanatory content is separate from saved algorithms and progress.
const WIKI_METHOD_NOTES={
  cfce:['Start with the cross and four first-two-layer pairs. This leaves only the last layer to solve.', 'CLL solves the corners first. ELL then solves the remaining edges while keeping the corners solved.'],
  cfop:['The cross solves four edges on one face. F2L pairs each remaining lower-layer corner with its matching edge and inserts the four pairs.', 'OLL makes the last face one color. PLL then moves the last-layer pieces to their correct positions. Advanced subsets can combine steps or handle special cases.'],
  roux:['Build a 1×2×3 block on one side, then a matching block on the opposite side. These blocks leave the M slice available for later steps.', 'CMLL solves the four upper corners while preserving those blocks. LSE finishes the six remaining edges and centers; EO4A and EOLR cover different parts of that finish.'],
};
const WIKI_SUBSET_NOTES={
  CLL:['Use this after the first two layers are solved. Recognize the orientation of the upper corners and the side colors that identify their permutation.', 'The edges may change during the algorithm. In CFCE, ELL handles them afterward.'],
  ELL:['Use this after CLL, with the first two layers and all corners solved. Look for flipped edges and where each edge belongs.', 'EPLL is the part of ELL where the last-layer edges are already oriented and only need permutation.'],
  OLL:['Use this once F2L is complete. Focus on the top-color pattern on the upper face and its surrounding side stickers.', 'A single-color top face does not imply that the last layer is permuted correctly. Continue with PLL.'],
  PLL:['Use this after the last layer is oriented. Recognize matching bars, headlights, and the relative positions of corners and edges.', 'An AUF, or adjustment of the U face, may be needed before or after the algorithm.'],
  WV:['Winter Variation combines insertion of the final F2L pair with corner orientation. Check that the last-layer edges are already oriented and the final pair has the required setup.', 'The illustrated setup matters: another pair position may require a different algorithm. Finish last-layer permutation afterward.'],
  SV:['Summer Variation also combines the final F2L insertion with corner orientation, using a different pair setup from Winter Variation.', 'Compare the pair position and upper-corner pattern with the case diagram before executing the algorithm.'],
  COLL:['Use this with the first two layers solved and last-layer edges oriented. Recognize both the corner orientation pattern and the corner side colors.', 'COLL preserves edge orientation, leaving an edge-permutation finish. CLL and CMLL have different preservation requirements, so their algorithms are not interchangeable without checking.'],
  CMLL:['Use this after both Roux blocks are complete. Recognize upper-corner orientation and permutation; the six unsolved edges do not determine the CMLL case.', 'Unlike COLL, CMLL does not need to preserve edge orientation or the M slice. Continue with LSE.'],
  LSE:['Last Six Edges finishes Roux after CMLL. It includes edge orientation, placement of the UL and UR edges, and a final four-edge and center finish.', 'The current LSE library contains EO4A, the edge-orientation stage. Advanced Roux EOLR combines edge orientation with left/right-edge placement.', 'Inspect the bottom edges as well as the top layer: the thumbnails cannot show every LSE recognition detail.'],
  EOLR:['EOLR combines the edge-orientation and left/right-edge-placement stages of LSE. The supplied algorithms move UL and UR to the bottom; M2 inserts them afterward.', 'The positions in parentheses in each case name identify where UL and UR start. These algorithms solve a stage, rather than the whole cube, so practice uses case-specific setups.', 'The reference includes 46 cases and omits some mirrored cases.'],
  'Anti PLL':['These cases combine last-layer permutation with all four upper edges flipped. The Pure case has no additional PLL permutation.', 'CFCE and CFOP link to one shared Anti PLL library. Editing an algorithm, note, drawing, or progress state through either method changes the same saved case.'],
};
const WIKI_SOURCES={
  CLL:['CubePal CLL','https://www.cubepal.app/cubes/3x3x3/stages/cll'],
  ELL:['Sarah’s ELL reference','https://sarah.cubing.net/3x3x3/ell'],
  OLL:['SpeedCubeDB OLL','https://speedcubedb.com/a/3x3/OLL'],
  PLL:['SpeedCubeDB PLL','https://speedcubedb.com/a/3x3/PLL'],
  WV:['SpeedCubeDB WV','https://speedcubedb.com/a/3x3/WV'],
  SV:['SpeedCubeDB SV','https://speedcubedb.com/a/3x3/SV'],
  COLL:['SpeedCubeDB COLL','https://speedcubedb.com/a/3x3/COLL'],
  CMLL:['SpeedCubeDB CMLL','https://speedcubedb.com/a/3x3/CMLL'],
  LSE:['SpeedCubeDB EO4A','https://speedcubedb.com/a/3x3/EO4A'],
  EOLR:['CubingApp EOLR','https://cubingapp.com/algorithms/LSE-EOLR'],
  'Anti PLL':['SpeedCubeDB Anti PLL','https://speedcubedb.com/a/3x3/AntiPLL'],
};
function wikiLink(label,path){const a=document.createElement('a');a.textContent=label;a.href=path;return a;}
function wikiParagraph(container,text){const p=document.createElement('p');p.textContent=text;container.append(p);}
function renderWiki(route){
  const topics=document.getElementById('wiki-topics'), article=document.getElementById('wiki-article');
  const query=document.getElementById('wiki-search').value.trim().toLowerCase();
  topics.replaceChildren(wikiLink('Wiki home','#/info'),wikiLink('Notation guide','#/info/notation'));
  let count=0;
  for(const [key,method] of Object.entries(METHODS)){
    const group=document.createElement('section');
    const matches=text=>!query||text.toLowerCase().includes(query);
    if(matches(method.name+' '+method.description)){
      group.append(wikiLink(method.name,'#/info/method/'+key));count++;
    }
    for(const name of [...method.sets,...method.advanced]){
      if(!matches(name+' '+SUBSET_NAMES[name]+' '+subsetDescription(name)+' '+method.name))continue;
      const link=wikiLink(name+(method.advanced.includes(name)?' · advanced':''),'#/info/subset/'+encodeURIComponent(name));
      link.className='wiki-subtopic';group.append(link);count++;
    }
    if(group.childElementCount)topics.append(group);
  }
  if(!count)wikiParagraph(topics,'No matching topics.');
  for(const link of topics.querySelectorAll('a'))if(link.hash==='#'+route)link.setAttribute('aria-current','page');
  article.replaceChildren();
  let parts;try{parts=route.split('/').map(decodeURIComponent);}catch{parts=[];}
  const kind=parts[2], key=parts[3];
  const method=kind==='method'&&Object.hasOwn(METHODS,key)?METHODS[key]:null;
  const subset=kind==='subset'&&Object.hasOwn(SUBSET_NAMES,key)?key:null;
  const title=document.createElement('h2');title.textContent=route==='/info/notation'?'Cube notation':method?method.name:subset?subset:'Welcome to the cubing wiki';article.append(title);
  if(route==='/info/notation'){
    renderNotationGuide(article);
  }else if(method){
    wikiParagraph(article,method.description);
    for(const text of WIKI_METHOD_NOTES[key]||[])wikiParagraph(article,text);
    for(const [label,sets] of [['Algorithm sets',method.sets],['Advanced subsets',method.advanced]]){
      if(!sets.length)continue;
      const h=document.createElement('h3');h.textContent=label;article.append(h);
      for(const name of sets){article.append(wikiLink(name+' — '+SUBSET_NAMES[name],'#/info/subset/'+encodeURIComponent(name)));}
    }
    const browse=wikiLink('Open '+method.name+' library','#/methods/'+key);browse.className='info-link';article.append(browse);
  }else if(subset){
    wikiParagraph(article,SUBSET_NAMES[subset]);wikiParagraph(article,subsetDescription(subset));
    for(const text of WIKI_SUBSET_NOTES[subset]||[])wikiParagraph(article,text);
    const h=document.createElement('h3');h.textContent='Related methods';article.append(h);
    for(const [id,value] of Object.entries(METHODS))if([...value.sets,...value.advanced].includes(subset))article.append(wikiLink(value.name,'#/info/method/'+id));
    const browse=wikiLink('Browse '+subset+' cases','#/sets/'+encodeURIComponent(subset));browse.className='info-link';article.append(browse);
    const source=WIKI_SOURCES[subset];if(source){const a=wikiLink(source[0]+' ↗',source[1]);a.target='_blank';a.rel='noreferrer';article.append(a);}
  }else{
    if(route!=='/info')wikiParagraph(article,'This topic was not found. Choose a method or subset from the navigation.');
    wikiParagraph(article,'Choose a method to follow its solving stages, or open a subset to learn when it applies, what to recognize, and what remains afterward.');
    for(const [id,value] of Object.entries(METHODS))article.append(wikiLink(value.name+' — '+value.summary,'#/info/method/'+id));
    const h=document.createElement('h3');h.textContent='Useful terms';article.append(h);
    wikiParagraph(article,'F2L means First Two Layers. Orientation describes how a piece is twisted or flipped; permutation describes where it belongs. AUF means adjusting the U face before or after an algorithm.');
    renderNotationGuide(article);
  }
}
document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('wiki-search').addEventListener('input',()=>renderWiki(location.hash.slice(1)||'/info'));
});

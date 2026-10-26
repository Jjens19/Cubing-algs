// Apply before styles paint to avoid flashing the wrong saved theme.
(()=>{
  const key='cube-library-theme',media=window.matchMedia('(prefers-color-scheme: dark)');
  let preference=null;
  try{const saved=localStorage.getItem(key);if(saved==='light'||saved==='dark')preference=saved;}catch{}
  function apply(){
    const dark=(preference|| (media.matches?'dark':'light'))==='dark';
    document.documentElement.dataset.theme=dark?'dark':'light';
    const button=document.getElementById('theme-toggle');
    if(button){button.textContent=dark?'☀ Light mode':'☾ Dark mode';button.setAttribute('aria-pressed',String(dark));button.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode');}
  }
  apply();
  media.addEventListener('change',()=>{if(!preference)apply();});
  window.addEventListener('storage',event=>{if(event.key===key){preference=['light','dark'].includes(event.newValue)?event.newValue:null;apply();}});
  document.addEventListener('DOMContentLoaded',()=>{
    apply();
    document.getElementById('theme-toggle').onclick=()=>{
      preference=document.documentElement.dataset.theme==='dark'?'light':'dark';
      try{localStorage.setItem(key,preference);}catch{}
      apply();
    };
  });
})();

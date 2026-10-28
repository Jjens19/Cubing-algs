import {connectGanCube} from './vendor/gan-web-bluetooth-3.0.2.js';
import {scanLocalCubes,connectLocalGanCube} from './local-bluetooth.js';

const element=id=>document.getElementById(id);
let connection=null,subscription=null,connecting=false,selectedDevice=null;
let moves=[],moveCount=0,battery=null,cubeState='Waiting for cube state',resetting=false,resetPending=false;
const macPattern=/^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/;
function normalizeMac(value){return value.trim().replace(/-/g,':').toUpperCase();}
function status(text){element('bluetooth-cube-status').textContent=text;}
function renderDetails(){
  element('reset-bluetooth-cube').hidden=!connection;
  element('reset-bluetooth-cube-help').hidden=!connection;
  element('reset-bluetooth-cube').disabled=resetting||element('reset-bluetooth-cube').dataset.timerLocked==='true';
  element('bluetooth-cube-details').hidden=!connection;
  element('bluetooth-cube-details').textContent=[cubeState,battery===null?null:`Battery ${battery}%`,`${moveCount} moves`].filter(Boolean).join(' · ');
  element('bluetooth-cube-moves').hidden=!moves.length;
  element('bluetooth-cube-moves').textContent=moves.join(' ');
}
function resetConnection(message){
  subscription?.unsubscribe();subscription=null;connection=null;resetPending=false;
  moves=[];moveCount=0;battery=null;cubeState='Waiting for cube state';
  element('connect-bluetooth-cube').textContent='Connect Bluetooth Cube';
  status(message);renderDetails();
  document.dispatchEvent(new CustomEvent('bluetooth-cube-disconnected'));
}
function requestMac(device){
  const dialog=element('cube-mac-dialog');
  element('cube-mac-description').textContent=`The browser could not read the Bluetooth address of ${device.name||'your GAN cube'}. Enter its MAC address from your computer’s Bluetooth device details.`;
  element('cube-mac-input').value=element('bluetooth-cube-mac').value;
  element('cube-mac-error').textContent='';
  return new Promise(resolve=>{
    let value=null;
    const close=()=>{dialog.removeEventListener('close',close);resolve(value);};
    dialog.addEventListener('close',close);
    element('cube-mac-form').onsubmit=event=>{
      event.preventDefault();const mac=normalizeMac(element('cube-mac-input').value);
      if(!macPattern.test(mac)){element('cube-mac-error').textContent='Enter six pairs, for example AA:BB:CC:DD:EE:FF.';return;}
      value=mac;element('bluetooth-cube-mac').value=mac;dialog.close();
    };
    element('cancel-cube-mac').onclick=()=>dialog.close();
    dialog.showModal();element('cube-mac-input').focus();
  });
}
async function macProvider(device,fallback){
  selectedDevice=device;
  if(device.localBridge&&macPattern.test(device.id.toUpperCase()))return device.id.toUpperCase();
  const entered=normalizeMac(element('bluetooth-cube-mac').value);
  if(entered){if(!macPattern.test(entered))throw Error('Invalid Bluetooth MAC address. Use AA:BB:CC:DD:EE:FF.');return entered;}
  try{const saved=localStorage.getItem('cube-library-gan-mac-'+device.id);if(saved&&macPattern.test(saved))return saved;}catch{}
  return fallback?requestMac(device):null;
}
function onCubeEvent(event){
  if(event.type==='GYRO'){document.dispatchEvent(new CustomEvent('bluetooth-cube-event',{detail:event}));return;}
  if(event.type==='DISCONNECT'){resetConnection('Cube disconnected. Click Connect Bluetooth Cube to reconnect.');return;}
  if(event.type==='MOVE'){
    moveCount++;moves.push(event.move);moves=moves.slice(-20);
    // Ask for authoritative state rather than guessing after missed BLE packets.
    connection?.sendCubeCommand({type:'REQUEST_FACELETS'}).catch(()=>{});
  }else if(event.type==='BATTERY')battery=event.batteryLevel;
  else if(event.type==='FACELETS'){
    const state=event.facelets;
    if(typeof state==='string'&&state.length===54){
      cubeState=Array.from({length:6},(_,i)=>state.slice(i*9,i*9+9)).every(face=>new Set(face).size===1)?'Solved':'Mixed';
      if(resetPending){resetPending=false;status(cubeState==='Solved'?'Cube state reset to solved.':'Reset sent, but the cube reports a mixed state. Try resetting again.');}
    }
  }
  document.dispatchEvent(new CustomEvent('bluetooth-cube-event',{detail:event}));
  renderDetails();
}
element('reset-bluetooth-cube').onclick=async()=>{
  const current=connection;
  if(!current||resetting)return;
  document.dispatchEvent(new CustomEvent('bluetooth-cube-reset'));
  resetting=true;resetPending=true;
  element('connect-bluetooth-cube').disabled=true;renderDetails();
  status('Resetting cube state…');
  try{
    await current.sendCubeCommand({type:'REQUEST_RESET'});
    if(connection!==current)return;
    moves=[];moveCount=0;cubeState='Waiting for reset confirmation';renderDetails();
    await current.sendCubeCommand({type:'REQUEST_FACELETS'});
  }catch(error){
    if(connection===current){resetPending=false;status('Could not reset cube state: '+error.message);}
  }finally{
    resetting=false;element('connect-bluetooth-cube').disabled=connecting;renderDetails();
  }
};
async function chooseLocalCube(){
  status('Scanning for GAN cubes through the local app…');
  const devices=await scanLocalCubes();
  if(!devices.length)throw Error('No GAN cubes found. Wake the cube, close other cube apps, and try again.');
  const dialog=element('local-cube-dialog'),list=element('local-cube-list');
  list.replaceChildren();
  return new Promise(resolve=>{
    let selected=null;
    const closed=()=>{dialog.removeEventListener('close',closed);resolve(selected);};
    dialog.addEventListener('close',closed);
    for(const device of devices){
      const button=document.createElement('button');button.type='button';button.textContent=device.name+' · '+device.id;
      button.onclick=()=>{selected=device;dialog.close();};list.append(button);
    }
    element('cancel-local-cube').onclick=()=>dialog.close();dialog.showModal();
  });
}
element('connect-bluetooth-cube').onclick=async()=>{
  if(connecting)return;
  if(connection){
    try{await connection.disconnect();resetConnection('Cube disconnected.');}
    catch{status('Could not disconnect the cube. Try again.');}
    return;
  }
  const transport=element('bluetooth-transport').value;
  const local=transport==='local'||(transport==='auto'&&(!navigator.bluetooth?.requestDevice||navigator.brave));
  if(!local&&!navigator.bluetooth?.requestDevice){status('Web Bluetooth is unavailable. Select Local app in Connection help.');return;}
  if(!window.isSecureContext){status('Bluetooth requires localhost or HTTPS.');return;}
  connecting=true;element('connect-bluetooth-cube').disabled=true;status('Choose your GAN cube in the Bluetooth device chooser…');
  try{
    if(local){
      const selected=await chooseLocalCube();
      if(!selected){status('No cube selected.');return;}
      connection=await connectLocalGanCube(selected,macProvider);
    }else connection=await connectGanCube(macProvider);
    moves=[];moveCount=0;battery=null;cubeState='Waiting for cube state';
    status(`Connected to ${connection.deviceName||'GAN cube'}${local?' through the local app':''}. Turn a face to see moves.`);
    element('connect-bluetooth-cube').textContent='Disconnect Bluetooth Cube';
    try{localStorage.setItem('cube-library-gan-mac-'+selectedDevice.id,connection.deviceMAC);}catch{}
    subscription=connection.events$.subscribe({next:onCubeEvent,error:()=>{selectedDevice?.gatt?.disconnect();resetConnection('Cube connection failed. Reconnect to try again.');}});
    renderDetails();
    document.dispatchEvent(new CustomEvent('bluetooth-cube-connected'));
    for(const type of ['REQUEST_FACELETS','REQUEST_BATTERY']){
      try{await connection?.sendCubeCommand({type});}catch{status('Connected, but cube data could not be read. Check the MAC address in Connection help and reconnect.');}
    }
  }catch(error){
    selectedDevice?.gatt?.disconnect();
    resetConnection(error.name==='NotFoundError'?'No cube selected. Wake your cube and try again.':`Could not connect: ${error.message}${!local?' Try Local app in Connection help.':''}`);
  }finally{connecting=false;element('connect-bluetooth-cube').disabled=false;}
};
window.addEventListener('pagehide',()=>{connection?.disconnect().catch(()=>{});});

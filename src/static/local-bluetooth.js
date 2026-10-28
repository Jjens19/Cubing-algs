import {connectGanCube} from './vendor/gan-web-bluetooth-3.0.2.js';

async function request(action,data={}){
  const response=await fetch('/api/bluetooth/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),keepalive:action==='disconnect'});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'Local Bluetooth failed.');
  return result;
}
export async function scanLocalCubes(){return (await request('scan')).devices;}

// Adapt the GAN library's GATT interface to the app's local Python transport.
export async function connectLocalGanCube(selected,macProvider){
  const device=new EventTarget();
  device.id=selected.id;device.name=selected.name;device.localBridge=true;
  let token=null,cursor=0,pollTimer=null,closed=false,disconnectTask=null;
  const characteristics=new Map();
  const call=(action,data={})=>request(action,{...data,token});
  const ended=()=>{
    if(closed)return;closed=true;clearTimeout(pollTimer);device.gatt.connected=false;
    device.dispatchEvent(new Event('gattserverdisconnected'));
  };
  const poll=async()=>{
    if(closed)return;
    try{
      const result=await call('events',{cursor});
      if(!result.connected){ended();return;}
      for(const event of result.events){
        cursor=event.serial;
        const characteristic=characteristics.get(event.characteristic);
        if(characteristic){characteristic.value=new DataView(new Uint8Array(event.value).buffer);characteristic.dispatchEvent(new Event('characteristicvaluechanged'));}
      }
      if(!closed)pollTimer=setTimeout(poll,120);
    }catch{await call('disconnect').catch(()=>{});ended();}
  };
  const characteristic=uuid=>{
    if(!characteristics.has(uuid)){
      const value=new EventTarget();value.uuid=uuid;
      value.writeValue=bytes=>call('write',{characteristic:uuid,value:Array.from(bytes)});
      value.startNotifications=async()=>{await call('notify',{characteristic:uuid});if(!pollTimer)pollTimer=setTimeout(poll,0);return value;};
      value.stopNotifications=async()=>value;
      characteristics.set(uuid,value);
    }
    return characteristics.get(uuid);
  };
  device.gatt={connected:false,async connect(){
    const result=await request('connect',{device:device.id});token=result.token;device.gatt.connected=true;
    device.gatt.getPrimaryServices=async()=>result.services.map(uuid=>({uuid,getCharacteristic:async key=>characteristic(key)}));
    return device.gatt;
  },disconnect(){if(!token)return;const current=token;ended();disconnectTask=request('disconnect',{token:current}).catch(()=>{});}};
  const descriptor=Object.getOwnPropertyDescriptor(navigator,'bluetooth');
  // Only the library's initial device request uses this temporary adapter.
  Object.defineProperty(navigator,'bluetooth',{configurable:true,value:{requestDevice:async()=>device}});
  try{
    const connection=await connectGanCube(async(d,fallback)=>{
      if(/^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/i.test(d.id)){
        await macProvider(d,false);return d.id.toUpperCase();
      }
      return macProvider(d,fallback);
    });
    const disconnect=connection.disconnect.bind(connection);
    connection.disconnect=async()=>{await disconnect();await disconnectTask;};
    return connection;
  }catch(error){device.gatt.disconnect();throw error;}
  finally{if(descriptor)Object.defineProperty(navigator,'bluetooth',descriptor);else delete navigator.bluetooth;}
}

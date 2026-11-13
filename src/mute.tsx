import React,{useSyncExternalStore} from 'react';
// Global "mute videos and music" default plus per-media overrides. Changing the
// global switch clears every override, so all players follow it; each player can
// still be toggled on its own afterwards.
const KEY='yukine-muted';
let globalMuted=(()=>{try{return localStorage.getItem(KEY)!=='false';}catch{return true;}})();
const overrides=new Map<string,boolean>();
const listeners=new Set<()=>void>();
const emit=()=>listeners.forEach(fn=>fn());
const subscribe=(fn:()=>void)=>{listeners.add(fn);return ()=>{listeners.delete(fn);};};
export const isMuted=(key:string)=>overrides.get(key)??globalMuted;
export function setMuted(key:string,muted:boolean){if(isMuted(key)===muted)return;overrides.set(key,muted);emit();}
export function setGlobalMuted(muted:boolean){globalMuted=muted;overrides.clear();try{localStorage.setItem(KEY,String(muted));}catch{}emit();}
export const useMediaMuted=(key:string)=>useSyncExternalStore(subscribe,()=>isMuted(key));
export const useGlobalMuted=()=>useSyncExternalStore(subscribe,()=>globalMuted);
/** A <video> whose mute state follows the global switch and remembers manual toggles. */
export function SyncedVideo({muteKey,onVolumeChange,...props}:React.VideoHTMLAttributes<HTMLVideoElement>&{muteKey:string}){
  const muted=useMediaMuted(muteKey);
  return <video {...props} muted={muted} onVolumeChange={e=>{setMuted(muteKey,e.currentTarget.muted);onVolumeChange?.(e);}}/>;
}

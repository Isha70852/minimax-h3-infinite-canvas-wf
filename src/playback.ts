import {useEffect,useState} from 'react';
export function usePlaybackVolume(){
 const [volume,setVolume]=useState(()=>{const raw=localStorage.getItem('h3-playback-volume');const value=raw===null?1:Number(raw);return Number.isFinite(value)?Math.min(1,Math.max(0,value)):1;});
 useEffect(()=>{
  localStorage.setItem('h3-playback-volume',String(volume));
  const apply=(root:ParentNode)=>{root.querySelectorAll<HTMLMediaElement>('video,audio').forEach(el=>{el.volume=volume;});};
  apply(document);
  const observer=new MutationObserver(records=>{for(const r of records)for(const node of r.addedNodes)if(node instanceof Element){if(node instanceof HTMLMediaElement)node.volume=volume;apply(node);}});
  observer.observe(document.body,{subtree:true,childList:true});
  return ()=>observer.disconnect();
 },[volume]);
 return [volume,setVolume] as const;
}

import React,{useEffect,useMemo,useState} from 'react';
import {useReactFlow} from '@xyflow/react';
import {ChevronLeft,ChevronRight,ChevronUp,ChevronDown,Music2} from 'lucide-react';

type Media={id:string;name:string;kind:string;url:string;deleted?:boolean};
type Dir='left'|'right'|'up'|'down';
const VEC:Record<Dir,[number,number]>={left:[-1,0],right:[1,0],up:[0,-1],down:[0,1]};
const KEYS:Record<string,Dir>={ArrowLeft:'left',ArrowRight:'right',ArrowUp:'up',ArrowDown:'down'};
const ICON={left:ChevronLeft,right:ChevronRight,up:ChevronUp,down:ChevronDown};
const LABEL={left:'左',right:'右',up:'上',down:'下'};
const nodeAsset=(n:any)=>n.data?.asset_id||n.data?.output_id;

/** Arrow-key / edge-button navigation between nearby media nodes while the
 *  enlarged viewer is open. Only computed while the viewer is shown. */
export function ModalNav({asset,nodes,assets,onOpen}:{asset:Media;nodes:any[];assets:Media[];onOpen:(a:any)=>void}){
  const flow=useReactFlow();
  const [current,setCurrent]=useState<string|null>(null);
  const byId=useMemo(()=>new Map(assets.map(a=>[a.id,a])),[assets]);
  // Resolve which node the viewer belongs to (prefer the selected one when the same asset appears twice).
  const currentId=useMemo(()=>{
    const match=(n:any)=>nodeAsset(n)===asset.id;
    if(current&&nodes.some(n=>n.id===current&&match(n)))return current;
    return (nodes.find(n=>n.selected&&match(n))||nodes.find(match))?.id||null;
  },[current,nodes,asset.id]);
  const targets=useMemo(()=>{
    const out:Partial<Record<Dir,{id:string;asset:Media}>>={};
    if(!currentId)return out;
    const center=(id:string)=>{const n=flow.getInternalNode(id);if(!n)return null;const p=n.internals.positionAbsolute,w=n.measured?.width??n.width??0,h=n.measured?.height??n.height??0;return {x:p.x+w/2,y:p.y+h/2};};
    const origin=center(currentId);if(!origin)return out;
    const items=nodes.flatMap(n=>{if(n.id===currentId||n.hidden)return [];const a=byId.get(nodeAsset(n));if(!a||a.deleted||a.kind==='model')return [];const c=center(n.id);return c?[{id:n.id,asset:a,c}]:[];});
    (Object.keys(VEC) as Dir[]).forEach(dir=>{
      const [vx,vy]=VEC[dir];let best:any=null,score=Infinity;
      for(const it of items){const dx=it.c.x-origin.x,dy=it.c.y-origin.y,main=dx*vx+dy*vy,off=Math.abs(dx*vy-dy*vx);
        if(main<=8||off>main*2)continue;const s=main+off*1.5;if(s<score){score=s;best=it;}}
      if(best)out[dir]={id:best.id,asset:best.asset};
    });
    return out;
  },[currentId,nodes,byId,flow]);
  // Hand keyboard focus to the viewer's media so Space / controls work right away.
  const focusMedia=()=>window.setTimeout(()=>{const el=['.media-modal .video-play-surface','.media-modal .audio-play','.media-modal'].map(q=>document.querySelector<HTMLElement>(q)).find(Boolean);el?.focus({preventScroll:true});},40);
  useEffect(()=>{focusMedia();},[]);
  const go=(dir:Dir)=>{const t=targets[dir];if(!t)return;setCurrent(t.id);onOpen(t.asset);focusMedia();
    const n=flow.getInternalNode(t.id);if(n){const p=n.internals.positionAbsolute;flow.setCenter(p.x+(n.measured?.width??0)/2,p.y+(n.measured?.height??0)/2,{zoom:flow.getZoom()});}};
  useEffect(()=>{
    const onKey=(e:KeyboardEvent)=>{const dir=KEYS[e.key];if(!dir||e.altKey||e.ctrlKey||e.metaKey)return;
      const el=e.target as HTMLElement|null;if(el?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
      if(!targets[dir])return;e.preventDefault();e.stopPropagation();go(dir);};
    window.addEventListener('keydown',onKey,true);return ()=>window.removeEventListener('keydown',onKey,true);
  });
  return <>{(Object.keys(VEC) as Dir[]).map(dir=>{const t=targets[dir];if(!t)return null;const Icon=ICON[dir];
    return <button key={dir} className={'modal-nav nav-'+dir} title={`${LABEL[dir]}方節點：${t.asset.name}（方向鍵）`} aria-label={`前往${LABEL[dir]}方節點 ${t.asset.name}`} onMouseDown={e=>e.preventDefault()} onClick={e=>{e.stopPropagation();go(dir);}}>
      <Icon size={18}/>
      <span className="modal-nav-thumb">{t.asset.kind==='image'?<img src={t.asset.url} alt="" loading="lazy" draggable={false}/>:t.asset.kind==='video'?<video src={t.asset.url+'#t=0.1'} muted preload="metadata" playsInline/>:<Music2 size={16}/>}</span>
      <span className="modal-nav-name">{t.asset.name}</span>
    </button>;})}</>;
}

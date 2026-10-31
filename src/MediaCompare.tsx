import React,{useEffect,useRef,useState} from 'react';
import {X,Columns2,SlidersHorizontal,Play,Pause,ArrowLeftRight} from 'lucide-react';
import './MediaArchive.css';
export type CompareAsset={id:string;name:string;kind:string;url:string;thumbnail_url?:string};
const time=(n:number)=>`${Math.floor(n/60).toString().padStart(2,'0')}:${(n%60).toFixed(3).padStart(6,'0')}`;
export function CompareView({items,onClose,embedded=false}: {items:CompareAsset[];onClose:()=>void;embedded?:boolean}){
 const [sound,setSound]=useState('a');
 const [swap,setSwap]=useState(false),[mode,setMode]=useState('split'),[position,setPosition]=useState(50),[playing,setPlaying]=useState(false),[clock,setClock]=useState(0),[length,setLength]=useState(0),[error,setError]=useState('');
 const videos=useRef<(HTMLVideoElement|null)[]>([]),stage=useRef<HTMLDivElement>(null);const pair=swap?[items[1],items[0]]:items;
 function pause(){videos.current.forEach(v=>v?.pause());setPlaying(false);}
 function seek(n:number){videos.current.forEach(v=>{if(v&&Number.isFinite(v.duration))v.currentTime=Math.min(n,v.duration);});setClock(n);}
 function loaded(){const all=videos.current.filter(Boolean) as HTMLVideoElement[];const durations=all.map(v=>v.duration).filter(Number.isFinite);setLength(durations.length?Math.min(...durations):0);}
 async function play(){setError('');if(clock>=length)seek(0);try{await Promise.all(videos.current.filter(Boolean).map(v=>v!.play()));setPlaying(true);}catch{pause();setError('瀏覽器無法播放其中一段影片，可能需要轉換編碼。');}}
 function tick(index:number){const master=videos.current.findIndex(Boolean);if(index!==master)return;const v=videos.current[index];if(!v)return;setClock(v.currentTime);videos.current.forEach((other,i)=>{if(other&&i!==index&&Math.abs(other.currentTime-v.currentTime)>.12)other.currentTime=v.currentTime;});if(length&&v.currentTime>=length)pause();}
 useEffect(()=>{const stop=(e:KeyboardEvent)=>{if(!embedded&&e.key==='Escape')onClose();};window.addEventListener('keydown',stop);return()=>{window.removeEventListener('keydown',stop);videos.current.forEach(v=>v?.pause());};},[]);
 function drag(e:React.PointerEvent){const r=stage.current?.getBoundingClientRect();if(r)setPosition(Math.max(0,Math.min(100,(e.clientX-r.left)/r.width*100)));}
 return <div className={"compare-overlay"+(embedded?" compare-embedded nodrag nowheel":"")} role={embedded?"region":"dialog"} aria-modal={embedded?undefined:true} aria-label="素材比較"><header><div><strong>素材比較</strong><small>A / B · 同步時間軸</small></div><nav><button className={mode==='split'?'active':''} onClick={()=>setMode('split')}><Columns2 size={16}/>並排</button><button className={mode==='wipe'?'active':''} onClick={()=>setMode('wipe')}><SlidersHorizontal size={16}/>直桿比較</button><button onClick={()=>{pause();setSwap(!swap);seek(0);}}><ArrowLeftRight size={16}/>交換</button>{!embedded&&<button onClick={onClose} aria-label="關閉比較"><X/></button>}</nav></header>
 <div className="compare-labels"><span>A · {pair[0].name}</span><span>B · {pair[1].name}</span></div>
 <div className={'compare-stage '+mode} ref={stage}>
 {pair.map((a,i)=><div key={a.id+':'+i} className={'compare-layer layer-'+i} style={mode==='wipe'&&i===1?{clipPath:`inset(0 0 0 ${position}%)`}:undefined}>{a.kind==='image'?<img src={a.url} alt={a.name}/>:<video ref={el=>{videos.current[i]=el;}} src={a.url} muted={sound!=='both'&&sound!==(i===0?'a':'b')} playsInline preload="metadata" onLoadedMetadata={loaded} onTimeUpdate={()=>tick(i)} onEnded={pause} onError={()=>setError('無法播放 '+a.name+'，請檢查檔案及瀏覽器編碼支援。')}/>}</div>)}
 {mode==='wipe'&&<button className="compare-divider" style={{left:position+'%'}} aria-label="拖曳比較分界" onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);drag(e);}} onPointerMove={e=>{if(e.currentTarget.hasPointerCapture(e.pointerId))drag(e);}} onKeyDown={e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setPosition(p=>Math.max(0,Math.min(100,p+(e.key==='ArrowRight'?1:-1))));}}}><span>↔</span></button>}
 </div>
 <footer>{mode==='wipe'&&<label>分界<input aria-label="比較分界" type="range" min={0} max={100} value={position} onChange={e=>setPosition(+e.target.value)}/>{Math.round(position)}%</label>}
 {pair.some(a=>a.kind==='video')&&<div className="compare-transport"><button onClick={()=>playing?pause():play()} aria-label={playing?'暫停比較':'同步播放'}>{playing?<Pause/>:<Play/>}</button><span>{time(clock)} / {time(length)}</span><input aria-label="同步播放位置" type="range" min={0} max={length||1} step={.001} value={Math.min(clock,length||1)} onChange={e=>seek(+e.target.value)}/><select aria-label="比較聲音" value={sound} onChange={e=>setSound(e.target.value)}><option value="a">A 聲音</option><option value="b">B 聲音</option><option value="both">兩者聲音</option><option value="mute">靜音</option></select></div>}
 <p className="help">依共同畫面框等比例顯示，不裁切；滑桿用於比較相同位置。影片同步為瀏覽器預覽，非逐影格精密量測。</p>{error&&<p className="archive-error">{error}</p>}</footer></div>;
}
export function ComparePicker({assets,onClose}: {assets:CompareAsset[];onClose:()=>void}){
 const [ids,setIds]=useState<string[]>([]),[q,setQ]=useState(''),[view,setView]=useState(false);
 const selected=ids.map(id=>assets.find(a=>a.id===id)!).filter(Boolean);
 if(view&&selected.length===2)return <CompareView items={selected} onClose={()=>setView(false)}/>;
 return <div className="compare-overlay compare-picker" role="dialog" aria-modal="true" aria-label="選擇比較素材"><header><div><strong>選擇兩個素材</strong><small>專案中的圖片或影片</small></div><button onClick={onClose} aria-label="關閉"><X/></button></header><input aria-label="搜尋比較素材" placeholder="搜尋名稱…" value={q} onChange={e=>setQ(e.target.value)}/><div className="archive-grid">{assets.filter(a=>['image','video'].includes(a.kind)&&a.name.toLowerCase().includes(q.toLowerCase())).map(a=><button className={'archive-card '+(ids.includes(a.id)?'chosen':'')} key={a.id} onClick={()=>setIds(old=>old.includes(a.id)?old.filter(id=>id!==a.id):old.length<2?[...old,a.id]:[old[0],a.id])}><div className="archive-thumb">{a.kind==='image'?<img src={a.url} alt="" loading="lazy"/>:<video src={a.url} muted preload="metadata"/>}</div><strong>{a.name}</strong><small>{ids.includes(a.id)?'已選 '+(ids.indexOf(a.id)+1):a.kind}</small></button>)}</div><footer><span>已選 {ids.length} / 2</span><button disabled={ids.length!==2} onClick={()=>setView(true)}>開始比較</button></footer></div>;
}

import React,{useEffect,useState} from 'react';
export const formatTime=(ms:number)=>`${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
function TimeField({label,value,max,onChange}:any){
 const [text,setText]=useState(formatTime(value));
 useEffect(()=>setText(formatTime(value)),[value]);
 function commit(){const m=text.match(/^(\d+):([0-5]?\d)(?:\.(\d{1,3}))?$/);if(m){const n=Number(m[1])*60000+Number(m[2])*1000+Number((m[3]||'').padEnd(3,'0'));onChange(Math.min(max,n));}else setText(formatTime(value));}
 return <label>{label}<input aria-label={label} value={text} placeholder="00:00.000" onChange={e=>setText(e.target.value)} onBlur={commit} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();}}/></label>;
}
export function TrimTimeline({start,end,duration,onStart,onEnd}:any){
 return <section className="trim-timeline"><div className="trim-ruler"><span>00:00.000</span><span>{formatTime(duration)}</span></div>
 <div className="trim-track"><div style={{left:`${start/(duration||1)*100}%`,width:`${(end-start)/(duration||1)*100}%`}}/></div>
 <label>起點拉條<input type="range" aria-label="裁剪起點" min={0} max={Math.max(0,end-1)} step={1} value={start} onChange={e=>onStart(Number(e.target.value))}/></label>
 <label>終點拉條<input type="range" aria-label="裁剪終點" min={Math.min(start+1,duration)} max={duration} step={1} value={end} onChange={e=>onEnd(Number(e.target.value))}/></label>
 <div className="advanced-grid"><TimeField label="開始（分:秒.毫秒）" value={start} max={Math.max(0,end-1)} onChange={onStart}/><TimeField label="結束（分:秒.毫秒）" value={end} max={duration} onChange={(v:number)=>onEnd(Math.max(start+1,v))}/></div>
 <p>保留 {formatTime(Math.max(0,end-start))}</p></section>;
}

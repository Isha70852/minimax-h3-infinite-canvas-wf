import React from 'react';
import {NodeResizer} from '@xyflow/react';
import {Clapperboard,Plus,Trash2,Copy,ArrowUp} from 'lucide-react';
import {PromptInput} from './GenerationControls';
export function DirectorNode({id,data,selected,ctx,Usage}:any){
 const ids:string[]=data.segments||[];
 return <article className="canvas-card director-card"><NodeResizer isVisible={selected} minWidth={460} minHeight={320}/>
 <header><Clapperboard size={18}/><span>{data.label}</span><small>實驗功能</small></header>
 <div className="director-body nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
 <p className="help">逐段生成，第二段起自動上傳前段最近成功生成的 MP4，以影格與聲音延續動作。每段提示詞、素材可各自設定；上下文影片不占用參考素材編號。工作流使用 22 影格畫面與 24 影格聲音上下文；去除重疊後片長可能較短。</p>
 {ids.map((child,i)=>{const node=ctx.nodes.find((n:any)=>n.id===child);const runs=ctx.runs.filter((r:any)=>r.node_id===child).sort((a:any,b:any)=>b.created_at-a.created_at);const run=runs[0];const previous=i?ctx.runs.filter((r:any)=>r.node_id===ids[i-1]&&r.status==='success'&&r.outputs?.some((a:any)=>a.kind==='video')).sort((a:any,b:any)=>b.created_at-a.created_at)[0]:null;
 return <section className="director-segment" key={child}><header><strong>第 {i+1} 段 · {node?.data.label||'節點已移除'}</strong><button disabled={!i} title="上移" onClick={()=>{const next=[...ids];[next[i-1],next[i]]=[next[i],next[i-1]];ctx.setSegments(id,next);}}><ArrowUp size={14}/></button><button title="刪除此段與對應畫布節點（已生成素材保留）" onClick={()=>ctx.remove(child)}><Trash2 size={14}/></button></header>
 {node&&<><PromptInput rows={4} value={node.data.spec.prompt} onValueChange={(prompt:string)=>ctx.editSpec(child,{prompt})}/><div className="template-actions"><button onClick={()=>ctx.focusNode(child)}>參數設定</button><button onClick={()=>ctx.pickReferences(child)}>本段素材</button><button onClick={()=>ctx.openAssistant(child)}>AI 撰寫／沿用對話</button><button disabled={i>0&&!previous} onClick={()=>ctx.generateSegment(child,previous?.id)}>生成此段</button></div></>}
 {run&&<><p>{run.stage}{run.error&&' · '+run.error}</p><Usage run={run}/><button onClick={()=>ctx.editSpec(child,{noise_seed:run.seed})}>沿用此 Noise seed</button>{run.outputs?.filter((a:any)=>a.kind==='video').map((a:any)=><video key={a.id} src={a.url} controls preload="metadata"/>)}</>}
 </section>;})}
 <button onClick={()=>ctx.addSegment(id)}><Plus size={16}/>新增一段（沿用前段設定與素材）</button>
 <select aria-label="加入既有影片節點" value="" onChange={e=>{if(e.target.value)ctx.setSegments(id,[...ids,e.target.value]);}}><option value="">加入既有影片生成節點…</option>{ctx.nodes.filter((n:any)=>n.data.kind==='generation'&&!ids.includes(n.id)).map((n:any)=><option key={n.id} value={n.id}>{n.data.label}</option>)}</select>
 </div><footer><button onClick={()=>ctx.duplicate(id)} title="複製導演台"><Copy size={15}/></button><button onClick={()=>ctx.remove(id)} title="移除導演台（片段仍保留）"><Trash2 size={15}/></button></footer></article>;
}

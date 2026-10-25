import React,{useEffect} from 'react';
import {Maximize2,Copy,Trash2,Image as ImageIcon} from 'lucide-react';
import {Handle,Position,NodeResizer,useUpdateNodeInternals} from '@xyflow/react';
import {NumberInput,PromptInput} from './GenerationControls';

export function imageDefaults(definition:any,provider:string){
  return {kind:'image',provider,workflow:definition.id,values:Object.fromEntries(definition.fields.filter((f:any)=>f.type!=='image').map((f:any)=>[f.key,f.default])),image_assets:{},loras:[]};
}

export function ImageNode({id,data,selected,ctx,Media,Usage}:any){
  const updateInternals=useUpdateNodeInternals(),spec=data.image_spec;
  const catalog=ctx.config.image_workflows||[],definition=catalog.find((d:any)=>d.id===spec.workflow);
  useEffect(()=>{updateInternals(id);},[id,selected,spec.workflow,updateInternals]);
  const runs=ctx.runs.filter((r:any)=>r.node_id===id).sort((a:any,b:any)=>b.created_at-a.created_at);
  const active=runs.some((r:any)=>['uploading','submitting','queued','running','downloading','reconnecting'].includes(r.status));
  const output=ctx.assets.find((a:any)=>a.id===data.output_id);
  const update=(change:any)=>ctx.editImage(id,{...spec,...change});
  const inputFields=definition?.fields.filter((f:any)=>['text','image'].includes(f.type))||[];
  function field(f:any){
    if(f.show_when&&!Object.entries(f.show_when).every(([k,v])=>spec.values[k]===v))return null;
    const edge=ctx.edges.find((e:any)=>e.target===id&&e.targetHandle===f.key),source=ctx.nodes.find((n:any)=>n.id===edge?.source);
    const assetId=edge?.data?.asset_id||spec.image_assets?.[f.key]||'',asset=ctx.assets.find((a:any)=>a.id===assetId);
    const set=(value:any)=>update({values:{...spec.values,[f.key]:value}});
    return <div className="audio-field" key={f.key}>
      {['text','image'].includes(f.type)&&<Handle type="target" id={f.key} position={Position.Left} aria-label={f.label+'輸入'}/>}
      <label>{f.label}</label>
      {f.type==='text'&&<><select aria-label={f.label+'文字來源'} value={source?.id||''} onChange={e=>ctx.bindAudio(id,f.key,e.target.value)}><option value="">直接輸入</option>{ctx.nodes.filter((n:any)=>n.data.kind==='text').map((n:any)=><option key={n.id} value={n.id}>{n.data.label} · {(n.data.text||'').slice(0,35)}</option>)}</select><PromptInput rows={4} value={source?.data.text??spec.values[f.key]??''} disabled={!!source} onValueChange={set}/></>}
      {f.type==='image'&&<><select aria-label={f.label} value={assetId} onChange={e=>{ctx.bindAudio(id,f.key,'');update({image_assets:{...spec.image_assets,[f.key]:e.target.value}});}}><option value="">{f.optional?'不使用':'選擇專案圖片或連接圖片節點'}</option>{ctx.assets.filter((a:any)=>a.kind==='image'&&!a.deleted).map((a:any)=><option key={a.id} value={a.id}>{a.name}</option>)}</select>{asset&&<img className="image-input-preview" src={asset.url} alt={asset.name}/>}</>}
      {f.type==='string'&&<input aria-label={f.label} value={spec.values[f.key]??f.default} onChange={e=>set(e.target.value)}/>}
      {f.type==='select'&&<select aria-label={f.label} value={spec.values[f.key]??f.default} onChange={e=>set(e.target.value)}>{f.options.map((v:string)=><option key={v}>{v}</option>)}</select>}
      {f.type==='boolean'&&<select value={String(spec.values[f.key]??f.default)} onChange={e=>set(e.target.value==='true')}><option value="true">True · 沿用圖片大小</option><option value="false">False · 自訂大小</option></select>}
      {['number','integer'].includes(f.type)&&<NumberInput aria-label={f.label} value={spec.values[f.key]??f.default} min={f.min} max={f.max} step={f.step||1} onValueChange={set}/>}
    </div>;
  }
  return <article className={'canvas-card asset image-generation '+(selected?'is-selected':'')}>
    <NodeResizer isVisible={selected} minWidth={320} minHeight={220}/>
    {!selected&&inputFields.map((f:any,i:number)=><Handle key={f.key} type="target" id={f.key} position={Position.Left} style={{top:65+i*32}} title={f.label}/>)}
    <header><span className="node-icon"><ImageIcon size={15}/></span><span>{data.label}</span><small>IMAGE</small></header>
    <div className="card-media" onDoubleClick={()=>output&&ctx.preview(output)}>{output?<><Media asset={output}/><button className="expand nodrag" title="放大查看" onClick={()=>ctx.preview(output)}><Maximize2 size={17}/></button></>:<div className="generation-placeholder"><strong>{definition?.name}</strong><span>{active?'圖片生成中…':'選取節點，設定輸入後生成'}</span></div>}</div>
    {selected&&<div className="node-composer audio-composer nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
      <div className="composer-fields"><label>功能<select aria-label="圖片生成功能" value={spec.workflow} onChange={e=>ctx.resetImage(id,imageDefaults(catalog.find((d:any)=>d.id===e.target.value),spec.provider))}>{catalog.map((d:any)=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>運算服務<select value={spec.provider} onChange={e=>update({provider:e.target.value})}><option value="runninghub">RunningHub</option><option value="comfyui">本機 ComfyUI</option></select></label></div>
      {definition?.fields.filter((f:any)=>!f.advanced).map(field)}
      {definition?.supports_lora&&<details onToggle={()=>updateInternals(id)}><summary>高級功能 · LoRA 與採樣</summary>
        <p className="help">LoRA 依清單順序載入；空白或未啟用會跳過。寬高使用 16 的倍數。</p>
        {(spec.loras||[]).map((l:any,i:number)=><div className="image-lora-row" key={i}><input type="checkbox" aria-label="啟用 LoRA" checked={l.enabled!==false} onChange={e=>update({loras:spec.loras.map((v:any,j:number)=>i===j?{...v,enabled:e.target.checked}:v)})}/><input aria-label="LoRA 檔名" placeholder="LoRA 檔名.safetensors" value={l.name} onChange={e=>update({loras:spec.loras.map((v:any,j:number)=>i===j?{...v,name:e.target.value}:v)})}/><NumberInput aria-label="LoRA strength" value={l.strength} min={-20} max={20} step={.1} onValueChange={(n:number)=>update({loras:spec.loras.map((v:any,j:number)=>i===j?{...v,strength:n}:v)})}/><button onClick={()=>update({loras:spec.loras.filter((_:any,j:number)=>j!==i)})}>移除</button></div>)}
        <button onClick={()=>update({loras:[...(spec.loras||[]),{name:'',strength:1,enabled:true}]})}>＋ 新增 LoRA</button>
        <div className="advanced-grid">{definition.fields.filter((f:any)=>f.advanced).map(field)}</div>
      </details>}
      <div className="composer-submit"><button onClick={()=>ctx.duplicate(id)}>複製</button><button onClick={()=>ctx.remove(id)}>移除節點</button><button disabled={active} className="primary" onClick={()=>ctx.generate(id)}>{active?'生成中…':'生成圖片'}</button></div>
      {runs[0]&&<><p>{runs[0].stage}{runs[0].progress!=null?' · '+runs[0].progress+'%':''}</p><Usage run={runs[0]}/>{runs[0].error&&<p className="error-message">{runs[0].error}</p>}</>}
      {!!runs.length&&<details><summary>生成歷史（{runs.length}）</summary>{runs.map((r:any)=><div className="audio-history" key={r.id}><p>{new Date(r.created_at*1000).toLocaleString()} · {r.stage}</p>{r.outputs.map((a:any)=><div key={a.id}><img className="image-input-preview" src={a.url} alt={a.name} onClick={()=>ctx.preview(a)}/><button onClick={()=>ctx.audioOutput(id,a.id)}>顯示此版本</button><a href={a.url} download={a.name}>下載</a></div>)}<button onClick={()=>ctx.resetImage(id,r.spec)}>套用此版參數</button></div>)}</details>}
    </div>}
    {selected&&<footer className="nodrag"><button title="複製節點與連線" onClick={()=>ctx.duplicate(id)}><Copy size={14}/></button><button title="移除節點" onClick={()=>ctx.remove(id)}><Trash2 size={14}/></button><span/><small>圖片生成</small></footer>}
    <Handle type="source" position={Position.Right} isConnectable={!!output} aria-label="圖片輸出"/>
  </article>;
}

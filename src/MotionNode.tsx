import {CancelRun} from './CancelRun';
import {ProviderSelect} from './ProviderSettings';
import {NodeName,NumberInput,PromptInput} from './GenerationControls';
import {TemplateBar} from './NodeTemplates';
import React,{useEffect} from 'react';
import {Maximize2,Copy,Trash2,PersonStanding} from 'lucide-react';
import {Handle,Position,NodeResizer,useUpdateNodeInternals} from '@xyflow/react';

const MEDIA=['image','video'];
export function motionDefaults(definition:any,provider:string){
  return {kind:'motion',provider,workflow:definition.id,values:Object.fromEntries(definition.fields.filter((f:any)=>!['text',...MEDIA].includes(f.type)).map((f:any)=>[f.key,f.default])),media_assets:{}};
}

export function MotionNode({id,data,selected,ctx,Media,Usage}:any){
  const updateInternals=useUpdateNodeInternals(),spec=data.motion_spec;
  const catalog=ctx.config.motion_workflows||[],definition=catalog.find((d:any)=>d.id===spec.workflow);
  useEffect(()=>{updateInternals(id);},[id,selected,spec.workflow,updateInternals]);
  const runs=ctx.runs.filter((r:any)=>r.node_id===id).sort((a:any,b:any)=>b.created_at-a.created_at);
  const active=runs.some((r:any)=>['uploading','submitting','queued','running','downloading','reconnecting'].includes(r.status));
  const output=ctx.assets.find((a:any)=>a.id===data.output_id);
  const update=(change:any)=>ctx.editMotion(id,{...spec,...change});
  const inputFields=definition?.fields.filter((f:any)=>['text',...MEDIA].includes(f.type))||[];
  const visible=(f:any)=>!f.show_when||Object.entries(f.show_when).every(([k,v])=>(spec.values[k]??definition.fields.find((x:any)=>x.key===k)?.default)===v);
  function field(f:any){
    if(!visible(f))return null;
    const edge=ctx.edges.find((e:any)=>e.target===id&&e.targetHandle===f.key),source=ctx.nodes.find((n:any)=>n.id===edge?.source);
    const assetId=edge?.data?.asset_id||spec.media_assets?.[f.key]||'',asset=ctx.assets.find((a:any)=>a.id===assetId);
    const value=spec.values[f.key]??f.default;
    const set=(next:any)=>update({values:{...spec.values,[f.key]:next}});
    return <div className="audio-field" key={f.key}>
      {['text',...MEDIA].includes(f.type)&&<Handle type="target" id={f.key} position={Position.Left} aria-label={f.label+'輸入'}/>}
      <label>{f.label}</label>
      {f.type==='text'&&<><select aria-label={f.label+'文字來源'} value={source?.id||''} onChange={e=>ctx.bindAudio(id,f.key,e.target.value)}><option value="">直接輸入</option>{ctx.nodes.filter((n:any)=>n.data.kind==='text').map((n:any)=><option key={n.id} value={n.id}>{n.data.label} · {(n.data.text||'').slice(0,35)}</option>)}</select><PromptInput rows={3} value={source?.data.text??value??''} disabled={!!source} onValueChange={set}/></>}
      {MEDIA.includes(f.type)&&<><select aria-label={f.label} value={assetId} onChange={e=>{ctx.bindAudio(id,f.key,'');update({media_assets:{...spec.media_assets,[f.key]:e.target.value}});}}><option value="">{f.type==='image'?'選擇專案圖片或連接圖片節點':'選擇專案影片或連接影片節點'}</option>{ctx.assets.filter((a:any)=>a.kind===f.type&&!a.deleted).map((a:any)=><option key={a.id} value={a.id}>{a.name}</option>)}</select>{asset&&(f.type==='image'?<img className="image-input-preview" src={asset.url} alt={asset.name}/>:<video className="image-input-preview" src={asset.url} muted controls preload="metadata"/>)}</>}
      {f.type==='string'&&<input aria-label={f.label} value={value} onChange={e=>set(e.target.value)}/>}
      {f.type==='select'&&<select aria-label={f.label} value={value} onChange={e=>set(e.target.value)}>{f.options.map((v:string)=><option key={v} value={v}>{f.option_labels?.[v]||v}</option>)}</select>}
      {f.type==='boolean'&&<select aria-label={f.label} value={String(value)} onChange={e=>set(e.target.value==='true')}><option value="true">開啟</option><option value="false">關閉</option></select>}
      {['number','integer'].includes(f.type)&&<NumberInput aria-label={f.label} value={value} min={f.min} max={f.max} step={f.step||1} onValueChange={set}/>}
    </div>;
  }
  return <article className={'canvas-card asset image-generation motion-generation '+(selected?'is-selected':'')}>
    <NodeResizer isVisible={selected} minWidth={320} minHeight={220}/>
    {!selected&&inputFields.map((f:any,i:number)=><Handle key={f.key} type="target" id={f.key} position={Position.Left} style={{top:65+i*32}} title={f.label}/>)}
    <header><span className="node-icon"><PersonStanding size={15}/></span><NodeName value={data.label} onChange={(name:string)=>ctx.rename(id,name)}/><small>MOTION</small></header>
    <div className="card-media" onDoubleClick={()=>output&&ctx.preview(output)}>{output?<><Media asset={output} hover controls/><button className={"expand nodrag"+(output.kind==='video'?' video-expand':'')} title="放大查看" onClick={()=>ctx.preview(output)}><Maximize2 size={17}/></button></>:<div className="generation-placeholder"><strong>{definition?.name||'動作遷移'}</strong><span>{active?'動作遷移生成中…':'連接參考圖片與動作影片後生成'}</span></div>}</div>
    {selected&&definition&&<div className="node-composer audio-composer nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
      <TemplateBar category={'motion'} spec={spec} onApply={(next:any)=>next.workflow!==spec.workflow?ctx.resetMotion(id,next):ctx.editMotion(id,next)}/>
      <div className="composer-fields"><label>功能<select aria-label="動作遷移功能" value={spec.workflow} onChange={e=>ctx.resetMotion(id,{...motionDefaults(catalog.find((d:any)=>d.id===e.target.value),spec.provider),provider:spec.provider,provider_profile_id:spec.provider_profile_id})}>{catalog.map((d:any)=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>運算服務<ProviderSelect config={ctx.config} spec={spec} onChange={update}/></label></div>
      {definition.fields.filter((f:any)=>!f.advanced).map(field)}
      <details onToggle={()=>updateInternals(id)}><summary>高級功能 · 模型、採樣與遮罩</summary>
        <p className="help">預設為加速版（Distill LoRA、6 步、CFG 1）。人物替換保留影片背景；動作遷移保留參考圖背景。長影片每段 81 幀、重疊 5 幀接續。</p>
        <div className="advanced-grid">{definition.fields.filter((f:any)=>f.advanced).map(field)}</div>
      </details>
      <div className="composer-submit"><CancelRun id={id} ctx={ctx}/><button onClick={()=>ctx.duplicate(id)}>複製</button><button onClick={()=>ctx.remove(id)}>移除節點</button><button disabled={active} className="primary" onClick={()=>ctx.generate(id)}>{active?'生成中…':'生成影片'}</button></div>
      {runs[0]&&<><p>{runs[0].stage}{runs[0].progress!=null?' · '+runs[0].progress+'%':''}{runs[0].compiled?.segments?' · '+runs[0].compiled.segments.length+' 段':''}</p><Usage run={runs[0]}/>{runs[0].error&&<p className="error-message">{runs[0].error}</p>}</>}
      {!!runs.length&&<details><summary>生成歷史（{runs.length}）</summary>{runs.map((r:any)=><div className="audio-history" key={r.id}><p>{new Date(r.created_at*1000).toLocaleString()} · {r.stage}</p>{r.outputs.map((a:any)=><div key={a.id}><video className="image-input-preview" src={a.url} controls preload="metadata" onDoubleClick={()=>ctx.preview(a)}/><button onClick={()=>ctx.audioOutput(id,a.id)}>顯示此版本</button><a href={a.url} download={a.name}>下載</a></div>)}<button onClick={()=>ctx.resetMotion(id,r.spec)}>套用此版參數</button></div>)}</details>}
    </div>}
    {<footer className={"nodrag "+(!selected?"node-details-hidden":"")}><button title="複製節點與連線" onClick={()=>ctx.duplicate(id)}><Copy size={14}/></button><button title="移除節點" onClick={()=>ctx.remove(id)}><Trash2 size={14}/></button><span/><small>動作遷移</small></footer>}
    <Handle type="source" position={Position.Right} isConnectable={!!output} aria-label="影片輸出"/>
  </article>;
}

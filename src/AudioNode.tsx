import {TemplateBar} from './NodeTemplates';
import {AudioPlayer} from './AudioPlayer';
import {Copy,Trash2,Music2} from 'lucide-react';
import React,{useEffect} from 'react';
import {Handle,Position,NodeResizer,useUpdateNodeInternals} from '@xyflow/react';
import {NumberInput,PromptInput} from './GenerationControls';

export function AudioNode({id,data,selected,ctx,Media,Usage}:any) {
  const updateInternals=useUpdateNodeInternals();
  useEffect(()=>{updateInternals(id);},[id,selected,data.audio_spec.workflow,updateInternals]);
  const spec=data.audio_spec, catalog=ctx.config.audio_workflows||[];
  const definition=catalog.find((d:any)=>d.id===spec.workflow);
  const runs=ctx.runs.filter((r:any)=>r.node_id===id), active=runs.some((r:any)=>['uploading','submitting','queued','running','downloading','reconnecting'].includes(r.status));
  const output=ctx.assets.find((a:any)=>a.id===data.output_id);
  function update(values:any){ctx.editAudio(id,{...spec,...values});}
  return <article className={'canvas-card audio-generation compact-audio '+(selected?'is-selected':'')}>
    <NodeResizer isVisible={selected} minWidth={320} minHeight={136} maxHeight={136}/>
    {!selected&&definition?.fields.filter((f:any)=>['text','audio'].includes(f.type)).map((f:any,i:number)=><Handle key={f.key} type="target" id={f.key} position={Position.Left} style={{top:45+i*18}} title={f.label+' 輸入'} aria-label={f.label+' 輸入'}/>)}
    <header><Music2 size={15}/><span>{data.label}</span><small>{data.kind==='music'?'MUSIC':'TTS'}</small></header>
    <div className="card-media">{output?<Media asset={output} controls/>:<div className="generation-placeholder"><span>{active?'聲音生成中…':definition?.name+' · 選取後設定'}</span></div>}</div>
    {selected&&<div className="node-composer audio-composer nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
      <TemplateBar category={data.kind} spec={spec} onApply={(next:any)=>next.workflow!==spec.workflow?ctx.resetAudio(id,next):ctx.editAudio(id,next)}/>
      <div className="composer-fields"><label>功能<select aria-label="音訊生成功能" value={spec.workflow} onChange={e=>{const d=catalog.find((d:any)=>d.id===e.target.value);ctx.resetAudio(id,{kind:'audio',provider:spec.provider,workflow:d.id,values:Object.fromEntries(d.fields.filter((f:any)=>f.type!=='audio').map((f:any)=>[f.key,f.default??''])),audio_asset_id:null});}}>{catalog.filter((d:any)=>d.category===data.kind).map((d:any)=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>運算服務<select value={spec.provider} onChange={e=>update({provider:e.target.value})}><option value="runninghub">RunningHub</option><option value="comfyui">本機 ComfyUI</option></select></label></div>
      {definition?.fields.map((field:any)=>{
        const edge=ctx.edges.find((e:any)=>e.target===id&&e.targetHandle===field.key);
        const source=ctx.nodes.find((n:any)=>n.id===edge?.source);
        const audioId=edge?.data?.asset_id||spec.audio_assets?.[field.key]||(field.key==='audio'?spec.audio_asset_id:null)||'';
        return <div className="audio-field" key={field.key}>
          {['text','audio'].includes(field.type)&&<Handle type="target" id={field.key} position={Position.Left} title={field.label+' 輸入'} aria-label={field.label+' 輸入'}/>}
          <label>{field.label}</label>
          {field.type==='text'&&<><select aria-label={field.label+'文字來源'} value={source?.id||''} onChange={e=>ctx.bindAudio(id,field.key,e.target.value)}><option value="">直接輸入</option>{ctx.nodes.filter((n:any)=>n.data.kind==='text').map((n:any)=><option key={n.id} value={n.id}>{n.data.label} · {(n.data.text||'').slice(0,35)}</option>)}</select><PromptInput aria-label={field.label} key={source?.id||'direct'} rows={field.key==='lyrics'?7:3} value={source?source.data.text:spec.values[field.key]??''} disabled={!!source} onValueChange={(text:string)=>update({values:{...spec.values,[field.key]:text}})}/></>}
          {field.type==='audio'&&<><select aria-label={field.label} value={audioId} onChange={e=>{ctx.bindAudio(id,field.key,'');const audio_assets={...spec.audio_assets};if(e.target.value)audio_assets[field.key]=e.target.value;else delete audio_assets[field.key];update({audio_assets,...(field.key==='audio'?{audio_asset_id:e.target.value||null}:{})});}}><option value="">{field.fallback?'未指定：沿用第一個參考聲音':'選擇專案聲音素材，或連接聲音節點'}</option>{ctx.assets.filter((a:any)=>a.kind==='audio'&&!a.deleted).map((a:any)=><option key={a.id} value={a.id}>{a.name}</option>)}</select>{audioId&&ctx.assets.find((a:any)=>a.id===audioId)&&<AudioPlayer src={ctx.assets.find((a:any)=>a.id===audioId).url}/>}<small>{field.fallback?'控制語氣與情緒；未指定時使用第一個參考音訊。':'可從專案素材上傳音檔，生成的音樂／語音也可選用。'}</small></>}
          {field.type==='select'&&<select aria-label={field.label} value={spec.values[field.key]??field.default} onChange={e=>update({values:{...spec.values,[field.key]:e.target.value}})}>{field.options.map((o:string)=><option key={o}>{o}</option>)}</select>}
          {field.type==='number'&&<NumberInput aria-label={field.label} value={spec.values[field.key]??field.default} min={field.min} max={field.max} step={0.05} onValueChange={(n:number)=>update({values:{...spec.values,[field.key]:n}})}/>}
        </div>;
      })}
      <p className="help">只覆寫上方輸入，其餘參數保持工作流原值。</p>
      <div className="composer-submit"><button onClick={()=>ctx.duplicate(id)}>複製節點</button><button onClick={()=>ctx.remove(id)}>移除節點</button><button className="primary" disabled={active} onClick={()=>ctx.generate(id)}>{active?'生成中…':'生成聲音'}</button></div>
      {runs[0]&&<><p>{runs[0].stage}{runs[0].progress!=null?' · '+runs[0].progress+'%':''}</p><Usage run={runs[0]}/>{runs[0].error&&<p className="error-message">{runs[0].error}</p>}</>}
      {!!runs.length&&<details><summary>生成歷史（{runs.length}）</summary>{runs.map((r:any)=><div className="audio-history" key={r.id}><p>{new Date(r.created_at*1000).toLocaleString()} · {r.stage}</p>{r.outputs.map((a:any)=><div key={a.id}><AudioPlayer src={a.url}/><a href={a.url} download={a.name}>下載</a><button onClick={()=>ctx.audioOutput(id,a.id)}>顯示此版本</button></div>)}<button onClick={()=>ctx.resetAudio(id,r.spec)}>套用此版參數</button>{r.error&&<p className="error-message">{r.error}</p>}</div>)}</details>}
    </div>}
    <footer className="nodrag"><button title="複製節點與連線" onClick={()=>ctx.duplicate(id)}><Copy size={14}/></button><button title="移除節點" onClick={()=>ctx.remove(id)}><Trash2 size={14}/></button><span/><small>{active?'生成中…':'選取以編輯'}</small></footer>
    <Handle type="source" position={Position.Right} isConnectable={!!output} aria-label="聲音輸出"/>
  </article>;
}

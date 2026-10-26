import React,{createContext,useContext,useState} from 'react';
import {X,Bookmark} from 'lucide-react';
import {VideoDefaults,NumberInput} from './GenerationControls';

export const TemplateContext=createContext<any>({items:[],refresh:()=>{},api:()=>{},notify:()=>{}});
const names:any={video:'影片生成',image:'圖片生成',music:'音樂生成',tts:'TTS 生成'};
export function defaultTemplate(config:any,category:string,spec:any){
  const t=config?.node_templates?.find((t:any)=>t.category===category&&t.is_default);
  return t?mergeTemplate(spec,t.spec):spec;
}
export function mergeTemplate(spec:any,preset:any){
  const changed=spec.workflow&&preset.workflow&&spec.workflow!==preset.workflow;
  return {...(changed?{}:spec),...preset,...(preset.values?{values:{...(!changed?spec.values:{}),...preset.values}}:{})};
}
export function TemplateBar({category,spec,onApply}:any){
  const {items,api,refresh,notify}=useContext(TemplateContext);
  const [name,setName]=useState(''),[tags,setTags]=useState(''),[isDefault,setDefault]=useState(false);
  async function save(){try{await api('/node-templates',{method:'POST',body:JSON.stringify({category,name,tags:tags.split(/[,，]/).map(t=>t.trim()).filter(Boolean),spec,is_default:isDefault})});await refresh();setName('');notify('節點模板已儲存');}catch(e:any){notify(e.message);}}
  return <details className="node-template-bar"><summary><Bookmark size={14}/>節點模板</summary><select aria-label="套用節點模板" value="" onChange={e=>{const t=items.find((t:any)=>t.id===e.target.value);if(t)onApply(mergeTemplate(spec,t.spec));}}><option value="">選擇模板套用…</option>{items.filter((t:any)=>t.category===category).map((t:any)=><option key={t.id} value={t.id}>{t.is_default?'★ ':''}{t.name} {t.tags.map((v:string)=>'#'+v).join(' ')}</option>)}</select><div className="composer-fields"><input aria-label="模板名稱" placeholder="模板名稱" value={name} onChange={e=>setName(e.target.value)}/><input aria-label="模板標籤" placeholder="標籤，以逗號分隔" value={tags} onChange={e=>setTags(e.target.value)}/></div><label><input type="checkbox" checked={isDefault} onChange={e=>setDefault(e.target.checked)}/>設為此分類預設</label><button disabled={!name.trim()} onClick={save}>將目前參數存成模板</button><p className="help">不包含提示詞、素材與前段影片。套用後仍可調整參數。</p></details>;
}

export function LoraList({value=[],onChange}:any){return <div>{value.map((l:any,i:number)=><div className="image-lora-row" key={i}><input type="checkbox" checked={l.enabled!==false} onChange={e=>onChange(value.map((v:any,j:number)=>i===j?{...v,enabled:e.target.checked}:v))}/><input aria-label="LoRA 檔名" placeholder="LoRA 檔名" value={l.name} onChange={e=>onChange(value.map((v:any,j:number)=>i===j?{...v,name:e.target.value}:v))}/><NumberInput aria-label="LoRA 強度" min={-20} max={20} step={.1} value={l.strength} onValueChange={(n:number)=>onChange(value.map((v:any,j:number)=>i===j?{...v,strength:n}:v))}/><button onClick={()=>onChange(value.filter((_:any,j:number)=>j!==i))}>移除</button></div>)}<button onClick={()=>onChange([...value,{name:'',strength:1,enabled:true}])}>＋ LoRA</button></div>;}

export function TemplateManager({config,videoDefault,onClose}:any){
  const {items,api,refresh,notify}=useContext(TemplateContext);
  const [category,setCategory]=useState('video'),[draft,setDraft]=useState<any>(null);
  const catalog=category==='image'?config.image_workflows:config.audio_workflows?.filter((d:any)=>d.category===category);
  function fresh(workflow?:string){const d=catalog?.find((d:any)=>d.id===workflow)||catalog?.[0];return category==='video'?videoDefault:{kind:category==='image'?'image':'audio',provider:videoDefault.provider,workflow:d.id,values:Object.fromEntries(d.fields.filter((f:any)=>!['text','image','audio'].includes(f.type)).map((f:any)=>[f.key,f.default])),...(category==='image'?{loras:[]}:{})};}
  function patch(spec:any){setDraft({...draft,spec:{...draft.spec,...spec}});}
  async function save(){try{await api('/node-templates'+(draft.id?'/'+draft.id:''),{method:draft.id?'PUT':'POST',body:JSON.stringify(draft)});await refresh();setDraft(null);notify('模板已儲存');}catch(e:any){notify(e.message);}}
  const definition=catalog?.find((d:any)=>d.id===draft?.spec.workflow);
  return <div className="modal-overlay" onClick={onClose}><div className="dialog template-manager" role="dialog" aria-modal="true" aria-label="節點模板管理" onClick={e=>e.stopPropagation()}><header><h2><Bookmark/>節點模板</h2><button onClick={onClose} aria-label="關閉模板管理"><X/></button></header><p className="help">每個分類可建立多個模板及一個預設。新節點會先套用預設；既有節點不會被改寫。AI 可用標籤或 ID 選擇。</p><div className="template-actions">{Object.entries(names).map(([k,v]:any)=><button className={category===k?'active':''} key={k} onClick={()=>{setCategory(k);setDraft(null);}}>{v}</button>)}</div><button onClick={()=>setDraft({category,name:'',tags:[],is_default:false,spec:fresh()})}>＋ 新增模板</button>
    {items.filter((t:any)=>t.category===category).map((t:any)=><div className="template-actions" key={t.id}><strong>{t.is_default?'★ ':''}{t.name}</strong><span>{t.tags.map((v:string)=>'#'+v).join(' ')}</span><button onClick={()=>setDraft(structuredClone(t))}>編輯</button><button onClick={async()=>{try{await api('/node-templates/'+t.id,{method:'PUT',body:JSON.stringify({...t,is_default:!t.is_default})});await refresh();}catch(e:any){notify(e.message);}}}>{t.is_default?'取消預設':'設為預設'}</button><button onClick={async()=>{if(!confirm('刪除模板「'+t.name+'」？'))return;try{await api('/node-templates/'+t.id,{method:'DELETE'});await refresh();if(draft?.id===t.id)setDraft(null);}catch(e:any){notify(e.message);}}}>刪除</button></div>)}
    {draft&&<section className="template-editor"><label>名稱<input value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})}/></label><label>標籤（逗號分隔）<input value={draft.tags.join(',')} onChange={e=>setDraft({...draft,tags:e.target.value.split(/[,，]/)})}/></label><label><input type="checkbox" checked={draft.is_default} onChange={e=>setDraft({...draft,is_default:e.target.checked})}/>設為預設</label>
    {category==='video'?<VideoDefaults config={config} value={draft.spec} onChange={(spec:any)=>setDraft({...draft,spec})}/>:<><label>工作流<select value={draft.spec.workflow} onChange={e=>setDraft({...draft,spec:fresh(e.target.value)})}>{catalog.map((d:any)=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>運算服務<select value={draft.spec.provider} onChange={e=>patch({provider:e.target.value})}><option value="comfyui">本機 ComfyUI</option><option value="runninghub">RunningHub</option></select></label><div className="advanced-grid">{definition?.fields.filter((f:any)=>!['text','audio','image'].includes(f.type)).map((f:any)=>{const value=draft.spec.values[f.key]??f.default;const set=(v:any)=>patch({values:{...draft.spec.values,[f.key]:v}});return <label key={f.key}>{f.label}{f.type==='select'?<select value={value} onChange={e=>set(e.target.value)}>{f.options.map((o:string)=><option key={o}>{o}</option>)}</select>:f.type==='boolean'?<input type="checkbox" checked={!!value} onChange={e=>set(e.target.checked)}/>:['number','integer'].includes(f.type)?<NumberInput value={value} min={f.min??-100000} max={f.max??100000} step={f.step??(f.type==='integer'?1:.1)} onValueChange={set}/>:<input value={value??''} onChange={e=>set(e.target.value)}/>}</label>;})}</div>{definition?.supports_lora&&<LoraList value={draft.spec.loras} onChange={(loras:any)=>patch({loras})}/>}<p className="help">只提供此工作流已映射的參數；不支援 LoRA 的聲音工作流不會顯示 LoRA 設定。</p></>}
    <button className="primary" disabled={!draft.name.trim()} onClick={save}>儲存模板</button><button onClick={()=>setDraft(null)}>取消</button></section>}
  </div></div>;
}

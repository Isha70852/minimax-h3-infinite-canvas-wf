import {PromptInput} from './GenerationControls';
import React, { useEffect, useState } from 'react';

export function PromptPanel({projectId,nodeId,api,getSpec,saveProject,onClose,onApply,requirement,onRequirement,refs,notify,textMode=false,onReuseReferences,onPickReferences,onRemoveReference}:any) {
  const [config,setConfig]=useState<any>(null),[templateId,setTemplateId]=useState(''),[notes,setNotes]=useState('');
  const [templateMode,setTemplateMode]=useState('saved'),[customTemplate,setCustomTemplate]=useState(''),[historyIds,setHistoryIds]=useState<string[]>([]),[history,setHistory]=useState<any[]>([]),[endingNotes,setEndingNotes]=useState('');
  const [includeTemplates,setIncludeTemplates]=useState(true);
  const [jobs,setJobs]=useState<any[]>([]),[active,setActive]=useState<any>(null),[result,setResult]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{api('/prompt-assistant/settings').then((c:any)=>{setConfig({...c,api_key:''});setTemplateId(c.default_template_id||c.templates[0]?.id||'');if(!c.templates.length)setTemplateMode('none');}).catch((e:any)=>notify(e.message));},[]);
  useEffect(()=>{let stop=false; const poll=()=>api('/prompt-assistant/drafts?project_id='+projectId+'&node_id='+nodeId).then((j:any[])=>{if(stop)return;setJobs(j);setActive((a:any)=>{const next=j.find(x=>x.id===a?.id);if(next&&a.status==='running'&&next.status!=='running'){if(next.result)setResult(next.result);if(next.error)notify(next.error);}return next||a||j.find(x=>x.status==='running')||null;});}).catch((e:any)=>{if(!stop)notify(e.message);});poll();const timer=setInterval(poll,4000);return()=>{stop=true;clearInterval(timer);};},[projectId,nodeId]);
  useEffect(()=>{
    if(!active?.id||active.status!=='running')return;
    const stream=new EventSource('/api/prompt-assistant/drafts/'+active.id+'/stream');
    stream.onmessage=event=>{const job=JSON.parse(event.data);setActive((a:any)=>a?.id===job.id?{...a,...job}:a);setResult(job.result??job.partial??'');if(job.status!=='running'){stream.close();if(job.error)notify(job.error);}};
    return()=>stream.close();
  },[active?.id,active?.status]);
  useEffect(()=>{saveProject().then(()=>api('/prompt-assistant/context-options?project_id='+projectId)).then((rows:any[])=>setHistory(rows)).catch((e:any)=>notify(e.message));},[projectId,jobs.length,active?.status]);
  if(!config)return <div className="modal-overlay"><div className="dialog">載入提示詞助手…<button onClick={onClose}>關閉</button></div></div>;
  const template=config.templates.find((t:any)=>t.id===templateId), running=busy||jobs.some(j=>j.status==='running');
  async function request(){
    if(!requirement.trim()){notify('請填寫需求');return;}if(templateMode==='inherit'&&!historyIds.length){notify('請先選擇歷史段落，或改用其他模板');return;}setBusy(true);
    try{await saveProject();const spec=getSpec();const body={target_type:textMode?'text':'video',project_id:projectId,node_id:nodeId,request_id:crypto.randomUUID(),template_id:templateId,template_mode:templateMode,custom_template:customTemplate,history_ids:historyIds,history_include_templates:includeTemplates,ending_notes:endingNotes,requirement,material_notes:notes,spec:{...spec,prompt:spec.prompt||'（尚無提示詞）'}};
      const job=await api('/prompt-assistant/drafts',{method:'POST',body:JSON.stringify(body)});setJobs(j=>[job,...j]);setActive(job);setResult('');
    }catch(e:any){notify(e.message);}finally{setBusy(false);}
  }
  async function apply(submit:boolean){try{const spec=getSpec();if(active?.spec&&JSON.stringify(active.spec.references)!==JSON.stringify(spec.references))throw Error('引用素材已改變，請重新撰寫提示詞，以免人物對應錯誤。');if(!textMode)await api('/workflow/preview',{method:'POST',body:JSON.stringify({...spec,prompt:result})});await onApply(result,submit);onClose();}catch(e:any){notify(e.message);}}
  return <div className="modal-overlay prompt-overlay"><section role="dialog" aria-modal="true" aria-label="AI 提示詞助手" className="prompt-panel">
    <header><div><h2>AI 提示詞助手</h2><p>{textMode?'依使用者要求及引用素材撰寫，套用後成為一般文字內容。':'使用目前節點的引用順序與設定；草稿不會自動覆寫或生成影片。'}</p></div><button onClick={onClose}>關閉</button></header>
    <div className="prompt-panel-body"><div className="prompt-input-column">
<p className="help">AI 來源：{config.provider} · 模型：{config.model||'尚未設定'} · 模板：{template?.name||'尚未設定'}。可至設定面板調整。</p>
      <label>本次模板<select aria-label="本次模板模式" value={templateMode} onChange={e=>setTemplateMode(e.target.value)}><option value="saved">選擇已儲存模板</option><option value="inherit">沿用最後一筆歷史的模板</option><option value="custom">本次自訂模板</option><option value="none">留空，不使用模板</option></select></label>
      {templateMode==='saved'&&<select aria-label="本次模板" value={templateId} onChange={e=>setTemplateId(e.target.value)}>{config.templates.map((t:any)=><option key={t.id} value={t.id}>{t.name}</option>)}</select>}
      {templateMode==='custom'&&<textarea aria-label="本次自訂模板" rows={7} value={customTemplate} onChange={e=>setCustomTemplate(e.target.value)} placeholder="只用於這次，不會覆寫已儲存模板"/>}
      <details className="prompt-history-picker"><summary>加入前段 AI／手動提示詞（可多選 · 已選 {historyIds.length}）</summary><p className="help">依下列順序加入完整歷史輸入與輸出，作為劇情背景，不強制無縫銜接。重複的段落只送一次。</p>
        {historyIds.map((id,i)=>{const row=history.find(r=>r.id===id);return <div className="selected-history" key={id}><span>{i+1}. {row?.requirement?.slice(0,45)||id}</span><button disabled={!i} onClick={()=>setHistoryIds(ids=>{const n=[...ids];[n[i-1],n[i]]=[n[i],n[i-1]];return n;})}>上移</button><button onClick={()=>setHistoryIds(ids=>ids.filter(x=>x!==id))}>移除</button></div>;})}
        <label><input type="checkbox" checked={includeTemplates} onChange={e=>setIncludeTemplates(e.target.checked)}/>附上歷史段落的模板（本次使用的模板仍由上方選擇）</label><p className="help">手動來源包含目前文字／影片節點及影片提交紀錄，會標記為使用者撰寫的前段內容。請在下方使用者要求描述本次變化。</p><div className="history-options">{history.map(row=><div className="history-option" key={row.id}><label><input type="checkbox" checked={historyIds.includes(row.id)} onChange={e=>{setHistoryIds(ids=>e.target.checked?[...ids,row.id]:ids.filter(x=>x!==row.id));}}/><span>{row.source_type==='user_authored'?'手動／節點':'AI'} · {new Date(row.created_at*1000).toLocaleString()} · {row.requirement?.slice(0,65)}</span></label><button onClick={()=>{onReuseReferences?.(row.spec);setNotes(row.material_notes||'');}}>沿用這段素材</button><details><summary>查看輸入與輸出</summary><p>{row.template?.name}</p><pre>{row.requirement}</pre><pre>{row.result}</pre></details></div>)}</div>
      </details>
      <label>結尾／連續性補充（選填）<textarea rows={2} value={endingNotes} onChange={e=>setEndingNotes(e.target.value)} placeholder="只有成片和提示詞不同，或有額外狀態要提醒時才填"/></label>
      <label>使用者要求<PromptInput mentions={refs} aria-label="AI 使用者要求" rows={4} value={requirement} onValueChange={onRequirement} placeholder="角色、事件、動作、對白、風格與想要的結果…"/></label>
      <button onClick={onPickReferences}>選擇／修改本次素材</button><div className="assistant-ref-list">{refs.map((r:any)=><span key={r.edge.id}>{r.tag} · {r.asset.name}<button aria-label={'移除 '+r.asset.name} onClick={()=>onRemoveReference?.(r.edge.id)}>×</button></span>)}</div>
      <label>素材補充說明<textarea value={notes} onChange={e=>setNotes(e.target.value)} placeholder="影片僅提供開頭抽樣影格；音檔不會被聽取。可在此補充動作、聲線、台詞等資訊。" rows={2}/></label>
    </div><div className="prompt-result-column">
      <div className="template-actions"><button className="primary" disabled={running} onClick={()=>request()}>{running?'撰寫中…':'撰寫提示詞'}</button></div>
      <select aria-label="提示詞撰寫紀錄" value={active?.id||''} onChange={e=>{const j=jobs.find(j=>j.id===e.target.value);setActive(j||null);setResult(j?.result||j?.partial||'');}}><option value="">手動貼上 / 新草稿</option>{jobs.map(j=><option key={j.id} value={j.id}>{new Date(j.created_at*1000).toLocaleString()} · {j.provider} · {j.status}</option>)}</select>
      {active&&active.status!=='running'&&<button onClick={async()=>{try{await api('/prompt-assistant/drafts/'+active.id,{method:'DELETE'});setJobs(j=>j.filter(x=>x.id!==active.id));setActive(null);setResult('');}catch(e:any){notify(e.message);}}}>刪除此筆提示詞紀錄</button>}
      {active?.status==='running'&&<p className="help">正在串流輸出…完成後可編輯或套用。</p>}
      {active?.error&&<p className="error-message">{active.error}</p>}{active?.warnings?.map((w:string)=><p className="help" key={w}>{w}</p>)}
      <PromptInput mentions={refs} aria-label="AI 提示詞草稿" className="draft-editor" readOnly={active?.status==='running'} placeholder="模型結果會出現在此；可修改後再套用。" value={result} onValueChange={setResult}/>
      <footer><button disabled={!result.trim()||running} onClick={()=>apply(false)}>套用至節點</button>{!textMode&&<button className="primary" disabled={!result.trim()||running} onClick={()=>apply(true)}>套用並生成影片（使用生成服務額度）</button>}</footer>
    </div></div>
  </section></div>;
}

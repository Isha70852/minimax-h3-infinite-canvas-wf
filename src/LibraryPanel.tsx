import React, { useEffect, useRef, useState } from 'react';

export function LibraryPanel({ projectId, initialScope, referenceMode, selectedIds=[], onClose, onSelect, onChanged, notify, Media, api, onEdit }: any) {
  const [scope, setScope] = useState(initialScope || 'project');
  const [items, setItems] = useState<any[]>([]);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [trash, setTrash] = useState(false);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const refresh = () => api('/assets' + (scope === 'project' ? '?project_id=' + projectId : '')).then(setItems);
  useEffect(() => { refresh().catch((e:any)=>notify(e.message)); }, [scope, projectId]);
  async function change(item:any, values:any) {
    try { const updated = await api('/assets/'+item.id,{method:'PATCH',body:JSON.stringify(values)}); setItems(old=>old.map(a=>a.id===item.id?updated:a)); onChanged(); }
    catch(e:any){notify(e.message);}
  }
  async function upload(files:FileList|null) {
    if(!files)return; setBusy(true);
    try { for(const f of Array.from(files)){const data=new FormData();data.append('file',f);await api('/assets?scope='+scope+(scope==='project'?'&project_id='+projectId:''),{method:'POST',body:data});} await refresh(); onChanged(); notify(scope==='shared'?'已加入跨專案資產庫':'已加入本專案素材'); }
    catch(e:any){notify(e.message);}finally{setBusy(false);if(file.current)file.current.value='';}
  }
  const shown = items.filter(a=>!!a.deleted===trash && (filter==='all'||a.kind===filter) && a.name.toLowerCase().includes(query.toLowerCase())).sort((a,b)=>Number(!!b.favorite)-Number(!!a.favorite)||(b.use_count||0)-(a.use_count||0)||(b.updated_at||0)-(a.updated_at||0));
  return <div className="modal-overlay library-overlay" onClick={onClose}><section className="library-panel" role="dialog" aria-modal="true" aria-label={referenceMode?'選擇專案素材':'素材管理'} onClick={e=>e.stopPropagation()}>
    <header><div><h2>{referenceMode?'從專案素材加入':'素材管理'}</h2><p>{scope==='shared'?'跨專案共用；匯入後會建立專案自己的素材紀錄。':'只顯示目前專案素材。常用收藏與使用較多的素材優先。'}</p></div><button onClick={onClose} aria-label="關閉素材面板">✕</button></header>
    <nav>{!referenceMode && <><button className={scope==='project'?'active':''} onClick={()=>{setScope('project');setTrash(false);}}>專案素材</button><button className={scope==='shared'?'active':''} onClick={()=>{setScope('shared');setTrash(false);}}>共用資產</button></>}<span/><button disabled={busy} onClick={()=>file.current?.click()}>{busy?'上傳中…':scope==='shared'?'上傳共用資產':'從本機上傳'}</button></nav>
    <div className="library-filter"><input aria-label="搜尋素材" placeholder="搜尋素材名稱" value={query} onChange={e=>setQuery(e.target.value)}/>{[['all','全部'],['image','圖片'],['video','影片'],['audio','音檔']].map(([k,label])=><button key={k} className={filter===k?'active':''} onClick={()=>setFilter(k)}>{label}</button>)}{!referenceMode&&<button className={trash?'active':''} onClick={()=>setTrash(!trash)}>回收區</button>}</div>
    <div className="library-grid">{shown.map(item=><article key={item.id} className={"library-tile"+(referenceMode&&selectedIds.includes(item.id)?" is-picked":"")}>
      <button className="library-tile-media" disabled={trash||busy} title={scope==='shared'?'匯入本專案':referenceMode?(selectedIds.includes(item.id)?'取消引用':'加入引用'):'加入畫布'} onClick={async()=>{try{if(scope==='shared'){await api('/projects/'+projectId+'/import/'+item.id,{method:'POST'});onChanged();notify('已匯入專案素材，切換「專案素材」即可選用');}else{onSelect(item);}}catch(e:any){notify(e.message);}}}><Media asset={item}/><span>{scope==='shared'?'＋ 匯入本專案':referenceMode?(selectedIds.includes(item.id)?'✓ 已選取 · 點擊取消':'＋ 加入引用'):'＋ 加入畫布'}</span></button>
      <input key={item.id+item.name} defaultValue={item.name} aria-label={'重新命名 '+item.name} onBlur={e=>{const name=e.target.value.trim();if(name&&name!==item.name)change(item,{name});else e.target.value=item.name;}} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();}}/>
      <footer>{!trash&&onEdit&&<button title="裁切並另存至目前專案" onClick={()=>onEdit(item)}>裁切</button>}<button title="常用優先" aria-pressed={!!item.favorite} onClick={()=>change(item,{favorite:!item.favorite})}>{item.favorite?'★ 常用':'☆ 常用'}</button><span>{item.use_count||0} 次使用</span><button onClick={()=>change(item,{deleted:!item.deleted})}>{trash?'還原':'刪除'}</button>{trash&&<button onClick={async()=>{if(!window.confirm('永久刪除「'+item.name+'」？無法還原，既有節點將無法使用此素材；其他專案獨立匯入的副本保留。'))return;try{await api('/assets/'+item.id+'/permanent?confirm=true',{method:'DELETE'});await refresh();onChanged();}catch(e:any){notify(e.message);}}}>永久刪除</button>}</footer>
    </article>)}{!shown.length&&<p className="library-no-items">{trash?'回收區沒有素材':'尚無符合的素材。可從本機上傳，或到共用資產匯入。'}</p>}</div>
    <footer className="library-panel-footer">刪除會移至回收區，既有畫布與歷史檔案保留。{referenceMode&&` 已選 ${selectedIds.length} 項；再次點擊取消，可連續選取多項。`} {referenceMode&&<button onClick={onClose}>完成選取</button>}</footer>
    <input ref={file} type="file" multiple accept="image/png,image/jpeg,image/webp,video/*,audio/*" hidden onChange={e=>upload(e.target.files)}/>
  </section></div>;
}

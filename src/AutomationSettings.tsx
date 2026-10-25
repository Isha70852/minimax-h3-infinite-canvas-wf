import React, {useEffect,useState} from 'react';
import {createPortal} from 'react-dom';
import {Trees, Github, X} from 'lucide-react';
export function StudioInfo(){
 const [open,setOpen]=useState(false);
 useEffect(()=>{if(!open)return;const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false);};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape);},[open]);
 return <><button className="brand" aria-label="關於 Wizard Forest Studio" onClick={()=>setOpen(true)}><span className="brand-symbol">h3</span><span>CANVAS</span></button>{open&&createPortal(<div className="modal-overlay studio-overlay" onClick={()=>setOpen(false)}><section role="dialog" aria-modal="true" aria-label="Wizard Forest Studio" className="studio-dialog" onClick={e=>e.stopPropagation()}><button autoFocus className="studio-close" title="關閉" onClick={()=>setOpen(false)}><X size={20}/></button><Trees size={42} strokeWidth={1.5}/><h2>Wizard Forest Studio</h2><a href="https://github.com/Isha70852/minimax-h3-infinite-canvas-wf" target="_blank" rel="noopener noreferrer"><Github size={20}/>github</a></section></div>,document.body)}</>;
}
export function AutomationSettings({api,notify}:any){
 const [state,setState]=useState<any>(null),[token,setToken]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{api('/automation/settings').then(setState).catch((e:any)=>notify(e.message));},[]);
 async function update(enabled:boolean,rotate=false){setBusy(true);try{const next=await api('/automation/settings',{method:'PUT',body:JSON.stringify({enabled,rotate_token:rotate})});setState(next);if(next.token)setToken(next.token);}catch(e:any){notify(e.message);}finally{setBusy(false);}}
 return <section className="connection-block"><h3>外部 AI 操作 API</h3><p className="help">供 Codex、Claude Code 等本機工具使用。允許操作專案、上傳素材、撰寫提示詞及提交生成；生成會使用已設定服務的額度。此開關立即儲存。</p>{state&&<><label><input type="checkbox" disabled={busy} checked={state.enabled} onChange={e=>update(e.target.checked)}/>開啟外部操作接口（預設關閉）</label><p><code>{state.base_url}</code></p><button disabled={busy} onClick={()=>update(state.enabled,true)}>重新產生權杖（舊權杖失效）</button>{token&&<label>存取權杖（只在產生時顯示，請交給你授權的工具）<input readOnly value={token} onFocus={e=>e.target.select()}/><button onClick={()=>navigator.clipboard.writeText(token).then(()=>notify('已複製權杖')).catch(()=>notify('請手動複製權杖'))}>複製權杖</button></label>}<p className="help">使用 Authorization: Bearer 權杖。關閉後拒絕新的外部 API 請求，已提交的任務仍繼續。使用說明：專案內 skills/h3-canvas-api/SKILL.md。呼叫期間避免同時編輯同一專案，完成後重新載入專案查看。</p></>}</section>;
}

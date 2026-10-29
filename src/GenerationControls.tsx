import {createPortal} from 'react-dom';
import React, {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';

// Mirror textarea layout so the popup follows the caret even inside a zoomed canvas.
function caretPosition(el:HTMLTextAreaElement, caret:number){
  const mirror=document.createElement('div'), style=getComputedStyle(el);
  for(const key of Array.from(style))mirror.style.setProperty(key,style.getPropertyValue(key));
  Object.assign(mirror.style,{position:'fixed',left:'-10000px',top:'0',transform:'none',width:el.offsetWidth+'px',height:'auto',minHeight:'0',maxHeight:'none',overflow:'visible',whiteSpace:'pre-wrap',overflowWrap:'break-word',visibility:'hidden'});
  mirror.textContent=el.value.slice(0,caret);const marker=document.createElement('span');marker.textContent=el.value.slice(caret)||'​';mirror.append(marker);document.body.append(mirror);
  const r=el.getBoundingClientRect(),sx=r.width/el.offsetWidth,sy=r.height/el.offsetHeight;
  const point={left:r.left+(marker.offsetLeft-el.scrollLeft)*sx,top:r.top+(marker.offsetTop-el.scrollTop+parseFloat(style.lineHeight||'20'))*sy};
  mirror.remove();return point;
}
export const PromptInput = forwardRef<HTMLTextAreaElement, any>(function PromptInput({value,onValueChange,mentions=[],...props}, forwarded) {
  const ref=useRef<HTMLTextAreaElement>(null),composing=useRef(false);
  const [text,setText]=useState(value||''),[caret,setCaret]=useState(0),[focused,setFocused]=useState(false),[dismissed,setDismissed]=useState(false),[choice,setChoice]=useState(0),[point,setPoint]=useState({left:0,top:0});
  const match=text.slice(0,caret).match(/@([^\s@]*)$/);
  const options=match?mentions.filter((m:any)=>(m.alias+' '+(m.asset?.name||'')).includes(match[1])):[];
  const show=focused&&!dismissed&&!props.readOnly&&!props.disabled&&!!match&&options.length>0;
  useImperativeHandle(forwarded,()=>ref.current!);
  useEffect(()=>{if(props.readOnly||document.activeElement!==ref.current)setText(value||'');},[value,props.readOnly]);
  useEffect(()=>{if(!show)return;const update=()=>{if(ref.current){const p=caretPosition(ref.current,caret);setPoint({left:Math.max(8,Math.min(p.left,window.innerWidth-300)),top:Math.max(8,Math.min(p.top+5,window.innerHeight-240))});}};update();window.addEventListener('scroll',update,true);window.addEventListener('resize',update);return()=>{window.removeEventListener('scroll',update,true);window.removeEventListener('resize',update);};},[show,text,caret]);
  function insert(m:any){if(!match)return;const start=caret-match[0].length,insert='@'+m.alias+' ',next=text.slice(0,start)+insert+text.slice(caret);setText(next);onValueChange(next,start+insert.length);setCaret(start+insert.length);setDismissed(true);requestAnimationFrame(()=>{ref.current?.focus();ref.current?.setSelectionRange(start+insert.length,start+insert.length);});}
  return <><textarea {...props} ref={ref} value={text} onFocus={()=>setFocused(true)} onSelect={e=>setCaret(e.currentTarget.selectionStart)}
    onCompositionStart={()=>{composing.current=true;}} onCompositionEnd={e=>{composing.current=false;onValueChange(e.currentTarget.value,e.currentTarget.selectionStart);}}
    onChange={e=>{setCaret(e.target.selectionStart);setText(e.target.value);setDismissed(false);setChoice(0);if(!composing.current)onValueChange(e.target.value,e.target.selectionStart);}}
    onBlur={e=>{setFocused(false);if(e.currentTarget.value!==value)onValueChange(e.currentTarget.value,e.currentTarget.selectionStart);}}
    onKeyDown={e=>{e.stopPropagation();if(!show||composing.current)return;if(e.key==='Escape'){setDismissed(true);e.preventDefault();}else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setChoice(i=>(i+(e.key==='ArrowDown'?1:-1)+options.length)%options.length);}else if(e.key==='Enter'||e.key==='Tab'){e.preventDefault();insert(options[Math.min(choice,options.length-1)]);}}}/>
    {show&&createPortal(<div className="mention-popup nodrag nowheel" role="listbox" aria-label="引用素材" style={{left:point.left,top:point.top}} onWheel={e=>e.stopPropagation()} onPointerDown={e=>e.stopPropagation()}>{options.map((m:any,i:number)=><button type="button" role="option" aria-selected={i===choice} key={m.alias} onMouseDown={e=>e.preventDefault()} onClick={()=>insert(m)}>{m.asset?.kind==='image'?<img src={m.asset.url} alt=""/>:m.asset?.kind==='video'?<video src={m.asset.url} muted preload="metadata"/>:<span className="mention-audio">♫</span>}<span><strong>{m.role==='first'?'首幀 · ':m.role==='last'?'尾幀 · ':''}@{m.alias}</strong><small>{m.asset?.name}</small></span></button>)}</div>,document.body)}</>;
});

export function NumberInput({value,onValueChange,min,max,step=1,...props}:any) {
  const ref=useRef<HTMLInputElement>(null),[text,setText]=useState(String(value??''));
  useEffect(()=>{if(document.activeElement!==ref.current)setText(String(value??''));},[value]);
  const valid=(s:string)=>s.trim()!==''&&Number.isFinite(Number(s))&&Number(s)>=min&&Number(s)<=max;
  return <input {...props} ref={ref} type="number" min={min} max={max} step={step} value={text}
    onFocus={e=>e.target.select()} onKeyDown={e=>e.stopPropagation()}
    onChange={e=>{setText(e.target.value);if(valid(e.target.value))onValueChange(Number(e.target.value));}}
    onBlur={()=>{if(!valid(text))setText(String(value));else {setText(String(Number(text)));onValueChange(Number(text));}}}/>;
}

export const SPECIAL_LORA='minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors';
export function modelSelection(name:string, config:any) {
  const profile=config.model_profiles?.find((p:any)=>p.name===name);
  // Built-in defaults retain the LoRA's shift policy. Custom models carry their own defaults.
  const builtin=['minimax_h3_fl2va_int8_convrot.safetensors','minimax_h3_hybrid_fl2va_ref2va_b25-49-int8_r.safetensors'].includes(name);
  return {model:name,shift_enabled:builtin?null:!!profile?.shift_enabled,shift_video:profile?.shift_video??6,shift_audio:profile?.shift_audio??3};
}

export function AdvancedSettings({spec,config,onChange,driveAudio}:any) {
  const enabled=spec.lora_enabled!==false;
  const shift=spec.shift_enabled??(spec.lora===SPECIAL_LORA);
  const loras=Array.from(new Set([...(config.loras||[]),spec.lora].filter(Boolean))) as string[];
  return <details className="advanced-settings nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
    <summary>高級功能 · LoRA、Shift、採樣與顯存</summary>
    <div className="advanced-body">
      {spec.provider==='runninghub'&&<label>本次運算機型<select value={spec.instance_type??''} onChange={e=>onChange({instance_type:e.target.value||null})}><option value="">沿用設定</option><option value="default">Standard · 24 GB</option><option value="plus">Plus · 48 GB</option><option value="ultra">Ultra · 96 GB</option></select></label>}
      <label>Audio mode<select value={spec.audio_mode??'native'} onChange={e=>onChange({audio_mode:e.target.value})}>{['native','reference_only','lock_source','remix_source'].map(x=><option key={x}>{x}</option>)}</select></label>
      {driveAudio}
      <p className="help">native：原生生成；reference_only：音訊參考；lock_source：鎖定來源；remix_source：重混來源。後兩者需要 drive audio。</p>
      <label>Seed 模式<select value={spec.seed_mode??(spec.noise_seed!=null?'fixed':'randomize')} onChange={e=>onChange({seed_mode:e.target.value,...(e.target.value==='fixed'&&spec.noise_seed==null?{noise_seed:'0'}:{})})}><option value="randomize">randomize · 每次隨機</option><option value="fixed">fixed · 固定</option></select></label><label>Noise seed<input aria-label="Noise seed" type="text" inputMode="numeric" placeholder="留空每次隨機；或貼上歷史 seed" value={spec.noise_seed??''} onChange={e=>{if(/^[0-9]*$/.test(e.target.value))onChange({noise_seed:e.target.value||null,seed_mode:'fixed'});}}/></label><p className="help">範圍 0–18446744073709551615。相同 seed 仍需配合相同模型、素材及參數；不保證不同環境的輸出完全一致。</p>
      <label className="check-row"><input type="checkbox" checked={enabled} onChange={e=>onChange({lora_enabled:e.target.checked})}/>啟用 LoRA 與 Shift</label>
      <fieldset disabled={!enabled}>
        <label>主要 LoRA 強度<NumberInput min={-20} max={20} step={.1} value={spec.lora_strength??1} onValueChange={(n:number)=>onChange({lora_strength:n})}/></label>
        {(spec.extra_loras||[]).map((l:any,i:number)=><div className="image-lora-row" key={i}><input type="checkbox" checked={l.enabled!==false} onChange={e=>onChange({extra_loras:spec.extra_loras.map((v:any,j:number)=>i===j?{...v,enabled:e.target.checked}:v)})}/><input placeholder="額外 LoRA 檔名" value={l.name} onChange={e=>onChange({extra_loras:spec.extra_loras.map((v:any,j:number)=>i===j?{...v,name:e.target.value}:v)})}/><NumberInput min={-20} max={20} step={.1} value={l.strength} onValueChange={(n:number)=>onChange({extra_loras:spec.extra_loras.map((v:any,j:number)=>i===j?{...v,strength:n}:v)})}/><button onClick={()=>onChange({extra_loras:spec.extra_loras.filter((_:any,j:number)=>j!==i)})}>移除</button></div>)}
        <button onClick={()=>onChange({extra_loras:[...(spec.extra_loras||[]),{name:'',strength:1,enabled:true}]})}>＋ 額外 LoRA（依順序載入）</button>
        <label>LoRA 檔名<select aria-label="節點 LoRA" value={spec.lora} onChange={e=>onChange({lora:e.target.value,shift_enabled:e.target.value===SPECIAL_LORA,shift_video:6,shift_audio:3})}>{loras.map(m=><option key={m} value={m}>{m}</option>)}</select></label>
        <label className="check-row"><input type="checkbox" checked={!!shift} onChange={e=>onChange({shift_enabled:e.target.checked})}/>啟用 video / audio Shift</label>
        {shift&&<div className="advanced-grid"><label>Video Shift<NumberInput value={spec.shift_video??6} min={0} max={100} step={0.1} onValueChange={(n:number)=>onChange({shift_video:n})}/></label><label>Audio Shift<NumberInput value={spec.shift_audio??3} min={0} max={100} step={0.1} onValueChange={(n:number)=>onChange({shift_audio:n})}/></label></div>}
        <p className="help">768p 4step LoRA 預設 Shift 6 / 3；「4步加速」預設關閉。可在此覆寫；停用 LoRA 時 Shift 一起停用。</p>
      </fieldset>
      <div className="advanced-grid"><label>Steps<NumberInput value={spec.steps??8} min={1} max={200} onValueChange={(n:number)=>onChange({steps:n})}/></label><label>Sampler<input value={spec.sampler??'euler'} onChange={e=>onChange({sampler:e.target.value})}/></label><label>Scheduler<input value={spec.scheduler??'beta'} onChange={e=>onChange({scheduler:e.target.value})}/></label></div>
      <p className="help">預設 8 / euler / beta；自訂名稱需由工作流服務支援。</p>
      <label className="check-row"><input type="checkbox" checked={!!spec.low_vram_enabled} onChange={e=>onChange({low_vram_enabled:e.target.checked})}/>啟用降低顯存（預設關閉）</label>
      {spec.low_vram_enabled&&<div className="advanced-grid"><label>Head chunks<NumberInput value={spec.head_chunks??(spec.megapixels>=1.5?8:4)} min={1} max={56} onValueChange={(n:number)=>onChange({head_chunks:n})}/></label><label>Chunks<NumberInput value={spec.chunks??(spec.megapixels>=1.5?4:2)} min={1} max={64} onValueChange={(n:number)=>onChange({chunks:n})}/></label></div>}
      <p className="help">分塊可降低顯存需求，可能增加耗時。建議 1.0 MP 用 4 / 2，≥ 1.5 MP 用 8 / 4；依顯存自行開啟。</p>
      <label className="check-row"><input type="checkbox" checked={!!spec.two_pass} onChange={e=>onChange({two_pass:e.target.checked})}/>啟用二採放大</label>
      {spec.two_pass&&<><label>放大倍數 scale_by<NumberInput min={1} max={4} step={.01} value={spec.two_pass_parameters?.upscale?.scale_by??2} onValueChange={(n:number)=>onChange({two_pass_parameters:{...spec.two_pass_parameters,upscale:{...spec.two_pass_parameters?.upscale,scale_by:n}}})}/></label>
      <label className="check-row"><input type="checkbox" checked={spec.save_first_pass!==false} onChange={e=>onChange({save_first_pass:e.target.checked})}/>同時保存一採影片（導演台優先使用）</label>
      <details><summary>二採全部參數（工作流預設）</summary>{Object.entries(config.video_two_pass_parameters||{}).map(([group,fields]:any)=><fieldset key={group}><legend>{group}</legend>{Object.entries(fields).map(([key,initial]:any)=>{const value=spec.two_pass_parameters?.[group]?.[key]??initial;const set=(v:any)=>onChange({two_pass_parameters:{...spec.two_pass_parameters,[group]:{...spec.two_pass_parameters?.[group],[key]:v}}});return <label className={typeof initial==='boolean'?'check-row':undefined} key={key}>{key}{typeof initial==='boolean'?<input type="checkbox" checked={value} onChange={e=>set(e.target.checked)}/>:typeof initial==='number'?<NumberInput min={-1000000} max={1000000} step={Number.isInteger(initial)?1:.001} value={value} onValueChange={set}/>:<input value={value} onChange={e=>set(e.target.value)}/>}</label>;})}</fieldset>)}</details><p className="help">其餘參數沿用工作流；二採需要較大顯存。scale_by 直接交給節點計算，不將 MP 手動乘倍數。</p></>}


    </div>
  </details>;
}

export function ModelSettings({settings,onChange}:any) {
  return <div className="connection-block model-settings"><h3>模型與 LoRA 檔名</h3><p className="help">填入服務端實際檔名（包含副檔名）；會直接傳給 RunningHub / ComfyUI。修改清單不會改寫既有節點，請重新選取。</p>
    {(settings.models||[]).map((m:any,i:number)=><div className="model-entry" key={i}><label>模型<input aria-label={'模型檔名 '+(i+1)} value={m.name} onChange={e=>onChange({...settings,models:settings.models.map((x:any,j:number)=>j===i?{...x,name:e.target.value}:x)})}/></label><button disabled={settings.models.length<=1} onClick={()=>onChange({...settings,models:settings.models.filter((_:any,j:number)=>j!==i)})}>移除</button>
      <label className="check-row"><input type="checkbox" checked={!!m.shift_enabled} onChange={e=>onChange({...settings,models:settings.models.map((x:any,j:number)=>j===i?{...x,shift_enabled:e.target.checked}:x)})}/>自訂模型預設 Shift</label>
      {m.shift_enabled&&<div className="advanced-grid">{['video','audio'].map(k=><label key={k}>{k} Shift<NumberInput min={0} max={100} step={0.1} value={m['shift_'+k]??(k==='video'?6:3)} onValueChange={(n:number)=>onChange({...settings,models:settings.models.map((x:any,j:number)=>j===i?{...x,['shift_'+k]:n}:x)})}/></label>)}</div>}
    </div>)}
    <button onClick={()=>onChange({...settings,models:[...settings.models,{name:'',shift_enabled:false,shift_video:6,shift_audio:3}]})}>＋ 新增模型</button>
    {(settings.loras||[]).map((name:string,i:number)=><div className="model-entry" key={i}><label>LoRA<input aria-label={'LoRA 檔名 '+(i+1)} value={name} onChange={e=>onChange({...settings,loras:settings.loras.map((x:string,j:number)=>j===i?e.target.value:x)})}/></label><button disabled={settings.loras.length<=1} onClick={()=>onChange({...settings,loras:settings.loras.filter((_:string,j:number)=>j!==i)})}>移除</button></div>)}
    <button onClick={()=>onChange({...settings,loras:[...settings.loras,'']})}>＋ 新增 LoRA</button>
  </div>;
}

export function VideoDefaults({config,value,onChange}:any){
  const change=(patch:any)=>onChange({...value,...patch});
  return <div className="connection-block"><h3>新影片節點預設參數</h3><p className="help">儲存後只套用至之後新增的影片節點；既有節點保持原設定。</p><div className="advanced-grid">
    <label>服務<select value={value.provider} onChange={e=>change({provider:e.target.value})}><option value="comfyui">本機 ComfyUI</option><option value="runninghub">RunningHub</option></select></label>
    <label>模式<select value={value.mode} onChange={e=>change({mode:e.target.value})}><option value="T2VA">文生影片</option><option value="Ref2VA">參考生影片</option><option value="I2VA">首幀生影片</option><option value="L2VA">尾幀生影片</option><option value="FL2VA">首尾生影片</option></select></label>
    <label>模型<select value={value.model} onChange={e=>change(modelSelection(e.target.value,config))}>{config.models.map((m:string)=><option key={m}>{m}</option>)}</select></label>
    <label>比例<select value={value.aspect_ratio} onChange={e=>change({aspect_ratio:e.target.value})}>{config.aspects.map((a:string)=><option key={a}>{a}</option>)}</select></label>
    <label>大小 / MP<select value={value.megapixels} onChange={e=>change({megapixels:Number(e.target.value)})}>{Array.from({length:19},(_,i)=>(i+2)/10).map(n=><option key={n} value={n}>{n.toFixed(1)}</option>)}</select></label>
    <label>時長 / 秒<NumberInput min={1} max={15} value={value.duration} onValueChange={(n:number)=>change({duration:n})}/></label>
  </div><AdvancedSettings spec={value} config={config} onChange={change}/></div>;
}

export function NodeName({value,onChange}:any){return <input className="node-name nodrag" aria-label="節點名稱" title="編輯節點名稱" value={value} onChange={e=>onChange(e.target.value)} onKeyDown={e=>e.stopPropagation()} onDoubleClick={e=>e.stopPropagation()}/>;}

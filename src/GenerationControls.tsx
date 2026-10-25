import React, {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';

// Keep in-progress typing local: React Flow's store synchronization must not reset caret/IME.
export const PromptInput = forwardRef<HTMLTextAreaElement, any>(function PromptInput({value,onValueChange,...props}, forwarded) {
  const ref=useRef<HTMLTextAreaElement>(null), composing=useRef(false);
  const [text,setText]=useState(value||'');
  useImperativeHandle(forwarded,()=>ref.current!);
  useEffect(()=>{if(document.activeElement!==ref.current)setText(value||'');},[value]);
  return <textarea {...props} ref={ref} value={text}
    onCompositionStart={()=>{composing.current=true;}}
    onCompositionEnd={e=>{composing.current=false;onValueChange(e.currentTarget.value,e.currentTarget.selectionStart);}}
    onChange={e=>{setText(e.target.value);if(!composing.current)onValueChange(e.target.value,e.target.selectionStart);}}
    onBlur={e=>{if(e.currentTarget.value!==value)onValueChange(e.currentTarget.value,e.currentTarget.selectionStart);}}
    onKeyDown={e=>e.stopPropagation()}/>;
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

export function AdvancedSettings({spec,config,onChange}:any) {
  const enabled=spec.lora_enabled!==false;
  const shift=spec.shift_enabled??(spec.lora===SPECIAL_LORA);
  const loras=Array.from(new Set([...(config.loras||[]),spec.lora].filter(Boolean))) as string[];
  return <details className="advanced-settings nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
    <summary>高級功能 · LoRA、Shift、採樣與顯存</summary>
    <div className="advanced-body">
      <label className="check-row"><input type="checkbox" checked={enabled} onChange={e=>onChange({lora_enabled:e.target.checked})}/>啟用 LoRA 與 Shift</label>
      <fieldset disabled={!enabled}>
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
    <label>模式<select value={value.mode} onChange={e=>change({mode:e.target.value})}><option value="T2VA">文生影片</option><option value="Ref2VA">參考生影片</option><option value="FL2VA">首尾生影片</option></select></label>
    <label>模型<select value={value.model} onChange={e=>change(modelSelection(e.target.value,config))}>{config.models.map((m:string)=><option key={m}>{m}</option>)}</select></label>
    <label>比例<select value={value.aspect_ratio} onChange={e=>change({aspect_ratio:e.target.value})}>{config.aspects.map((a:string)=><option key={a}>{a}</option>)}</select></label>
    <label>大小 / MP<select value={value.megapixels} onChange={e=>change({megapixels:Number(e.target.value)})}>{Array.from({length:19},(_,i)=>(i+2)/10).map(n=><option key={n} value={n}>{n.toFixed(1)}</option>)}</select></label>
    <label>時長 / 秒<NumberInput min={1} max={15} value={value.duration} onValueChange={(n:number)=>change({duration:n})}/></label>
  </div><AdvancedSettings spec={value} config={config} onChange={change}/></div>;
}

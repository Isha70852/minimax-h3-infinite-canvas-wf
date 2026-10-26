import {TemplateContext,TemplateBar,TemplateManager,defaultTemplate} from './NodeTemplates';
import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  createContext,
  useContext,
} from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  MiniMap,
  NodeResizer,
  Controls,
  Handle,
  Position,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
  MarkerType,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
} from "@xyflow/react";
import {
  Plus,
  Upload,
  Film,
  Image as ImageIcon,
  Music2,
  FolderOpen,
  Settings,
  Copy,
  Maximize2,
  X,
  Play,
  ArrowUpRight,
  Trash2,
  Check,
  Link2,
  ChevronUp,
  ChevronDown,
  Clock3,
  Download,
  PanelLeftClose,
  PanelLeftOpen,
  Save,
  LoaderCircle,
  MousePointer2,
  Unplug,
  RefreshCw,
  Type,
  Volume2,
  VolumeX,
  Scissors,
  LayoutGrid,
} from "lucide-react";
import {
  uid,
  modeNames,
  kindNames,
  activeStatuses,
  duplicateNode,
  referenceRows,
  megapixelOptions,
  resolutionLabel,
} from "./canvas.mjs";
import "@xyflow/react/dist/style.css";
import "./style.css";
import { LibraryPanel } from "./LibraryPanel";
import { AutomationSettings, StudioInfo } from "./AutomationSettings";
import { PromptPanel } from "./PromptPanel";
import {MediaTools} from "./MediaTools";
import {AudioPlayer} from "./AudioPlayer";
import {ImageNode,imageDefaults} from "./ImageNode";
import {AssistantSettingsPanel} from "./AssistantSettingsPanel";
import {DirectorNode} from './DirectorNode';
import {AudioNode} from "./AudioNode";
import {AdvancedSettings, NumberInput, PromptInput, ModelSettings, VideoDefaults, modelSelection} from "./GenerationControls";

type Asset = {
  id: string;
  name: string;
  kind: "image" | "video" | "audio";
  url: string;
  size?: number;
  deleted?: boolean;
  favorite?: boolean;
  use_count?: number;
};
type Config = { node_templates?: any[]; models: string[]; loras: string[]; aspects: string[]; model_profiles?: any[]; audio_workflows?: any[]; image_workflows?: any[]; video_defaults?: Partial<Spec> };
type Spec = {
  provider: string;
  prompt: string;
  mode: "T2VA" | "FL2VA" | "Ref2VA";
  model: string;
  lora: string;
  prompt_source?: string | null;
  motion_context?: boolean;
  context_run_id?: string | null;
  context_video_asset_id?: string | null;
  _template_id?: string;
  _template_name?: string;
  lora_strength?: number;
  extra_loras?: {name:string;strength:number;enabled:boolean}[];
  megapixels: number;
  aspect_ratio: string;
  duration: number;
  head_chunks: number | null;
  chunks: number | null;
  lora_enabled?: boolean;
  shift_enabled?: boolean | null;
  shift_video?: number;
  shift_audio?: number;
  low_vram_enabled?: boolean;
  steps?: number;
  sampler?: string;
  scheduler?: string;
};
type CardData = Record<string, unknown> & {
  label: string;
  kind: "asset" | "generation" | "text" | "music" | "tts" | "imagegen" | "director";
  audio_spec?: any;
  image_spec?: any;
  text?: string;
  assistant_requirement?: string;
  asset_id?: string;
  output_id?: string;
  applied_run_id?: string;
  spec?: Spec;
};
type CardNode = Node<CardData>;
type Run = {
  id: string;
  node_id: string;
  status: string;
  stage: string;
  progress: number | null;
  spec: Spec;
  outputs: Asset[];
  error?: string;
  created_at: number;
  seed: string;
  remote_id?: string;
  usage?: {consumeCoins?: string | number | null; taskCostTime?: string | number | null};
  compiled: { prompt: string; mapping: unknown[]; workflow: unknown };
};
type Project = {
  id: string;
  name: string;
  nodes: CardNode[];
  edges: Edge[];
  viewport: { x: number; y: number; zoom: number };
};
const defaults = (config: Config): Spec => ({
  provider: "comfyui",
  prompt: "",
  mode: "T2VA",
  model: config.models[0],
  lora: config.loras[0],
  megapixels: 0.7,
  aspect_ratio: config.aspects[0],
  duration: 15,
  head_chunks: null,
  chunks: null,
  lora_strength: 1, extra_loras: [],
  lora_enabled: true, shift_enabled: null, shift_video: 6, shift_audio: 3, low_vram_enabled: false, steps: 8, sampler: "euler", scheduler: "beta",
  ...config.video_defaults,
});
async function api(path: string, options: RequestInit = {}) {
  const response = await fetch("/api" + path, {
    ...options,
    headers:
      options.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json" },
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  return body;
}
const actions = createContext<{
  nodes: CardNode[];
  setSegments:(id:string,ids:string[])=>void;
  addSegment:(id:string)=>void;
  generateSegment:(id:string,previous?:string)=>void;
  focusNode:(id:string)=>void;
  editAudio: (id:string,spec:any)=>void;
  resetAudio: (id:string,spec:any)=>void;
  editImage: (id:string,spec:any)=>void;
  resetImage: (id:string,spec:any)=>void;
  bindAudio: (id:string,field:string,source:string)=>void;
  audioOutput: (id:string,asset:string)=>void;
  restoreVideo: (id:string,spec:Spec)=>void;
  assets: Asset[];
  runs: Run[];
  duplicate: (id: string) => void;
  preview: (asset: Asset) => void;
  remove: (id: string) => void;
  generate: (id: string) => void;
  editText: (id: string, text: string) => void;
  config: Config | null;
  edges: Edge[];
  editSpec: (id: string, spec: Partial<Spec>) => void;
  pickReferences: (id: string) => void;
  openAssistant: (id:string)=>void;
  removeReference: (edgeId:string)=>void;
}>({
  setSegments:()=>{},addSegment:()=>{},generateSegment:()=>{},focusNode:()=>{},
  restoreVideo:()=>{}, nodes: [], editImage:()=>{}, resetImage:()=>{}, editAudio:()=>{}, resetAudio:()=>{}, bindAudio:()=>{}, audioOutput:()=>{},
  assets: [],
  runs: [],
  duplicate: () => {},
  preview: () => {},
  remove: () => {},
  generate: () => {},
  editText: () => {},
  config: null, edges: [], editSpec: () => {}, pickReferences: () => {}, openAssistant: () => {}, removeReference: () => {},
});
function HoverVideo({asset, controls, hover}: {asset:Asset;controls:boolean;hover:boolean}) {
  const ref=useRef<HTMLVideoElement>(null), [muted,setMuted]=useState(true);
  return <div className="hover-video nodrag nowheel" onMouseEnter={()=>{if(hover)ref.current?.play().catch(()=>{});}} onMouseLeave={()=>{if(hover)ref.current?.pause();}}>
    <video ref={ref} src={asset.url} muted={muted} loop={hover} controls={controls} preload="metadata" playsInline />
    {hover&&<button className="video-mute nodrag" title={muted?'開啟影片聲音':'關閉影片聲音'} onClick={e=>{e.stopPropagation();setMuted(!muted);}}>{muted?<VolumeX size={16}/>:<Volume2 size={16}/>}</button>}
  </div>;
}
function Media({asset,controls=false,hover=false}:{asset:Asset;controls?:boolean;hover?:boolean}) {
  return asset.kind==='image'?<img src={asset.url} alt={asset.name} draggable={false}/>:asset.kind==='video'?<HoverVideo asset={asset} controls={controls} hover={hover}/>:controls?<AudioPlayer src={asset.url} label={asset.name}/>:<div className="audio-art"><Music2 size={36}/><div className="wave">{Array.from({length:28},(_,i)=><i key={i} style={{height:12+Math.sin(i*2.3)**2*36}}/>)}</div>{controls&&<audio src={asset.url} controls/>}</div>;
}
function Usage({run}: {run:Run}) {
  if(run.spec.provider!=='runninghub')return null;
  const seconds=run.usage?.taskCostTime;
  return <div className="usage-line">{run.usage?.consumeCoins != null ? `${run.usage.consumeCoins} RH 幣` : 'RH 幣：尚未回傳'} · {seconds != null ? `${seconds} 秒（${Math.floor(Number(seconds)/60)} 分 ${Number(seconds)%60} 秒）` : '耗時：尚未回傳'}</div>;
}
function CanvasCard({ id, data, selected }: NodeProps<CardNode>) {
  const ctx = useContext(actions),
    run = ctx.runs.find((r) => r.node_id === id),
    asset = ctx.assets.find((a) => a.id === (data.asset_id || data.output_id));
  const active = run && activeStatuses.includes(run.status);
  const promptEdge=ctx.edges.find(e=>e.target===id&&e.targetHandle==='prompt');
  const promptSource=ctx.nodes.find(n=>n.id===promptEdge?.source);
  if(data.kind==="director")return <DirectorNode id={id} data={data} selected={selected} ctx={ctx}/>;
  if(data.kind==="imagegen")return <ImageNode id={id} data={data} selected={selected} ctx={ctx} Media={Media} Usage={Usage}/>;
  if(data.kind==="music"||data.kind==="tts")return <AudioNode id={id} data={data} selected={selected} ctx={ctx} Media={Media} Usage={Usage}/>;
  return (
    <article
      className={"canvas-card " + (selected ? "is-selected " : "") + data.kind + (asset?.kind==='audio'?' compact-audio':'')}
    >
      <NodeResizer isVisible={selected} minWidth={240} minHeight={asset?.kind==='audio'?136:200} maxHeight={asset?.kind==='audio'?136:undefined} />
      {(data.kind === "generation" || data.kind === "text") && (
        <Handle
          type="target"
          position={Position.Left}
          aria-label="引用素材輸入"
        />
      )}
      {data.kind==='generation'&&<Handle type="target" id="prompt" position={Position.Left} style={{top:28}} title="文字提示詞輸入" aria-label="文字提示詞輸入"/>}
      <header>
        <span className="node-icon">
          {data.kind === "text" ? <Type size={15} /> : data.kind === "generation" ? (
            <Film size={15} />
          ) : asset?.kind === "audio" ? (
            <Music2 size={15} />
          ) : (
            <ImageIcon size={15} />
          )}
        </span>
        <span>{data.label}</span>
        <span className="node-type">
          {data.kind === "generation" ? "H3" : asset?.kind.toUpperCase()}
        </span>
      </header>
      <div
        className="card-media"
        onDoubleClick={() => asset && ctx.preview(asset)}
      >
        {data.kind === "text" ? (
          <textarea className="text-node-editor nodrag nowheel" aria-label="文字內容" placeholder="寫下想法、故事或提示詞…" value={data.text || ""} onChange={(e) => ctx.editText(id, e.target.value)} />
        ) : asset ? (
          <Media asset={asset} hover controls />
        ) : (
          <div className="generation-placeholder">
            <Film size={34} />
            <strong>
              {active ? "鏡頭正在成形" : "下一個鏡頭，從這裡開始"}
            </strong>
            <span>
              {data.spec ? modeNames[data.spec.mode] : "MiniMax H3"} ·{" "}
              {data.spec?.duration} 秒
            </span>
          </div>
        )}
        {asset && (
          <button
            className="expand nodrag"
            title="放大查看"
            onClick={() => ctx.preview(asset)}
          >
            <Maximize2 size={15} />
          </button>
        )}
      </div>
      {data.kind === "generation" && selected && data.spec && ctx.config && <div className="node-composer nodrag nowheel" onDoubleClick={e=>e.stopPropagation()}>
        <TemplateBar category="video" spec={data.spec} onApply={(spec:any)=>ctx.editSpec(id,spec)}/><div className="composer-modes">{Object.entries(modeNames).map(([mode,label])=><button key={mode} className={data.spec!.mode===mode?'active':''} onClick={()=>ctx.editSpec(id,{mode:mode as Spec['mode']})}>{label}</button>)}</div>
        <div className="composer-refs">{referenceRows(id,ctx.edges,ctx.assets).map((r:any)=><button key={r.edge.id} title={r.alias+' · 點擊取消引用 · '+r.asset.name} onClick={()=>ctx.removeReference(r.edge.id)}><Media asset={r.asset}/><span>{r.alias}</span></button>)}<button title="從專案素材加入" onClick={()=>ctx.pickReferences(id)}><Plus size={20}/></button></div>
        <label className="prompt-source-select">提示詞來源<select value={promptSource?.id||''} onChange={e=>ctx.bindAudio(id,'prompt',e.target.value)}><option value="">直接輸入</option>{ctx.nodes.filter(n=>n.data.kind==='text').map(n=><option key={n.id} value={n.id}>{n.data.label} · {(n.data.text||'').slice(0,32)}</option>)}</select></label>
        <PromptInput disabled={!!promptSource} aria-label="節點提示詞" placeholder="描述想生成的內容，使用 @圖片1 引用素材…" value={promptSource?.data.text??data.spec.prompt} onValueChange={(value:string)=>ctx.editSpec(id,{prompt:value})}/>
        {/@[^\s@]*$/.test(data.spec.prompt)&&<div className="composer-mentions">{referenceRows(id,ctx.edges,ctx.assets).map((r:any)=><button key={r.edge.id} onClick={()=>ctx.editSpec(id,{prompt:data.spec!.prompt.replace(/@[^\s@]*$/, '@'+r.alias+' ')})}>@{r.alias}</button>)}</div>}
        <div className="composer-fields">
          <select aria-label="節點運算服務" value={data.spec.provider} onChange={e=>ctx.editSpec(id,{provider:e.target.value})}><option value="runninghub">RunningHub</option><option value="comfyui">本機 ComfyUI</option></select>
          <select aria-label="節點模型" title={data.spec.model} value={data.spec.model} onChange={e=>ctx.editSpec(id,modelSelection(e.target.value,ctx.config))}>{Array.from(new Set([...ctx.config.models,data.spec.model])).map(m=><option key={m} value={m}>{m}</option>)}</select>

          <select aria-label="節點畫面比例" value={data.spec.aspect_ratio} onChange={e=>ctx.editSpec(id,{aspect_ratio:e.target.value})}>{ctx.config.aspects.map(m=><option key={m} value={m}>{m}</option>)}</select>
          <select aria-label="節點大小" value={data.spec.megapixels} onChange={e=>ctx.editSpec(id,{megapixels:Number(e.target.value)})}>{megapixelOptions.map(m=><option key={m} value={m}>{resolutionLabel(m,data.spec!.aspect_ratio)}</option>)}</select>
          <label className="duration-field"><NumberInput aria-label="節點時長" min={1} max={15} value={data.spec.duration} onValueChange={(n:number)=>ctx.editSpec(id,{duration:n})}/><span>秒</span></label>
        </div>
        <AdvancedSettings spec={data.spec} config={ctx.config} onChange={(value:Partial<Spec>)=>ctx.editSpec(id,value)}/>
        <div className="composer-submit"><button onClick={()=>ctx.openAssistant(id)}>✦ AI 撰寫提示詞</button><span>{data.spec.provider==='runninghub'?'依 RunningHub 實際用量計費':'本機運算'}</span><button className="primary" disabled={!!active} onClick={()=>ctx.generate(id)}><Play size={14}/>{active?'生成中…':asset?'重新生成':'生成影片'}</button></div>
        <details className="video-node-history"><summary>生成歷史（{ctx.runs.filter(r=>r.node_id===id).length}）</summary>
          {ctx.runs.filter(r=>r.node_id===id).sort((a,b)=>b.created_at-a.created_at).map(r=><div className="audio-history" key={r.id}>
            <p>{new Date(r.created_at*1000).toLocaleString('zh-TW')} · {r.stage}</p>
            {r.outputs.map(a=><div key={a.id}><Media asset={a} controls/><div className="template-actions"><button onClick={()=>ctx.preview(a)}>放大查看</button><button onClick={()=>ctx.audioOutput(id,a.id)}>顯示此版本</button><a href={a.url} download={a.name}>下載</a></div></div>)}
            <Usage run={r}/>{r.error&&<p className="error-message">{r.error}</p>}
            <details><summary>提示詞與參數</summary><textarea readOnly rows={5} value={r.compiled?.prompt||r.spec.prompt}/><p>{r.spec.duration} 秒 · {r.spec.megapixels} MP · {r.spec.steps??8} steps · {r.spec.sampler??'euler'} / {r.spec.scheduler??'beta'}</p><p>{r.spec.model}</p></details>
            <button onClick={()=>ctx.restoreVideo(id,r.spec)}>套用此版提示詞與參數</button>
          </div>)}
          {!ctx.runs.some(r=>r.node_id===id)&&<p className="help">尚無生成紀錄。</p>}
        </details>
      </div>}
      {selected && run && (
        <div className={"run-status " + run.status}>
          {active ? (
            <LoaderCircle className="spin" size={12} />
          ) : run.status === "success" ? (
            <Check size={12} />
          ) : (
            <Clock3 size={12} />
          )}
          <span>{run.stage}</span>
          {run.progress !== null && <span>{run.progress}%</span>}
          {active && (
            <div
              className={
                "progress " + (run.progress === null ? "indeterminate" : "")
              }
              style={{
                width: run.progress === null ? "35%" : `${run.progress}%`,
              }}
            />
          )}
        </div>
      )}
      {selected && run && <Usage run={run}/>}
      {(selected || data.kind === "text" || asset?.kind==='audio') && <footer className="nodrag" onClick={(event) => event.stopPropagation()}>
        <button title="複製節點與連線" onClick={() => ctx.duplicate(id)}>
          <Copy size={14} />
        </button>
        <button title="移除節點" onClick={() => ctx.remove(id)}>
          <Trash2 size={14} />
        </button>
        <span />
        {data.kind === "generation" ? (
          <button
            className="generate-small"
            disabled={!!active}
            onClick={() => ctx.generate(id)}
          >
            <Play size={12} />
            {asset ? "重新生成" : "生成影片"}
          </button>
        ) : (
          <small>{data.kind === "text" ? <><button onClick={()=>ctx.openAssistant(id)}>AI 撰寫</button><button onClick={()=>ctx.pickReferences(id)}>引用素材</button></> : <>拉出連線，開始創作 <ArrowUpRight size={13} /></>}</small>
        )}
      </footer>}
      {<Handle
        type="source"
        position={Position.Right}
        isConnectable={!!asset || data.kind==="text"}
        aria-label="素材輸出"
      />}
    </article>
  );
}
const nodeTypes = { card: CanvasCard };
function App() {
  const flow = useReactFlow<CardNode>();
  const [templatesOpen,setTemplatesOpen]=useState(false);
  const [config, setConfig] = useState<Config | null>(null),
    [project, setProject] = useState<Project | null>(null),
    [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [nodes, setNodes] = useState<CardNode[]>([]),
    [edges, setEdges] = useState<Edge[]>([]),
    [assets, setAssets] = useState<Asset[]>([]),
    [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string | null>(null),
    [sidebar, setSidebar] = useState(false),
    [tabName, setTabName] = useState<"assets" | "projects">("assets"),
    [inspectorTab, setInspectorTab] = useState<"edit" | "history">("edit");
  const [modal, setModal] = useState<Asset | null>(null),
    [settingsOpen, setSettingsOpen] = useState(false),
    [settings, setSettings] = useState<any>(null),
    [toast, setToast] = useState(""),
    [saving, setSaving] = useState("已儲存"),
    [uploading, setUploading] = useState(false),
    [mention, setMention] = useState(false),
    [preview, setPreview] = useState<any>(null);
  const [assistantNode,setAssistantNode]=useState<string|null>(null);
  const [trashProjects,setTrashProjects]=useState<{id:string;name:string}[]>([]);
  const [inspectorVisible, setInspectorVisible] = useState(false);
  const [mediaTool,setMediaTool]=useState<{mode:'crop'|'stitch'|'extract';asset?:Asset}|null>(null);
  const [libraryPanel, setLibraryPanel] = useState<{scope:string;target?:string}|null>(null);
  const [createMenu, setCreateMenu] = useState<{x:number;y:number;position:{x:number;y:number}} | null>(null);
  const uploadOrigin = useRef<{x:number;y:number} | null>(null);
  const fileInput = useRef<HTMLInputElement>(null),
    promptInput = useRef<HTMLTextAreaElement>(null),
    loaded = useRef(false),
    revision = useRef(0),
    saved = useRef(0),
    saveChain = useRef(Promise.resolve()),
    snapshot = useRef<any>(null),
    pending = useRef(new Set<string>());
  const notify = (s: string) => setToast(s);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 6500);
    return () => clearTimeout(t);
  }, [toast]);
  const refreshProjects = () => Promise.all([api("/projects").then(setProjects),api('/projects?deleted=true').then(setTrashProjects)]);
  async function deleteProject(id:string){
    await save(); await api('/projects/'+id,{method:'DELETE'});
    const remaining=await api('/projects');
    if(project?.id===id){loaded.current=false;revision.current=0;saved.current=0;setAssistantNode(null);if(remaining.length)await openProject(remaining[0].id);else await newProject();}
    await refreshProjects();notify('專案已移至回收區，可還原');
  }
  async function openProject(id: string) {
    await save();
    loaded.current = false;
    const p = await api("/projects/" + id);
    setProject(p);
    setAssets(await api("/assets?project_id="+p.id));
    setLibraryPanel(null);
    setNodes(p.nodes);
    setEdges(p.edges);
    setSelected(null);
    setRuns(await api("/runs?project_id=" + id));
    revision.current = 0;
    saved.current = 0;
    setSaving("已儲存");
    await flow.setViewport(p.viewport);
    loaded.current = true;
  }
  async function newProject() {
    await save();
    const p = await api("/projects", {
      method: "POST",
      body: JSON.stringify({ name: "新專案 " + (projects.length + 1) }),
    });
    loaded.current = false;
    setProject(p);
    setNodes([]);
    setAssets([]);
    setLibraryPanel(null);
    setEdges([]);
    setRuns([]);
    setSelected(null);
    await flow.setViewport({ x: 0, y: 0, zoom: 1 });
    revision.current = 0;
    saved.current = 0;
    loaded.current = true;
    await refreshProjects();
  }
  useEffect(() => {
    (async () => {
      const [c, p] = await Promise.all([api("/config"),api("/projects")]);
      setConfig(c);

      setProjects(p);
      const first = p[0]
        ? await api("/projects/" + p[0].id)
        : await api("/projects", {
            method: "POST",
            body: JSON.stringify({ name: "我的第一個鏡頭" }),
          });
      setProject(first);
      setAssets(await api("/assets?project_id="+first.id));
      setNodes(first.nodes);
      setEdges(first.edges);
      await flow.setViewport(first.viewport);
      loaded.current = true;
      refreshProjects();
    })().catch((e) => notify(e.message));
  }, []);
  snapshot.current = { project, nodes, edges };
  function dirty() {
    if (loaded.current) {
      revision.current++;
      setSaving("尚未儲存");
    }
  }
  async function save() {
    const state = snapshot.current;
    if (
      !state?.project ||
      !loaded.current ||
      revision.current === saved.current
    )
      return saveChain.current;
    const rev = revision.current;
    const id = state.project.id;
    const body = {
      name: state.project.name,
      nodes: state.nodes,
      edges: state.edges,
      viewport: flow.getViewport(),
    };
    setSaving("儲存中…");
    saveChain.current = saveChain.current
      .catch(() => {})
      .then(async () => {
        await api("/projects/" + id, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        if (snapshot.current.project?.id === id) {
          saved.current = rev;
          setSaving(revision.current === rev ? "已儲存" : "尚未儲存");
        }
      });
    try {
      await saveChain.current;
    } catch (e: any) {
      setSaving("儲存失敗");
      throw e;
    }
  }
  useEffect(() => {
    const t = setTimeout(() => save().catch((e) => notify(e.message)), 700);
    return () => clearTimeout(t);
  }, [nodes, edges, project]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (revision.current !== saved.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);
  useEffect(() => {
    if (!project) return;
    let canceled = false;
    async function poll() {
      try {
        const r: Run[] = await api("/runs?project_id=" + project!.id);
        if (canceled) return;
        setRuns(r.sort((a, b) => b.created_at - a.created_at));
        const outputs = r.flatMap((x) => x.outputs);
        if (outputs.length)
          setAssets((old) => [
            ...old,
            ...outputs.filter((a) => !old.some((b) => a.id === b.id)),
          ]);
        setNodes((old) => {
          let changed = false;
          const next = old.map((n) => {
            const latest = r
              .filter((x) => x.node_id === n.id)
              .sort((a, b) => b.created_at - a.created_at)
              .find((x) => x.status === "success");
            if (latest?.outputs[0] && n.data.applied_run_id !== latest.id) {
              changed = true;
              return {
                ...n,
                data: {
                  ...n.data,
                  output_id: latest.outputs[0].id,
                  applied_run_id: latest.id,
                },
              };
            }
            return n;
          });
          if (changed) dirty();
          return changed ? next : old;
        });
      } catch (e: any) {
        if (!canceled) notify(e.message);
      }
    }
    poll();
    const t = setInterval(poll, 2000);
    return () => {
      canceled = true;
      clearInterval(t);
    };
  }, [project?.id]);
  const current = nodes.find((n) => n.id === selected),
    spec = current?.data.spec;
  const rows = current ? referenceRows(current.id, edges, assets) : [];
  function patch(id: string, data: Partial<CardData>) {
    dirty();
    setNodes((old) =>
      old.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...data } } : n,
      ),
    );
  }
  function patchSpec(data: Partial<Spec>) {
    if (current && spec) patch(current.id, { spec: { ...spec, ...data } });
  }
  function addAsset(asset: Asset, position?: { x: number; y: number }) {
    api("/assets/"+asset.id+"/use",{method:"POST"}).catch(()=>{});
    const id = uid();
    const pos =
      position || flow.screenToFlowPosition({ x: sidebar ? 430 : 220, y: 200 });
    const node: CardNode = {
      id,
      type: "card",
      position: pos,
      data: { kind: "asset", label: asset.name, asset_id: asset.id },
    };
    dirty();
    setNodes((n) => [...n, node]);
    setSelected(id);
    return id;
  }
  function addGeneration(
    position?: { x: number; y: number },
    source?: CardNode,
  ) {
    if (!config) return;
    const id = uid(),
      assetId = source?.data.asset_id || source?.data.output_id;
    const node: CardNode = {
      id,
      type: "card",
      position:
        position ||
        flow.screenToFlowPosition({ x: window.innerWidth / 2 - 120, y: 200 }),
      data: {
        kind: "generation",
        label:
          "影片生成 " +
          (nodes.filter((n) => n.data.kind === "generation").length + 1),
        spec: { ...defaultTemplate(config,"video",defaults(config)), ...(assetId?{mode:"Ref2VA" as const}:{}) },
      },
    };
    dirty();
    setNodes((n) => [...n, node]);
    if (source && assetId)
      setEdges((e) => [...e, makeEdge(source.id, id, assetId)]);
    setSelected(id);
    setInspectorTab("edit");
  }
  function addDirector(){const id=uid();dirty();setNodes(old=>[...old,{id,type:'card',position:flow.screenToFlowPosition({x:window.innerWidth/2-200,y:150}),style:{width:540,height:540},data:{kind:'director',label:'Motion Context 導演台',segments:[]}}]);setSelected(id);}
  function addSegment(owner:string){
    const parent=nodes.find(n=>n.id===owner);if(!parent||!config)return;
    const ids=(parent.data.segments||[]) as string[], previous=nodes.find(n=>n.id===ids.at(-1)),id=uid();
    const spec={...defaultTemplate(config,"video",defaults(config)),...(previous?.data.spec||{}),motion_context:false,context_run_id:null,context_video_asset_id:null};
    dirty();setNodes(old=>[...old.map(n=>n.id===owner?{...n,data:{...n.data,segments:[...ids,id]}}:n),{id,type:'card',position:{x:parent.position.x+600,y:parent.position.y+ids.length*300},data:{kind:'generation',label:'導演台第 '+(ids.length+1)+' 段',spec}}]);
    if(previous)setEdges(old=>[...old,...old.filter(e=>e.target===previous.id&&e.targetHandle!=='prompt').map(e=>({...structuredClone(e),id:uid(),target:id}))]);
  }
  function presetBase(category:string,spec:any){
    if(category==='video'){const {prompt,...parameters}=defaults(config!);return parameters;}
    const catalog=category==='image'?config?.image_workflows:config?.audio_workflows;
    const definition=catalog?.find(d=>d.id===spec.workflow);
    return {kind:category==='image'?'image':'audio',provider:spec.provider,workflow:spec.workflow,values:Object.fromEntries((definition?.fields||[]).filter((f:any)=>!['text','audio','image'].includes(f.type)).map((f:any)=>[f.key,f.default])),...(category==='image'?{loras:[]}:{})};
  }
  function addAudio(category: 'music'|'tts', position?:{x:number;y:number}) {
    const definition=config?.audio_workflows?.find(d=>d.category===category);
    if(!definition)return;
    const id=uid();dirty();
    setNodes(old=>[...old,{id,type:'card',position:position||flow.screenToFlowPosition({x:window.innerWidth/2,y:200}),style:{width:360,height:250},data:{kind:category,label:category==='music'?'音樂生成':'語音生成',audio_spec:defaultTemplate(config,category,{kind:'audio',provider:config?.video_defaults?.provider||'comfyui',workflow:definition.id,values:Object.fromEntries(definition.fields.filter((f:any)=>f.type!=='audio').map((f:any)=>[f.key,f.default??''])),audio_asset_id:null})}}]);setSelected(id);
  }
  function addImage(position?:{x:number;y:number}) {
    const d=config?.image_workflows?.[0];if(!d)return;const id=uid();dirty();
    setNodes(old=>[...old,{id,type:'card',position:position||flow.screenToFlowPosition({x:window.innerWidth/2,y:200}),style:{width:360,height:260},data:{kind:'imagegen',label:'圖片生成',image_spec:defaultTemplate(config,'image',imageDefaults(d,config?.video_defaults?.provider||'comfyui'))}}]);setSelected(id);
  }
  function resetImage(id:string,spec:any){dirty();setEdges(old=>old.filter(e=>e.target!==id));patch(id,{image_spec:spec});}
  function bindAudio(id:string,field:string,sourceId:string) {
    const source=nodes.find(n=>n.id===sourceId);dirty();
    setEdges(old=>[...old.filter(e=>!(e.target===id&&e.targetHandle===field)),...(source?[{...makeEdge(source.id,id,source.data.asset_id||source.data.output_id||''),targetHandle:field}]:[])]);
  }
  function resetAudio(id:string,spec:any){dirty();setEdges(old=>old.filter(e=>e.target!==id));patch(id,{audio_spec:spec});}
  function makeEdge(source: string, target: string, assetId: string): Edge {
    return {
      id: uid(),
      source,
      target,
      type: "default",
      markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
      data: { asset_id: assetId, role: "reference" },
    };
  }
  function connect(connection: Connection) {
    const source = nodes.find((n) => n.id === connection.source),
      target = nodes.find((n) => n.id === connection.target),
      assetId = source?.data.asset_id || source?.data.output_id;
    if(target?.data.kind==='generation'&&source?.data.kind==='text'&&target.id!==source.id){bindAudio(target.id,'prompt',source.id);return;}
    if(target?.data.kind==='generation'&&connection.targetHandle==='prompt'){notify('提示詞輸入只接受文字節點');return;}
    if(target?.data.image_spec&&source&&source.id!==target.id){
      const d=config?.image_workflows?.find(d=>d.id===target.data.image_spec.workflow),f=d?.fields.find((f:any)=>f.key===connection.targetHandle),asset=assets.find(a=>a.id===assetId);
      if((f?.type==='text'&&source.data.kind==='text')||(f?.type==='image'&&asset?.kind==='image'))bindAudio(target.id,f.key,source.id);else notify('請連接此欄位對應的文字或圖片節點');return;
    }
    if(target&&(target.data.kind==='music'||target.data.kind==='tts')&&source&&source.id!==target.id){
      const def=config?.audio_workflows?.find(d=>d.id===target.data.audio_spec?.workflow);
      const field=def?.fields.find((f:any)=>f.key===connection.targetHandle);
      const media=assets.find(a=>a.id===assetId);
      if((field?.type==='text'&&source.data.kind==='text')||(field?.type==='audio'&&media?.kind==='audio')) bindAudio(target.id,field.key,source.id);
      else notify('此輸入需要'+(field?.type==='text'?'文字節點':'聲音素材'));
      return;
    }
    if (
      !assetId ||
      !target ||
      (target.data.kind !== "generation" && target.data.kind !== "text") ||
      source?.id === target.id
    )
      return;
    if (
      edges.some((e) => e.target === target.id && e.data?.asset_id === assetId)
    ) {
      notify("這個素材已在引用面板中");
      return;
    }
    dirty();
    setEdges((e) => [...e, makeEdge(source!.id, target.id, assetId)]);
    if (target.data.spec?.mode === "T2VA")
      patch(target.id, { spec: { ...target.data.spec, mode: "Ref2VA" } });
    setSelected(target.id);
  }
  function duplicate(id: string) {
    const node = nodes.find((n) => n.id === id);
    if (!node) return;
    const copy = duplicateNode(node, edges);
    dirty();
    setNodes((n) => [...n.map((x) => ({ ...x, selected: false })), copy.node]);
    setEdges((e) => [...e, ...copy.edges]);
    setSelected(copy.node.id);
    notify("已複製節點，保留連線與參數");
  }
  function remove(id: string) {
    dirty();
    setNodes((n) => n.filter((x) => x.id !== id).map(x=>x.data.kind==='director'?{...x,data:{...x.data,segments:((x.data.segments||[]) as string[]).filter(child=>child!==id)}}:x));
    setEdges((e) => e.filter((x) => x.source !== id && x.target !== id));
    if (selected === id) setSelected(null);
  }
  function payload(id: string) {
    const n = nodes.find((x) => x.id === id)!;
    if(n.data.image_spec){
      const spec={...n.data.image_spec,image_assets:{...n.data.image_spec.image_assets},text_sources:{} as Record<string,string>};
      const fields=config?.image_workflows?.find(d=>d.id===spec.workflow)?.fields||[];
      for(const edge of edges.filter(e=>e.target===id)){const field=fields.find((f:any)=>f.key===edge.targetHandle);if(field?.type==='image')spec.image_assets[field.key]=edge.data?.asset_id;else if(field?.type==='text')spec.text_sources[field.key]=edge.source;}
      return spec;
    }
    if(n.data.kind==='text')return {...defaults(config!),prompt:n.data.text||'',mode:referenceRows(id,edges,assets).length?'Ref2VA':'T2VA',references:referenceRows(id,edges,assets).map((r:any)=>({asset_id:r.asset.id,role:r.role}))};
    if(n.data.audio_spec){
      const spec={...n.data.audio_spec,audio_assets:{...(n.data.audio_spec as any).audio_assets} as Record<string,string>,text_sources:{} as Record<string,string>};
      const audioFields=config?.audio_workflows?.find(d=>d.id===spec.workflow)?.fields.filter((f:any)=>f.type==='audio').map((f:any)=>f.key)||[];
      for(const edge of edges.filter(e=>e.target===id)){
        if(edge.targetHandle&&audioFields.includes(edge.targetHandle)){spec.audio_assets[edge.targetHandle]=edge.data?.asset_id as string;if(edge.targetHandle==='audio')spec.audio_asset_id=edge.data?.asset_id;}
        else if(edge.targetHandle)spec.text_sources[edge.targetHandle]=edge.source;
      }
      return spec;
    }
    const promptEdge=edges.find(e=>e.target===id&&e.targetHandle==='prompt');
    const promptNode=nodes.find(n=>n.id===promptEdge?.source);
    return {
      ...n.data.spec,
      ...(promptNode?{prompt:promptNode.data.text||'',prompt_source:promptNode.id}:{}),
      references: referenceRows(id, edges, assets).map((r: any) => ({
        asset_id: r.asset.id,
        role: r.role,
      })),
    };
  }
  async function generate(id: string, promptOverride?:string, overrides:any={}) {
    if (!project || pending.current.has(id)) return;
    pending.current.add(id);
    try {
      await save();
      const run = await api("/runs", {
        method: "POST",
        body: JSON.stringify({
          project_id: project.id,
          node_id: id,
          request_id: uid(),
          spec: {...payload(id), ...(nodes.find(n=>n.id===id)?.data.kind==='generation'?{motion_context:false,context_run_id:null,context_video_asset_id:null}:{}), ...overrides, ...(promptOverride!==undefined?{prompt:promptOverride,prompt_source:null}:{})},
        }),
      });
      setRuns((r) => [run, ...r]);
      setSelected(id);

      notify("已建立生成任務");
    } catch (e: any) {
      notify(e.message);
    } finally {
      pending.current.delete(id);
    }
  }
  async function uploadFiles(files: FileList | File[]) {
    if(!project)return;
    const uploadProjectId=project.id;
    setUploading(true);
    try {
      for (const [i, file] of Array.from(files).entries()) {
        const data = new FormData();
        data.append("file", file);
        const asset = await api("/assets?scope=project&project_id="+uploadProjectId, { method: "POST", body: data });
        setAssets((a) => [asset, ...a]);
        addAsset(
          asset,
          uploadOrigin.current ? {x: uploadOrigin.current.x + i * 32, y: uploadOrigin.current.y + i * 32} : flow.screenToFlowPosition({
            x: sidebar ? 410 + i * 32 : 190 + i * 32,
            y: 180 + i * 32,
          }),
        );
      }
      notify("素材已加入畫布");
    } catch (e: any) {
      notify(e.message);
    } finally {
      setUploading(false);
      uploadOrigin.current = null;
      if (fileInput.current) { fileInput.current.value = ""; fileInput.current.accept = "image/*,video/*,audio/*"; }
    }
  }
  function chooseAsset(asset: Asset, targetId?: string) {
    const current = nodes.find(n=>n.id===(targetId||selected));
    if (!current) return;
    const rows = referenceRows(current.id,edges,assets), spec=current.data.spec;
    api('/assets/'+asset.id+'/use',{method:'POST'}).catch(()=>{});
    if (rows.some((r: any) => r.asset.id === asset.id)) {
      dirty();
      setEdges(old=>old.filter(e=>!(e.target===current.id&&e.data?.asset_id===asset.id)));
      return;
    }
    let source = nodes.find(
      (n) => (n.data.asset_id || n.data.output_id) === asset.id,
    );
    let sourceId = source?.id;
    if (!sourceId)
      sourceId = addAsset(asset, {
        x: current.position.x - 370,
        y: current.position.y + rows.length * 70,
      });
    dirty();
    setEdges((e) => [...e, makeEdge(sourceId!, current.id, asset.id)]);
    if (spec?.mode === "T2VA")
      patch(current.id, { spec: { ...spec, mode: "Ref2VA" } });
    setSelected(current.id);
  }
  function reuseReferences(id:string,previous:any){
    const materialEdges:Edge[]=[];
    for(const ref of previous.references||[]){const asset=assets.find(a=>a.id===ref.asset_id&&!a.deleted);if(!asset){notify('部分舊素材已刪除或不在專案，請重新選擇');continue;}const source=nodes.find(n=>(n.data.asset_id||n.data.output_id)===asset.id);const sourceId=source?.id||addAsset(asset);materialEdges.push({...makeEdge(sourceId,id,asset.id),data:{asset_id:asset.id,role:ref.role||'reference'}});}
    dirty();setEdges(old=>[...old.filter(e=>e.target!==id||e.targetHandle==='prompt'),...materialEdges]);
    const n=nodes.find(n=>n.id===id);if(n?.data.spec)patch(id,{spec:{...n.data.spec,mode:materialEdges.length?(previous.mode==='FL2VA'?'FL2VA':'Ref2VA'):'T2VA'}});
  }
  function setRole(edgeId: string, role: string) {
    dirty();
    setEdges((e) =>
      e.map((x) => (x.id === edgeId ? { ...x, data: { ...x.data, role } } : x)),
    );
  }
  function reorder(edgeId: string, direction: number) {
    dirty();
    setEdges((old) => {
      const indices = old
        .map((e, i) => (e.target === selected ? i : -1))
        .filter((i) => i >= 0);
      const index = indices.findIndex((i) => old[i].id === edgeId),
        other = index + direction;
      if (other < 0 || other >= indices.length) return old;
      const next = [...old];
      [next[indices[index]], next[indices[other]]] = [
        next[indices[other]],
        next[indices[index]],
      ];
      return next;
    });
  }
  function insertMention(alias: string) {
    if (!spec) return;
    const input = promptInput.current;
    const end = input?.selectionStart ?? spec.prompt.length;
    const before = spec.prompt.slice(0, end).replace(/@[^\s@]*$/, "");
    patchSpec({ prompt: before + "@" + alias + " " + spec.prompt.slice(end) });
    setMention(false);
    input?.focus();
  }
  async function showSettings() {
    try {
      setSettings({ ...(await api("/settings")), models: config?.model_profiles, loras: config?.loras, runninghub_key: "", clear_runninghub_key: false });
      setSettingsOpen(true);
    } catch (e: any) {
      notify(e.message);
    }
  }
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest("input,textarea,select")) return;
      if ((event.ctrlKey || event.metaKey) && event.key === "d" && selected) {
        event.preventDefault();
        duplicate(selected);
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "s") {
        event.preventDefault();
        save().catch((e) => notify(e.message));
      }
      if (event.key === "Escape") {
        setCreateMenu(null);
        setLibraryPanel(null);
        setAssistantNode(null);
        setModal(null);
        setPreview(null);
        setSettingsOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selected, nodes, edges]);
  if (!config || !project)
    return (
      <div className="loading">
        <LoaderCircle className="spin" />
        正在開啟畫布…{toast && <p>{toast}</p>}
      </div>
    );
  const nodeRuns = runs
    .filter((r) => r.node_id === selected)
    .sort((a, b) => b.created_at - a.created_at);
  return (
    <TemplateContext.Provider value={{items:config?.node_templates||[],api,notify,baseDefaults:presetBase,refresh:async()=>setConfig(await api("/config"))}}><actions.Provider
      value={{ restoreVideo:(id,spec)=>{dirty();setEdges(old=>old.filter(e=>!(e.target===id&&e.targetHandle==='prompt')));patch(id,{spec:{...spec,_template_id:'',_template_name:'',prompt_source:null,motion_context:false,context_run_id:null,context_video_asset_id:null}});}, nodes, setSegments:(id,segments)=>patch(id,{segments}),addSegment,generateSegment:(id,previous)=>generate(id,undefined,{motion_context:true,context_run_id:previous||null,context_video_asset_id:null}),focusNode:id=>{setSelected(id);flow.fitView({nodes:[{id}],duration:250,maxZoom:1});}, editImage:(id,spec)=>patch(id,{image_spec:spec}), resetImage, editAudio:(id,spec)=>patch(id,{audio_spec:spec}), resetAudio, bindAudio, audioOutput:(id,asset)=>patch(id,{output_id:asset}), assets, runs, duplicate, preview: setModal, remove, generate, editText: (id, text) => patch(id, {text}), config, edges, editSpec: (id, value)=>{dirty();setNodes(old=>old.map(n=>n.id===id&&n.data.spec?{...n,data:{...n.data,spec:{...n.data.spec,...value}}}:n));}, pickReferences: id=>setLibraryPanel({scope:"project",target:id}), openAssistant: setAssistantNode, removeReference: edgeId=>{dirty();setEdges(old=>old.filter(e=>e.id!==edgeId));} }}
    >
      <main>
        <header className="topbar">
          <StudioInfo/>
          <span className="divider" />
          <button
            className="icon-button"
            title="切換側欄"
            onClick={() => setSidebar(!sidebar)}
          >
            {sidebar ? (
              <PanelLeftClose size={18} />
            ) : (
              <PanelLeftOpen size={18} />
            )}
          </button>
          <input
            className="project-name"
            aria-label="專案名稱"
            value={project.name}
            onChange={(e) => {
              dirty();
              setProject({ ...project, name: e.target.value });
            }}
          />
        </header>
        <section
          className="workspace"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
          }}
        >
          {sidebar && (
            <aside className="left-panel">
              <div className="sidebar-tabs">
                <button
                  className={tabName === "assets" ? "active" : ""}
                  onClick={() => setTabName("assets")}
                >
                  專案素材 <span>{assets.filter(a=>!a.deleted).length}</span>
                </button>
                <button
                  className={tabName === "projects" ? "active" : ""}
                  onClick={() => {
                    setTabName("projects");
                    refreshProjects();
                  }}
                >
                  專案
                </button>
              </div>
              {tabName === "assets" ? (
                <>
                  <button
                    className="upload-button"
                    disabled={uploading}
                    onClick={() => fileInput.current?.click()}
                  >
                    {uploading ? (
                      <LoaderCircle size={18} className="spin" />
                    ) : (
                      <Upload size={18} />
                    )}
                    匯入素材
                  </button>
                  <button onClick={()=>setLibraryPanel({scope:"project"})}>開啟素材管理面板</button>
                  <p className="sidebar-note">
                    圖片、影片、聲音
                    <br />
                    拖曳檔案至畫布也能加入
                  </p>
                  <div className="asset-library">
                    {assets.filter(a=>!a.deleted).map((asset) => (
                      <button
                        className="library-item"
                        key={asset.id}
                        title={asset.name}
                        onClick={() => addAsset(asset)}
                      >
                        <div className="library-thumb">
                          <Media asset={asset} />
                        </div>
                        <div>
                          <strong>{asset.name}</strong>
                          <small>
                            {kindNames[asset.kind]} ·{" "}
                            {asset.size
                              ? `${(asset.size / 1048576).toFixed(1)} MB`
                              : "生成結果"}
                          </small>
                        </div>
                        <Plus size={14} />
                      </button>
                    ))}
                    {!assets.length && (
                      <div className="library-empty">
                        <ImageIcon size={26} />
                        <p>留一個位置給你的靈感</p>
                        <small>加入第一個素材，開始連接鏡頭。</small>
                      </div>
                    )}
                  </div>
                  <div className="sidebar-bottom">
                    <span className="status-dot" />
                    素材與專案保存在本機
                  </div>
                </>
              ) : (
                <>
                  <button
                    className="upload-button"
                    onClick={() => newProject().catch((e) => notify(e.message))}
                  >
                    <Plus size={18} />
                    新增專案
                  </button>
                  <div className="project-list">
                    {projects.map(p=><div className="project-row" key={p.id}><button className={p.id===project.id?'active':''} onClick={()=>openProject(p.id).catch(e=>notify(e.message))}><FolderOpen size={17}/><span title={p.id===project.id?project.name:p.name}>{p.id===project.id?project.name:p.name}</span></button><button title={'刪除專案 '+p.name} onClick={()=>deleteProject(p.id).catch(e=>notify(e.message))}><Trash2 size={15}/></button></div>)}
                    {!!trashProjects.length&&<details><summary>專案回收區（{trashProjects.length}）</summary>{trashProjects.map(p=><div className="project-row" key={p.id}><span>{p.name}</span><button onClick={()=>api('/projects/'+p.id+'/restore',{method:'POST'}).then(refreshProjects).catch(e=>notify(e.message))}>還原</button><button onClick={async()=>{if(!window.confirm('永久刪除專案「'+p.name+'」及專屬素材、生成與提示詞紀錄？此動作無法還原。'))return;try{await api('/projects/'+p.id+'/permanent?confirm=true',{method:'DELETE'});await refreshProjects();}catch(e:any){notify(e.message);}}}>永久刪除</button></div>)}</details>}
                  </div>
                </>
              )}
            </aside>
          )}
          <div className="flow-wrap" onDoubleClick={(event) => {
              if (!(event.target as HTMLElement).classList.contains('react-flow__pane')) return;
              event.preventDefault();
              setCreateMenu({x: Math.min(event.clientX, window.innerWidth - 230), y: Math.min(event.clientY, window.innerHeight - 390), position: flow.screenToFlowPosition({x:event.clientX,y:event.clientY})});
            }}>
            {createMenu && <div role="menu" aria-label="新增節點" className="create-menu" style={{left:createMenu.x,top:createMenu.y}}>
              <span>新增至畫布</span>
              <button role="menuitem" onClick={() => { const id=uid(); dirty(); setNodes(n=>[...n,{id,type:'card',position:createMenu.position,style:{width:320,height:260},data:{kind:'text',label:'文字',text:''}}]); setSelected(id); setCreateMenu(null); }}>文字</button>
              {(['image','audio','video'] as const).map(kind=><button role="menuitem" key={kind} onClick={()=>{uploadOrigin.current=createMenu.position; if(fileInput.current){fileInput.current.accept=kind+'/*';fileInput.current.click();} setCreateMenu(null);}}>{kindNames[kind]}</button>)}
              <button role="menuitem" onClick={()=>{addGeneration(createMenu.position);setCreateMenu(null);}}>影片生成</button>
              <button role="menuitem" onClick={()=>{addImage(createMenu.position);setCreateMenu(null);}}>圖片生成 / 編輯</button>
              <button role="menuitem" onClick={()=>{addAudio('music',createMenu.position);setCreateMenu(null);}}>音樂生成</button>
              <button role="menuitem" onClick={()=>{addAudio('tts',createMenu.position);setCreateMenu(null);}}>TTS 語音生成</button>
            </div>}

            <ReactFlow
              nodes={nodes.map((node) => ({
                ...node,
                selected: node.id === selected,
                ...((node.data.kind==='music'||node.data.kind==='tts'||assets.find(a=>a.id===(node.data.asset_id||node.data.output_id))?.kind==='audio')?{style:{...node.style,height:136}}:{}),
              }))}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={(changes) => {
                if (
                  changes.some(
                    (c) => c.type !== "select" && (c.type !== "dimensions" || !!c.resizing || !!c.setAttributes),
                  )
                )
                  dirty();
                setNodes((n) => applyNodeChanges(changes, n));
              }}
              onEdgesChange={(changes) => {
                dirty();
                setEdges((e) => applyEdgeChanges(changes, e));
              }}
              onConnect={connect}
              onConnectEnd={(event, state) => {
                if (
                  state.isValid ||
                  state.fromHandle?.type !== "source" ||
                  state.toNode
                )
                  return;
                const mouse =
                  "changedTouches" in event ? event.changedTouches[0] : event;
                const source = nodes.find((n) => n.id === state.fromNode?.id);
                if (source && (source.data.asset_id || source.data.output_id))
                  addGeneration(
                    flow.screenToFlowPosition({
                      x: mouse.clientX,
                      y: mouse.clientY,
                    }),
                    source,
                  );
              }}
              onNodeClick={(_, n) => {
                setCreateMenu(null);
                setSelected(n.id);
                setInspectorTab("edit");
                setPreview(null);
              }}
              onNodeDoubleClick={(event, n) => {
                if((event.target as HTMLElement).closest("input,textarea,select,button,.node-composer,video"))return;
                const a = assets.find(
                  (a) => a.id === (n.data.asset_id || n.data.output_id),
                );
                if (a) setModal(a);
              }}
              onPaneClick={() => {setSelected(null);setCreateMenu(null);}}
              zoomOnDoubleClick={false}
              onMoveEnd={() => {
                dirty();
                save().catch((e) => notify(e.message));
              }}
              minZoom={0.15}
              maxZoom={2}
              defaultViewport={project.viewport}
              deleteKeyCode={["Backspace", "Delete"]}
              onNodesDelete={(ns) => {
                dirty();
                setNodes(old=>old.map(x=>x.data.kind==='director'?{...x,data:{...x.data,segments:((x.data.segments||[]) as string[]).filter(child=>!ns.some(n=>n.id===child))}}:x));
                setEdges((e) =>
                  e.filter(
                    (x) =>
                      !ns.some((n) => n.id === x.source || n.id === x.target),
                  ),
                );
                if (ns.some((n) => n.id === selected)) setSelected(null);
              }}
              colorMode="dark"
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#303335" gap={24} size={1} />
              <MiniMap
                pannable
                zoomable
                nodeColor={(n) =>
                  n.data.kind === "generation" ? "#ddd" : "#656565"
                }
                maskColor="#101112c9"
              />
              <Controls showInteractive={false} />
            </ReactFlow>
            <div className="canvas-toolbar">
              <button title="儲存專案" onClick={()=>save().then(()=>notify('專案已儲存')).catch(e=>notify(e.message))}><Save size={18}/></button>
              <button title="專案素材" onClick={()=>setLibraryPanel({scope:'project'})}><FolderOpen size={18}/></button>
              <button title="新增 Motion Context 導演台（實驗）" onClick={addDirector}>導演</button><button title="拼接分鏡圖" onClick={()=>setMediaTool({mode:'stitch'})}><LayoutGrid size={18}/></button>
              <button title="共用資產" onClick={()=>setLibraryPanel({scope:'shared'})}><ImageIcon size={18}/></button>
              <button title="專案生成內容" onClick={()=>setInspectorVisible(!inspectorVisible)}><PanelLeftOpen size={18}/></button>
              <button title="節點模板" onClick={()=>setTemplatesOpen(true)}>模板</button>
              <button title="連線設定" onClick={showSettings}><Settings size={18}/></button>
              <span className="toolbar-save-state" title={saving} aria-label={saving}><i className={saving==='已儲存'?'saved':''}/></span>
              <span />

              <button title="新增影片生成節點" onClick={() => addGeneration()}>
                <Film size={18} />
                <span>影片生成</span>
                <Plus size={14} />
              </button>
              <span />
              <button
                title="上傳素材"
                onClick={() => fileInput.current?.click()}
              >
                <Upload size={18} />
              </button>
              <button
                title="檢視全部節點"
                onClick={() => flow.fitView({ padding: 0.25, duration: 350 })}
              >
                <Maximize2 size={18} />
              </button>
            </div>
            {!nodes.length && (
              <div className="empty-canvas">
                <span className="eyebrow">YOUR NEXT FRAME</span>
                <h1>把靈感，連成畫面。</h1>
                <p>
                  從一張圖、一段聲音，或一句想像開始。
                  <br />
                  在無限畫布上，串起你的下一個故事。
                </p>
                <div>
                  <button
                    className="primary"
                    onClick={() => fileInput.current?.click()}
                  >
                    <Upload size={17} />
                    加入素材
                  </button>
                  <button onClick={() => addGeneration()}>
                    <Plus size={17} />
                    從文字開始
                  </button>
                </div>
                <small>拖曳平移 · 滾輪縮放 · 從素材右側圓點拉出連線</small>
              </div>
            )}
            <div className="canvas-caption">
              <MousePointer2 size={12} />
              雙擊新增 <span>·</span> 滾輪縮放 <span>·</span> 拖曳節點邊角調整尺寸
            </div>
          </div>
          {inspectorVisible && (
            <aside className="inspector" aria-label="專案生成內容">
              <div className="inspector-heading">
                <div><strong>專案生成內容</strong><p className="help">最新生成排在最上方 · {runs.length} 筆</p></div>
                <button title="關閉面板" onClick={()=>setInspectorVisible(false)}><X size={18}/></button>
              </div>
              <div className="inspector-body history-list">
                {!runs.length && <div className="history-empty"><Clock3 size={30}/><p>此專案尚無生成內容</p><small>影片、音樂與語音生成結果會顯示在這裡。</small></div>}
                {[...runs].sort((a,b)=>b.created_at-a.created_at).map(run=>{
                  const audioSpec=run.spec as Spec & {kind?:string;workflow?:string};
                  const title=nodes.find(n=>n.id===run.node_id)?.data.label || (audioSpec.kind==='image' ? config.image_workflows?.find(w=>w.id===audioSpec.workflow)?.name || '圖片生成' : audioSpec.kind==='audio' ? config.audio_workflows?.find(w=>w.id===audioSpec.workflow)?.name || '音訊生成' : '影片生成');
                  return <div className="history-card" key={run.id}>
                    <header><strong>{title}</strong><span>{new Date(run.created_at*1000).toLocaleString('zh-TW')}</span></header>
                    <div className={'history-status '+run.status}>{activeStatuses.includes(run.status)&&<LoaderCircle size={13} className="spin"/>}{run.stage}{run.progress!==null&&` · ${run.progress}%`}</div>
                    {run.outputs.map(asset=><div className="history-output" key={asset.id}>
                      <div className="project-result-media"><Media asset={asset} controls/></div>
                      <div><button onClick={()=>setModal(asset)}>放大查看</button><button onClick={()=>addAsset(asset)}>加入畫布</button><a href={asset.url} download={asset.name} aria-label="下載生成結果"><Download size={14}/></a></div>
                    </div>)}
                    <Usage run={run}/>
                    {run.error&&<p className="error-message">{run.error}</p>}
                    {run.remote_id&&run.status!=='success'&&!activeStatuses.includes(run.status)&&<button onClick={()=>api('/runs/'+run.id+'/resume',{method:'POST'}).then(()=>notify('已恢復查詢')).catch(e=>notify(e.message))}>恢復查詢</button>}
                  </div>;
                })}
              </div>
            </aside>
          )}
        </section>
        <input
          ref={fileInput}
          type="file"
          multiple
          accept="image/png,image/jpeg,image/webp,video/*,audio/*"
          hidden
          onChange={(e) => e.target.files && uploadFiles(e.target.files)}
        />
        {assistantNode && nodes.some(n=>n.id===assistantNode) && <PromptPanel onPickReferences={()=>setLibraryPanel({scope:'project',target:assistantNode})} onRemoveReference={(edgeId:string)=>{dirty();setEdges(es=>es.filter(e=>e.id!==edgeId));}} onReuseReferences={(previous:any)=>reuseReferences(assistantNode,previous)} textMode={nodes.find(n=>n.id===assistantNode)?.data.kind==='text'} key={assistantNode} projectId={project.id} nodeId={assistantNode} api={api} getSpec={()=>payload(assistantNode)} saveProject={save} notify={notify} refs={referenceRows(assistantNode,edges,assets)} requirement={nodes.find(n=>n.id===assistantNode)?.data.assistant_requirement||''} onRequirement={(value:string)=>patch(assistantNode,{assistant_requirement:value})} onClose={()=>setAssistantNode(null)} onApply={async(text:string,submit:boolean)=>{const node=nodes.find(n=>n.id===assistantNode);if(node?.data.kind==='text'){patch(assistantNode,{text});}else if(node?.data.spec){const bound=edges.find(e=>e.target===assistantNode&&e.targetHandle==='prompt');if(bound)patch(bound.source,{text});patch(assistantNode,{spec:{...node.data.spec,prompt:text}});if(submit)await generate(assistantNode,text);}}}/>}
        {mediaTool&&<MediaTools key={mediaTool.asset?.id||'stitch'} {...mediaTool} assets={assets} projectId={project.id} api={api} onClose={()=>setMediaTool(null)} onSaved={(asset:Asset)=>{setAssets(old=>[...old,asset]);addAsset(asset);notify('已另存新素材，原檔保留');}}/>}
        {libraryPanel && <LibraryPanel onEdit={(asset:Asset)=>setMediaTool({mode:'crop',asset})} projectId={project.id} initialScope={libraryPanel.scope} referenceMode={!!libraryPanel.target} selectedIds={referenceRows(libraryPanel.target,edges,assets).map((r:any)=>r.asset.id)} api={api} Media={Media} notify={notify} onClose={()=>setLibraryPanel(null)} onChanged={()=>api('/assets?project_id='+project.id).then(setAssets).catch(e=>notify(e.message))} onSelect={(asset:Asset)=>libraryPanel.target?chooseAsset(asset,libraryPanel.target):addAsset(asset)}/>}
        {toast && (
          <div className="toast" role="status">
            {toast}
            <button title="關閉訊息" onClick={() => setToast("")}>
              <X size={14} />
            </button>
          </div>
        )}
        {uploading && (
          <div className="upload-progress">
            <LoaderCircle size={16} className="spin" />
            正在匯入與處理素材…
          </div>
        )}
        {modal && (
          <div className="modal-overlay" onClick={() => setModal(null)}>
            <div
              className="media-modal"
              role="dialog"
              aria-label="素材放大預覽"
              onClick={(e) => e.stopPropagation()}
            >
              <header>
                <span>{modal.name}</span>{modal.kind==='video'&&<button onClick={()=>{setMediaTool({mode:'extract',asset:modal});setModal(null);}}>抽出聲音</button>}<button title="裁切並另存" onClick={()=>{setMediaTool({mode:'crop',asset:modal});setModal(null);}}><Scissors size={18}/></button>
                <a href={modal.url} download={modal.name}>
                  <Download size={18} />
                </a>
                <button title="關閉預覽" onClick={() => setModal(null)}>
                  <X size={20} />
                </button>
              </header>
              <Media asset={modal} controls />
            </div>
          </div>
        )}
        {preview && (
          <div className="modal-overlay" onClick={() => setPreview(null)}>
            <div
              className="dialog mapping-dialog"
              role="dialog"
              aria-label="素材對應檢查"
              onClick={(e) => e.stopPropagation()}
            >
              <header>
                <h2>素材對應檢查</h2>
                <button onClick={() => setPreview(null)} title="關閉">
                  <X size={20} />
                </button>
              </header>
              <p className="help">以下是實際送給 T8 的提示詞與標籤。</p>
              {preview.mapping.map((r: any) => (
                <div className="mapping-row" key={r.tag}>
                  <strong>@{r.alias}</strong>
                  <span>→ {r.tag}</span>
                  <small>{r.name}</small>
                </div>
              ))}
              <pre>{preview.prompt}</pre>
              <button
                onClick={() => {
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(
                    new Blob([JSON.stringify(preview.workflow, null, 2)], {
                      type: "application/json",
                    }),
                  );
                  a.download = "h3-workflow-preview.json";
                  a.click();
                  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
                }}
              >
                <Download size={15} />
                下載工作流 JSON
              </button>
            </div>
          </div>
        )}
        {templatesOpen&&config&&<TemplateManager config={config} videoDefault={defaults(config)} onClose={()=>setTemplatesOpen(false)}/>}
        {settingsOpen && settings && (
          <div className="modal-overlay">
            <div className="dialog" role="dialog" aria-label="連線設定">
              <header>
                <div>
                  <span className="eyebrow">CONNECTIONS</span>
                  <h2>連接你的生成引擎</h2>
                </div>
                <button title="關閉設定" onClick={() => setSettingsOpen(false)}>
                  <X size={20} />
                </button>
              </header>
              <p className="help">
                API Key 僅由本機後端保存與使用，不會寫入專案或工作流。
              </p>
              <div className="connection-block">
                <h3>
                  <span className="connection-icon">C</span>本機 ComfyUI
                </h3>
                <label>
                  服務網址
                  <input
                    value={settings.comfy_url}
                    onChange={(e) =>
                      setSettings({ ...settings, comfy_url: e.target.value })
                    }
                  />
                </label>
                <button
                  onClick={async () => {
                    try {
                      await api("/settings", {
                        method: "PUT",
                        body: JSON.stringify({
                          ...settings,
                          runninghub_key: settings.runninghub_key || undefined,
                        }),
                      });
                      const r = await api("/connections/check", {
                        method: "POST",
                      });
                      notify(
                        r.ok
                          ? r.missing.length
                            ? "已連線；缺少節點：" + r.missing.join(", ")
                            : "ComfyUI 已連線，必要節點齊全"
                          : "連線失敗：" + r.error,
                      );
                    } catch (e: any) {
                      notify(e.message);
                    }
                  }}
                >
                  <Link2 size={14} />
                  儲存並測試 ComfyUI
                </button>
              </div>
              <div className="connection-block">
                <h3>
                  <span className="connection-icon rh">R</span>RunningHub
                </h3>
                <label>
                  API 網址
                  <select
                    value={settings.runninghub_url}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        runninghub_url: e.target.value,
                      })
                    }
                  >
                    <option>https://www.runninghub.cn</option>
                    <option>https://www.runninghub.ai</option>
                  </select>
                </label>
                <label>
                  API Key{" "}
                  {settings.has_key && (
                    <span className="key-saved">已設定</span>
                  )}
                  <input
                    type="password"
                    autoComplete="off"
                    placeholder={
                      settings.has_key
                        ? "留空保留現有金鑰"
                        : "貼上 RunningHub API Key"
                    }
                    value={settings.runninghub_key}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        runninghub_key: e.target.value, clear_runninghub_key: false,
                      })
                    }
                  />
                </label>
                <button onClick={()=>setSettings({...settings,runninghub_key:'',clear_runninghub_key:true,has_key:false})}>{settings.clear_runninghub_key?'儲存後將移除 API Key':'移除 RunningHub API Key'}</button>
                <label>
                  工作流 ID（必填）
                  <input
                    value={settings.workflow_id}
                    onChange={(e) =>
                      setSettings({ ...settings, workflow_id: e.target.value })
                    }
                  />
                </label>
                <label>
                  運算規格
                  <select
                    value={settings.instance_type}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        instance_type: e.target.value,
                      })
                    }
                  >
                    <option value="default">standard · 24 GB（預設）</option>
                    <option value="plus">plus · 48 GB</option>
                    <option value="ultra">ultra · 84 GB</option>
                  </select>
                </label>
              </div>
              <ModelSettings settings={settings} onChange={setSettings}/>
              <AssistantSettingsPanel api={api} notify={notify}/>
              <AutomationSettings api={api} notify={notify}/><div className="connection-block"><h3>Motion Context RunningHub 工作流 ID</h3><label>延續影片工作流<input value={settings.motion_workflow_id||''} onChange={e=>setSettings({...settings,motion_workflow_id:e.target.value})}/></label><p className="help">導演台使用 MP4 Motion Context 工作流，將前段影片的影格與聲音作為上下文。RunningHub 必填；本機 ComfyUI 不需要 ID。只存本機，不包含在分享包。</p></div><div className="connection-block"><h3>圖片生成 / 編輯 RunningHub 工作流 ID</h3><p className="help">只存於本機設定，分享包不含這些 ID。</p>{config.image_workflows?.map(d=><label key={d.id}>{d.name}<input value={settings.image_workflow_ids?.[d.id]||''} onChange={e=>setSettings({...settings,image_workflow_ids:{...settings.image_workflow_ids,[d.id]:e.target.value}})}/></label>)}</div>
              <div className="connection-block"><h3>音樂 / TTS RunningHub 工作流 ID</h3><p className="help">只保存在本機設定；本機 ComfyUI 不需要 ID。</p>{config.audio_workflows?.map(d=><label key={d.id}>{d.name}<input value={settings.audio_workflow_ids?.[d.id]||''} onChange={e=>setSettings({...settings,audio_workflow_ids:{...settings.audio_workflow_ids,[d.id]:e.target.value}})}/></label>)}</div>
              <VideoDefaults config={config} value={{...defaults(config),...settings.video_defaults}} onChange={(v:any)=>setSettings({...settings,video_defaults:v})}/>
              <button
                className="primary"
                onClick={async () => {
                  try {
                    await api("/settings", {
                      method: "PUT",
                      body: JSON.stringify({
                        ...settings,
                        runninghub_key: settings.runninghub_key || undefined,
                      }),
                    });
                    setConfig(await api("/config"));
                    setSettingsOpen(false);
                    notify("連線設定已儲存");
                  } catch (e: any) {
                    notify(e.message);
                  }
                }}
              >
                <Check size={16} />
                儲存設定
              </button>
            </div>
          </div>
        )}
      </main>
    </actions.Provider></TemplateContext.Provider>
  );
}
createRoot(document.getElementById("root")!).render(
  <ReactFlowProvider>
    <App />
  </ReactFlowProvider>,
);

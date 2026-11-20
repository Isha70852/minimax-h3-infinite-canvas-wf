import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Panel,useReactFlow,useStore} from '@xyflow/react';

/** Overview map whose bounds follow the nodes, not the viewport. React Flow's own
 *  MiniMap fits the union of nodes and viewport, so zooming out shrinks the nodes to a
 *  sliver. Here the nodes always fill at least two thirds of the map; a viewport larger
 *  than that is simply clipped. Click or drag to pan; wheel to zoom. */
const MIN_FILL=2/3, PAD=1.08;
const nodesKey=(s:any)=>{const out:string[]=[];s.nodeLookup.forEach((n:any)=>{if(n.hidden)return;const w=n.measured?.width??n.width??0,h=n.measured?.height??n.height??0;if(!w||!h)return;const p=n.internals.positionAbsolute;
  out.push(`${Math.round(p.x)},${Math.round(p.y)},${Math.round(w)},${Math.round(h)},${n.data?.kind==='generation'?1:0},${n.data?.kind==='group'?1:0}`);});return out.join(';');};

export function CanvasMiniMap(){
  const flow=useReactFlow();
  const key=useStore(nodesKey);
  const [tx,ty,zoom]=useStore((s:any)=>s.transform);
  const W=useStore((s:any)=>s.width),H=useStore((s:any)=>s.height);
  const ref=useRef<SVGSVGElement>(null);
  const [size,setSize]=useState({w:145,h:95});
  useEffect(()=>{const el=ref.current;if(!el)return;const ro=new ResizeObserver(()=>setSize({w:el.clientWidth||145,h:el.clientHeight||95}));ro.observe(el);return ()=>ro.disconnect();},[]);
  const rects=useMemo(()=>key?key.split(';').map(r=>{const [x,y,w,h,gen,group]=r.split(',').map(Number);return {x,y,w,h,gen,group};}):[],[key]);
  const view={x:-tx/zoom,y:-ty/zoom,w:(W||1)/zoom,h:(H||1)/zoom};
  const box=useMemo(()=>{
    const {w:mw,h:mh}=size;
    if(!rects.length)return {x:view.x,y:view.y,s:Math.max(view.w/mw,view.h/mh)};
    const nx=Math.min(...rects.map(r=>r.x)),ny=Math.min(...rects.map(r=>r.y)),nr=Math.max(...rects.map(r=>r.x+r.w)),nb=Math.max(...rects.map(r=>r.y+r.h));
    const fit=Math.max((nr-nx)/mw,(nb-ny)/mh,1e-6);
    // Show as much of the viewport as fits while the nodes keep >= 2/3 of the map.
    const ux=Math.min(nx,view.x),uy=Math.min(ny,view.y),ur=Math.max(nr,view.x+view.w),ub=Math.max(nb,view.y+view.h);
    const s=Math.min(Math.max(Math.max((ur-ux)/mw,(ub-uy)/mh),fit*PAD),fit/MIN_FILL);
    const vw=s*mw,vh=s*mh,clamp=(v:number,lo:number,hi:number)=>Math.min(Math.max(v,lo),hi);
    return {x:clamp((ux+ur)/2-vw/2,nr-vw,nx),y:clamp((uy+ub)/2-vh/2,nb-vh,ny),s};
  },[rects,size,view.x,view.y,view.w,view.h]);
  const toFlow=(e:{clientX:number;clientY:number})=>{const r=ref.current!.getBoundingClientRect();return {x:box.x+(e.clientX-r.left)*box.s,y:box.y+(e.clientY-r.top)*box.s};};
  const centerOn=(p:{x:number;y:number})=>{const z=flow.getZoom();flow.setViewport({x:(W||0)/2-p.x*z,y:(H||0)/2-p.y*z,zoom:z});};
  const drag=useRef(false);
  useEffect(()=>{const el=ref.current;if(!el)return;const onWheel=(e:WheelEvent)=>{e.preventDefault();e.stopPropagation();e.deltaY<0?flow.zoomIn({duration:0}):flow.zoomOut({duration:0});};
    el.addEventListener('wheel',onWheel,{passive:false});return ()=>el.removeEventListener('wheel',onWheel);},[flow]);
  const {w:mw,h:mh}=size,vbw=mw*box.s,vbh=mh*box.s;
  const outer=`M${box.x-vbw},${box.y-vbh}h${vbw*3}v${vbh*3}h${-vbw*3}z`;
  const hole=`M${view.x},${view.y}h${view.w}v${view.h}h${-view.w}z`;
  return <Panel position="bottom-right" className="react-flow__minimap canvas-minimap">
    <svg ref={ref} role="img" aria-label="畫布小地圖（點擊或拖曳移動視角，滾輪縮放）" viewBox={`${box.x} ${box.y} ${vbw} ${vbh}`} preserveAspectRatio="none"
      onPointerDown={e=>{drag.current=true;e.currentTarget.setPointerCapture(e.pointerId);centerOn(toFlow(e));}}
      onPointerMove={e=>{if(drag.current)centerOn(toFlow(e));}}
      onPointerUp={e=>{drag.current=false;e.currentTarget.releasePointerCapture(e.pointerId);}}>
      {rects.map((r,i)=><rect key={i} x={r.x} y={r.y} width={r.w} height={r.h} rx={6*box.s} className={'canvas-minimap-node'+(r.gen?' gen':'')+(r.group?' group':'')}/>)}
      <path d={outer+hole} fillRule="evenodd" className="canvas-minimap-mask"/>
      <rect x={view.x} y={view.y} width={view.w} height={view.h} fill="none" className="canvas-minimap-view" vectorEffect="non-scaling-stroke"/>
    </svg>
  </Panel>;
}

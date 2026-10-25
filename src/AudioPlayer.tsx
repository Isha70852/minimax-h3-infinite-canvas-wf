import React,{useRef,useState} from 'react';
import {Play,Pause,Volume2,VolumeX} from 'lucide-react';
const time=(s:number)=>Number.isFinite(s)?`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`:'0:00';
export function AudioPlayer({src,label='聲音播放',startMs=0,endMs}:{src:string;label?:string;startMs?:number;endMs?:number}){
  const ref=useRef<HTMLAudioElement>(null),[playing,setPlaying]=useState(false),[duration,setDuration]=useState(0),[position,setPosition]=useState(0),[muted,setMuted]=useState(false),[error,setError]=useState('');
  return <div className="compact-player nodrag nowheel" onClick={e=>e.stopPropagation()} onDoubleClick={e=>e.stopPropagation()}>
    <audio ref={ref} src={src} preload="metadata" muted={muted} onLoadedMetadata={e=>setDuration(Number.isFinite(e.currentTarget.duration)?e.currentTarget.duration:0)} onTimeUpdate={e=>{setPosition(e.currentTarget.currentTime);if(endMs&&e.currentTarget.currentTime>=endMs/1000)e.currentTarget.pause();}} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)} onError={()=>setError('瀏覽器無法播放此音檔')}/>
    <button className="audio-play" aria-label={playing?'暫停':'播放'} onClick={()=>{if(playing)ref.current?.pause();else if(ref.current){if(ref.current.currentTime<startMs/1000||(endMs&&ref.current.currentTime>=endMs/1000))ref.current.currentTime=startMs/1000;ref.current.play().catch(()=>setError('無法播放，請確認音訊格式'));}}}>{playing?<Pause size={17}/>:<Play size={17}/>}</button>
    <div className="audio-timeline"><input aria-label={label+'進度'} type="range" min={0} max={duration||1} step={.001} value={Math.min(position,duration||1)} onChange={e=>{const value=Number(e.target.value);if(ref.current)ref.current.currentTime=value;setPosition(value);}} style={{'--played':`${duration?position/duration*100:0}%`} as React.CSSProperties}/><div><span>{error||time(position)}</span><span>{time(duration)}</span></div></div>
    <button aria-label={muted?'開啟聲音':'靜音'} onClick={()=>setMuted(!muted)}>{muted?<VolumeX size={16}/>:<Volume2 size={16}/>}</button>
  </div>;
}

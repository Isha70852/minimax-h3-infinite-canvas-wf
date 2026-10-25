import {Input,BlobSource,ALL_FORMATS,Output,BufferTarget,Conversion,Mp4OutputFormat,WebMOutputFormat,WavOutputFormat,canEncodeVideo,canEncodeAudio} from 'mediabunny';

export async function trimMedia(blob:Blob,kind:string,startMs:number,endMs:number,onProgress:(n:number)=>void,onConversion:(c:Conversion)=>void){
  if(!Number.isInteger(startMs)||!Number.isInteger(endMs)||startMs<0||endMs<=startMs)throw Error('請輸入有效的起訖毫秒，結束需大於開始。');
  const input=new Input({source:new BlobSource(blob),formats:ALL_FORMATS});
  try{
    const duration=await input.computeDuration();
    if(endMs>Math.ceil(duration*1000))throw Error('結束時間超出素材長度。');
    const target=new BufferTarget();
    const hasAudio=!!await input.getPrimaryAudioTrack();
    if(kind==='audio'&&!hasAudio)throw Error('此素材沒有可抽出的音軌。');
    const mp4=kind==='video'&&await canEncodeVideo('avc')&&(!hasAudio||await canEncodeAudio('aac'));
    const format=kind==='audio'?new WavOutputFormat():mp4?new Mp4OutputFormat():new WebMOutputFormat();
    const output=new Output({format,target});
    const conversion=await Conversion.init({input,output,tracks:'primary',trim:{start:startMs/1000,end:endMs/1000},copy:false,
      video:kind==='audio'?{discard:true}:{codec:mp4?'avc':'vp9',forceTranscode:true},
      audio:{codec:kind==='audio'?'pcm-s16':mp4?'aac':'opus',forceTranscode:true},showWarnings:false});
    if(!conversion.isValid||conversion.discardedTracks.some(t=>!(kind==='audio'&&t.track.isVideoTrack())))throw Error('瀏覽器不支援此素材的解碼或輸出編碼，未另存或丟棄音軌。請改用最新版 Chrome / Edge。');
    onConversion(conversion);conversion.onProgress=(value)=>onProgress(Math.round(value*100));
    await conversion.execute();
    if(!target.buffer)throw Error('未產生輸出檔案。');
    return {blob:new Blob([target.buffer],{type:kind==='audio'?'audio/wav':mp4?'video/mp4':'video/webm'}),extension:kind==='audio'?'wav':mp4?'mp4':'webm'};
  }finally{input.dispose();}
}

export const canvasBlob=(canvas:HTMLCanvasElement)=>new Promise<Blob>((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('圖片輸出失敗')),'image/png'));
export async function loadBitmap(url:string){const response=await fetch(url);if(!response.ok)throw Error('無法讀取素材');return createImageBitmap(await response.blob());}
export function checkCanvasSize(width:number,height:number){if(!Number.isInteger(width)||!Number.isInteger(height)||width<64||height<64||width>8192||height>8192||width*height>33554432)throw Error('尺寸需為 64–8192 整數像素，總面積不超過 3200 萬像素。');}
export function drawStoryboard(canvas:HTMLCanvasElement,images:ImageBitmap[],width:number,height:number,columns:number){
  checkCanvasSize(width,height);
  if(!images.length)throw Error('請至少選一張圖片');
  columns=Math.min(Math.max(1,Math.floor(columns)),images.length);
  const rows=Math.ceil(images.length/columns),cellW=width/columns,cellH=height/rows;
  const label=Math.min(48,Math.max(16,Math.floor(Math.min(cellW,cellH)*.09)));
  if(cellH<label+10||cellW<32)throw Error('格子太小，請增加輸出尺寸或減少圖片。');
  canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d')!;
  ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);ctx.imageSmoothingQuality='high';
  images.forEach((image,i)=>{const x=(i%columns)*cellW,y=Math.floor(i/columns)*cellH,pad=Math.max(2,Math.floor(Math.min(cellW,cellH)*.025));
    const scale=Math.min((cellW-pad*2)/image.width,(cellH-label-pad*2)/image.height),w=image.width*scale,h=image.height*scale;
    ctx.drawImage(image,x+(cellW-w)/2,y+label+(cellH-label-h)/2,w,h);
    ctx.fillStyle='#111';ctx.font=`600 ${Math.round(label*.6)}px sans-serif`;ctx.textBaseline='middle';ctx.fillText('Panel '+(i+1),x+pad,y+label/2);
  });
}

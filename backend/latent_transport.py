"""Bounded ZIP transport for H3 video/audio safetensors, never pickle."""
import hashlib
import json
import shutil
import uuid
import zipfile
from pathlib import Path
import httpx
from . import storage as db

MAX_BYTES = 512 * 1024 * 1024

def validate_h3(path):
    size=path.stat().st_size
    with path.open('rb') as f:
        header_size=int.from_bytes(f.read(8),'little')
        if not 2 <= header_size <= min(size-8,1024*1024): raise ValueError('不是有效的 safetensors latent。')
        header=json.loads(f.read(header_size))
    for key in ('video','audio'):
        tensor=header.get(key,{})
        offsets=tensor.get('data_offsets',[])
        if len(offsets)!=2 or not 0 <= offsets[0] < offsets[1] <= size-8-header_size or not tensor.get('shape'):
            raise ValueError('latent 缺少有效的 video/audio 張量。')
    return {key:header[key]['shape'] for key in ('video','audio')}

async def download(output, run_id):
    folder=db.DATA/'latents';folder.mkdir(exist_ok=True)
    token=uuid.uuid4().hex
    source=folder/(token+'.download')
    path=folder/(token+'.safetensors')
    try:
        count=0
        async with httpx.AsyncClient(timeout=300,follow_redirects=True) as client:
            async with client.stream('GET',output['url']) as response:
                response.raise_for_status()
                with source.open('wb') as f:
                    async for chunk in response.aiter_bytes():
                        count+=len(chunk)
                        if count>MAX_BYTES: raise ValueError('latent 檔案超過 512 MB。')
                        f.write(chunk)
        if Path(output['filename']).suffix.lower()=='.zip':
            with zipfile.ZipFile(source) as z:
                entries=[x for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith(('.safetensors','.latent'))]
                if len(entries)!=1 or entries[0].file_size>MAX_BYTES: raise ValueError('ZIP 必須包含一份 H3 latent；未取得有效 latent。')
                # Copy a selected member to our own UUID path, never extract paths.
                with z.open(entries[0]) as src,path.open('wb') as dst: shutil.copyfileobj(src,dst)
        else: source.replace(path)
        shapes=validate_h3(path)
        with path.open('rb') as f:
            digest=hashlib.file_digest(f,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(f.read()).hexdigest()
        return {'filename':path.name,'name':'h3-context.safetensors','size':path.stat().st_size,'sha256':digest,'shapes':shapes,'url':f'/api/runs/{run_id}/latent/{path.name}'}
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally: source.unlink(missing_ok=True)

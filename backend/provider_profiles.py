"""Named local connections; public responses never include credentials."""
from urllib.parse import urlparse
from . import storage as db

KINDS=('comfyui','runninghub','colab')
FIELDS=('comfy_url','runninghub_url','runninghub_key','colab_url','colab_token','workflow_id','instance_type','image_workflow_ids','audio_workflow_ids')
SECRETS=('runninghub_key','colab_token')

def profiles(settings):
    saved=settings.get('provider_profiles',[])
    defaults=[{'id':'default:'+kind,'provider':kind,'name':{'comfyui':'本機 ComfyUI','runninghub':'RunningHub','colab':'Colab'}[kind]+'（預設）',**{k:settings.get(k,{} if k.endswith('_workflow_ids') else '') for k in FIELDS}} for kind in KINDS]
    for p in defaults: p['name']=settings.get('provider_default_names',{}).get(p['id'],p['name'])
    return defaults+saved

def public(settings, catalog=False):
    return [{**{k:v for k,v in p.items() if k not in SECRETS and (not catalog or k in ('id','provider','name'))},**({} if catalog else {k+'_saved':bool(p.get(k)) for k in SECRETS})} for p in profiles(settings)]

def resolve(settings, spec):
    ident=spec.get('provider_profile_id') or 'default:'+spec['provider']
    p=next((p for p in profiles(settings) if p['id']==ident),None)
    if not p or p['provider']!=spec['provider']: raise ValueError('提供者來源不存在或類型不相符，請重新選擇模板來源。')
    return {**settings,**{k:v for k,v in p.items() if k in FIELDS}}

def merge(items, settings):
    old={p['id']:p for p in profiles(settings)}
    result=[]; ids=set(); legacy={}; names=dict(settings.get('provider_default_names',{}))
    for p in items:
        ident=p.get('id','');kind=p.get('provider');name=p.get('name','').strip()
        if not ident or ident in ids or kind not in KINDS or not name: raise ValueError('來源 ID、名稱或類型不正確。')
        ids.add(ident)
        if ident.startswith('default:') and ident!='default:'+kind: raise ValueError('預設來源類型不可變更。')
        if ident in old and old[ident]['provider']!=kind: raise ValueError('既有來源類型不可變更。')
        entry={'id':ident,'provider':kind,'name':name,**{k:p.get(k,old.get(ident,{}).get(k,settings.get(k,{} if k.endswith('_workflow_ids') else ''))) for k in FIELDS}}
        for key in SECRETS:
            entry[key]='' if p.get('clear_'+key) else p.get(key) or old.get(ident,{}).get(key,'')
        url=entry[{'comfyui':'comfy_url','runninghub':'runninghub_url','colab':'colab_url'}[kind]]
        parsed=urlparse(url)
        if url and (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password): raise ValueError('來源網址必須為 HTTP/HTTPS，且不可含帳密。')
        if kind=='runninghub' and url.rstrip('/') not in ('https://www.runninghub.ai','https://www.runninghub.cn'): raise ValueError('RunningHub 僅支援官方網址。')
        if entry['instance_type'] not in ('default','plus','ultra'): raise ValueError('不支援的運算規格。')
        for value in [entry['workflow_id'],*entry['image_workflow_ids'].values(),*entry['audio_workflow_ids'].values()]:
            if value and not str(value).isdigit(): raise ValueError('工作流 ID 必須為數字。')
        active=[r for r in db.all_records('runs') if r.get('status') in ('uploading','submitting','queued','running','downloading','reconnecting') and (r.get('spec',{}).get('provider_profile_id') or 'default:'+r.get('spec',{}).get('provider',''))==ident]
        if active and ident in old and any(entry.get(k)!=old[ident].get(k) for k in (*SECRETS,'comfy_url','colab_url','runninghub_url')): raise ValueError('此來源仍有執行中任務，請完成或取消後再變更連線與金鑰。')
        if ident.startswith('default:'):
            names[ident]=name
            keys={'comfyui':['comfy_url'],'colab':['colab_url','colab_token'],'runninghub':['runninghub_url','runninghub_key','workflow_id','instance_type','image_workflow_ids','audio_workflow_ids']}[kind]
            legacy.update({k:entry[k] for k in keys})
        else: result.append(entry)
    removed=set(old)-ids
    if any(r.get('status') in ('uploading','submitting','queued','running','downloading','reconnecting') and r.get('spec',{}).get('provider_profile_id') in removed for r in db.all_records('runs')): raise ValueError('來源仍有執行中任務，請先等待完成或取消。')
    return {**legacy,'provider_profiles':result,'provider_default_names':names}

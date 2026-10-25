"""Public SIWC loopback flow. Tokens stay server-side and are DPAPI protected on Windows."""
import asyncio
import base64
import ctypes
import hashlib
import json
import os
import secrets
import time
import uuid
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from . import storage as db

router = APIRouter(prefix='/api/chatgpt')
ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
TOKEN = ISSUER + '/api/accounts/oauth/token'
SCOPE = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
pending = {}
lock = asyncio.Lock()


def protect(data, decrypt=False):
    if os.name != 'nt':
        return data
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ValueError('無法讀寫此 Windows 使用者的 ChatGPT 憑證。請重新登入。')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.windll.kernel32.LocalFree(output.data)


def vault():
    path = db.DATA / 'chatgpt-credentials.bin'
    if path.exists():
        return json.loads(protect(path.read_bytes(), True))
    return {'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'active': None, 'accounts': {}}


def save(value):
    path = db.DATA / 'chatgpt-credentials.bin'
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(protect(json.dumps(value).encode()))
    os.replace(temp, path)


@router.get('/status')
def status():
    value = vault()
    return {'active': value['active'], 'accounts': [
        {'id': key, 'label': a.get('email', 'ChatGPT') + ' · ' + key[-8:],
         'connected': bool(a.get('refresh_token') or a.get('access_token')),
         'plan_enabled': 'chatgpt.tokens.use.direct' in a.get('scopes', [])}
        for key, a in value['accounts'].items()]}


@router.post('/login')
async def login(request: Request, account_id: str | None = None):
    # Only the local application can initiate a login transaction.
    if request.url.hostname != '127.0.0.1':
        raise ValueError('請先以 http://127.0.0.1:8766 開啟畫布再登入。')
    async with lock:
        value = vault()
        account = value['accounts'].get(account_id) if account_id else None
        if account_id and not account:
            raise ValueError('帳號不存在。')
        save(value)
        state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
        cookie = secrets.token_urlsafe(32)
        callback = str(request.base_url).rstrip('/') + '/api/chatgpt/callback'
        for key in list(pending):
            if pending[key]['expires'] < time.time():
                del pending[key]
        pending[state] = {'nonce': nonce, 'verifier': verifier, 'callback': callback,
                          'expires': time.time() + 600, 'account': account, 'cookie': cookie}
        args = {'client_id': account_id or 'dynamic_agent_client', 'ext_agent_host_id': value['host_id'],
                'response_type': 'code', 'redirect_uri': callback, 'scope': SCOPE, 'resource': RESOURCE,
                'state': state, 'nonce': nonce, 'code_challenge_method': 'S256',
                'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
        if account:
            if account.get('id_token'): args['id_token_hint'] = account['id_token']
            if account.get('email'): args['login_hint'] = account['email']
        else:
            args['agent_name_hint'] = 'H3 Canvas'
    # Browser only receives a local redirect URL; OAuth URLs containing hints are not JSON/logged.
    from fastapi.responses import JSONResponse
    response = JSONResponse({'url': '/api/chatgpt/authorize?state=' + state})
    response.set_cookie('h3_oauth', cookie, httponly=True, samesite='lax', max_age=600, path='/api/chatgpt')
    pending[state]['url'] = ISSUER + '/api/accounts/authorize?' + urlencode(args)
    return response


@router.get('/authorize')
def authorize(request: Request, state: str):
    item = pending.get(state)
    if not item or item['expires'] < time.time() or not secrets.compare_digest(request.cookies.get('h3_oauth', ''), item['cookie']):
        raise HTTPException(400, '登入已過期，請重試。')
    response = RedirectResponse(item['url'])
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


async def validate_id(raw, client_id, nonce=None):
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        response = await client.get(ISSUER + '/.well-known/jwks.json')
        response.raise_for_status()
    header = jwt.get_unverified_header(raw)
    key = next((k for k in response.json()['keys'] if k.get('kid') == header.get('kid')), None)
    if not key or header.get('alg') != 'RS256':
        raise ValueError('ID token 簽章金鑰不符。')
    claims = jwt.decode(raw, jwt.PyJWK.from_dict(key).key, algorithms=['RS256'], audience=client_id,
                        issuer=ISSUER, leeway=5, options={'require': ['iss', 'aud', 'exp', 'iat', 'sub']})
    if not claims['sub'] or (nonce is not None and claims.get('nonce') != nonce):
        raise ValueError('ID token 身分或 nonce 不符。')
    return claims


@router.get('/callback')
async def callback(request: Request):
    query = request.query_params
    item = pending.pop(query.get('state', ''), None)
    try:
        if not item or item['expires'] < time.time() or not secrets.compare_digest(request.cookies.get('h3_oauth', ''), item['cookie']):
            raise ValueError('登入驗證過期或 state 不符，請重新登入。')
        if query.get('error'):
            raise ValueError('登入未完成或未授權。可回到畫布重新登入。')
        previous = item['account']
        client_id = query.get('client_id') or (previous or {}).get('client_id')
        if not client_id or client_id == 'dynamic_agent_client' or (previous and client_id != previous['client_id']):
            raise ValueError('未取得正確的應用程式註冊 ID。')
        if not query.get('code'):
            raise ValueError('缺少授權碼。')
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(TOKEN, data={'grant_type': 'authorization_code', 'client_id': client_id,
                'code': query['code'], 'code_verifier': item['verifier'], 'redirect_uri': item['callback'], 'resource': RESOURCE})
            if response.status_code != 200:
                raise ValueError('授權碼交換失敗，請重新登入。')
            tokens = response.json()
        claims = await validate_id(tokens['id_token'], client_id, item['nonce'])
        if previous and claims['sub'] != previous['subject']:
            raise ValueError('登入帳號與原註冊帳號不同。')
        async with lock:
            value = vault()
            value['accounts'][client_id] = {**tokens, 'client_id': client_id, 'subject': claims['sub'],
                'email': claims.get('email', 'ChatGPT'), 'scopes': tokens.get('scope', '').split(),
                'expires_at': time.time() + tokens.get('expires_in', 3600)}
            value['active'] = client_id
            save(value)
        message = '登入完成，請關閉此分頁並返回畫布。' if 'chatgpt.tokens.use.direct' in tokens.get('scope', '').split() else '已登入，但未授權使用 ChatGPT 方案。請在 ChatGPT 設定中開啟此應用程式權限。'
    except Exception:
        # Never expose tokens, authorization codes, provider payloads or request URLs.
        message = '登入未完成：授權被取消、驗證失敗或連線逾時。請回到畫布重新登入。'
    result = HTMLResponse('<!doctype html><meta charset="utf-8"><title>H3 Canvas</title><p>' + message + '</p>')
    result.delete_cookie('h3_oauth', path='/api/chatgpt')
    result.headers['Cache-Control'] = 'no-store'
    result.headers['Referrer-Policy'] = 'no-referrer'
    return result


@router.post('/select')
async def select(account_id: str):
    async with lock:
        value = vault()
        if account_id not in value['accounts']:
            raise ValueError('帳號不存在。')
        value['active'] = account_id
        save(value)
    return status()


@router.post('/logout')
async def logout(account_id: str):
    async with lock:
        value = vault()
        account = value['accounts'].get(account_id)
        if not account: raise ValueError('帳號不存在。')
        revoked = False
        if account.get('refresh_token'):
            try:
                async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                    discovery = await client.get(ISSUER + '/.well-known/openid-configuration')
                    endpoint = discovery.json()['revocation_endpoint']
                    if not endpoint.startswith(ISSUER + '/'): raise ValueError('不支援的撤銷網址')
                    response = await client.post(endpoint, data={'token': account['refresh_token'], 'token_type_hint': 'refresh_token', 'client_id': account_id})
                    revoked = response.status_code == 200
            except Exception:
                pass
        value['accounts'][account_id] = {k: account[k] for k in ('client_id', 'subject', 'email')}
        if value['active'] == account_id: value['active'] = None
        save(value)
    return {'revoked': revoked, 'message': '已登出。' if revoked else '已清除本機登入；遠端撤銷未確認，請至 ChatGPT 設定取消此應用程式的授權。'}


async def access_token(account_id=None):
    async with lock:
        value = vault()
        key = account_id or value['active']
        account = value['accounts'].get(key)
        if not account or not account.get('access_token'):
            raise ValueError('請先 Continue with ChatGPT 登入。')
        if 'chatgpt.tokens.use.direct' not in account.get('scopes', []):
            raise ValueError('未授權使用 ChatGPT 方案，請在 ChatGPT 設定開啟權限。')
        if account.get('expires_at', 0) < time.time() + 90:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                response = await client.post(TOKEN, data={'grant_type': 'refresh_token', 'client_id': key,
                    'refresh_token': account.get('refresh_token', ''), 'resource': RESOURCE})
            if response.status_code != 200:
                raise ValueError('ChatGPT 登入已失效或無法更新，請重新登入。')
            tokens = response.json()
            if tokens.get('id_token'):
                claims = await validate_id(tokens['id_token'], key)
                if claims['sub'] != account['subject']: raise ValueError('更新登入時帳號不符。')
            account.update(tokens)
            if 'scope' in tokens: account['scopes'] = tokens['scope'].split()
            account['expires_at'] = time.time() + tokens.get('expires_in', 3600)
            save(value)
            if 'chatgpt.tokens.use.direct' not in account.get('scopes', []):
                raise ValueError('ChatGPT 方案授權已移除。')
        return account['access_token']


async def models():
    token = await access_token()
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.get(RESOURCE + '/models', headers={'Authorization': 'Bearer ' + token})
        if response.status_code != 200: raise ValueError('無法取得 ChatGPT 模型列表，請確認登入與方案權限。')
    return [{'id': m['slug'], 'name': m.get('display_name', m['slug'])}
            for m in response.json().get('models', []) if m.get('visibility') == 'list']


async def draft(prompt, attachments, model, account_id, on_delta=None):
    token = await access_token(account_id)
    content = [{'type': 'input_text', 'text': prompt}]
    for label, path in attachments:
        content += [{'type': 'input_text', 'text': label}, {'type': 'input_image',
            'image_url': 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode()}]
    chunks, completed, usage = [], False, None
    async with httpx.AsyncClient(timeout=240, trust_env=False) as client:
        async with client.stream('POST', RESOURCE + '/responses', headers={'Authorization': 'Bearer ' + token},
            json={'model': model, 'input': [{'role': 'user', 'content': content}], 'store': False, 'stream': True}) as response:
            if response.status_code != 200:
                raise ValueError(f'ChatGPT 請求失敗（HTTP {response.status_code}），請確認模型、授權與額度。')
            async for line in response.aiter_lines():
                if not line.startswith('data:'): continue
                data = line[5:].strip()
                if data == '[DONE]': continue
                event = json.loads(data)
                kind = event.get('type')
                if kind == 'response.output_text.delta':
                    delta=event.get('delta', '')
                    chunks.append(delta)
                    if on_delta: on_delta(delta)
                elif kind in ('response.failed', 'response.incomplete', 'error'):
                    code = (event.get('response', {}).get('error') or event.get('error') or {}).get('code', kind)
                    raise ValueError('ChatGPT 未完成：' + str(code)[:120])
                elif kind == 'response.completed':
                    completed = True
                    usage = event.get('response', {}).get('usage')
    if not completed: raise ValueError('ChatGPT 串流中斷，未收到完成事件；不會自動重送。')
    return ''.join(chunks), usage

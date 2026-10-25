import asyncio
import base64
import json
import time
from urllib.parse import urlparse, parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from backend import chatgpt_auth as auth, main, storage


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA', tmp_path)
    monkeypatch.setattr(storage, 'MEDIA', tmp_path / 'media')
    storage.MEDIA.mkdir()
    auth.pending.clear()
    with TestClient(main.app, base_url='http://127.0.0.1:8766') as client:
        yield client


def test_oauth_pkce_identity_and_protected_storage(local, monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    key['kid'] = 'test-key'
    assert '未完成' in local.get('/api/chatgpt/callback?state=wrong&code=fake').text
    attempt = local.post('/api/chatgpt/login').json()
    location = local.get(attempt['url'], follow_redirects=False).headers['location']
    args = {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
    assert args['client_id'] == 'dynamic_agent_client'
    assert args['redirect_uri'] == 'http://127.0.0.1:8766/api/chatgpt/callback'
    assert args['code_challenge_method'] == 'S256'
    assert 'chatgpt.tokens.use.direct' in args['scope']
    client_id = 'oaiapp_test'
    signed = jwt.encode({'iss':auth.ISSUER, 'aud':client_id, 'sub':'test-user', 'iat':time.time(),
        'exp':time.time()+3600, 'nonce':args['nonce'], 'email':'test@example.test'}, private, algorithm='RS256', headers={'kid':'test-key'})
    calls=[]
    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith('jwks.json'): return httpx.Response(200,json={'keys':[key]})
        body=parse_qs(request.content.decode())
        assert body['client_id']==[client_id]
        assert body['redirect_uri']==[args['redirect_uri']]
        import hashlib
        assert base64.urlsafe_b64encode(hashlib.sha256(body['code_verifier'][0].encode()).digest()).decode().rstrip('=') == args['code_challenge']
        return httpx.Response(200,json={'access_token':'secret-access','refresh_token':'secret-refresh','id_token':signed,'expires_in':3600,'scope':auth.SCOPE})
    original = httpx.AsyncClient
    monkeypatch.setattr(auth.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler)))
    assert calls == []
    url='/api/chatgpt/callback?state='+args['state']+'&code=test-code&client_id='+client_id
    assert '登入完成' in local.get(url).text
    assert 'secret-access' not in local.get('/api/chatgpt/status').text
    assert auth.vault()['accounts'][client_id]['subject']=='test-user'
    if auth.os.name=='nt': assert b'secret-access' not in (storage.DATA/'chatgpt-credentials.bin').read_bytes()
    assert '未完成' in local.get(url).text  # replay rejected, no second exchange
    async def wrong_nonce():
        with pytest.raises(ValueError): await auth.validate_id(signed,client_id,'wrong')
        with pytest.raises(jwt.InvalidAudienceError): await auth.validate_id(signed,'different',args['nonce'])
    asyncio.run(wrong_nonce())


@pytest.mark.parametrize('complete',[True,False])
def test_responses_require_terminal_success(local,monkeypatch,complete):
    async def token(*args):return 'test-token'
    monkeypatch.setattr(auth,'access_token',token)
    def handler(request):
        body=json.loads(request.content)
        assert body['stream'] is True and body['store'] is False
        assert isinstance(body['input'],list)
        events=[{'type':'response.output_text.delta','delta':'draft'}]
        if complete:events.append({'type':'response.completed','response':{'usage':{'output_tokens':1}}})
        return httpx.Response(200,content=''.join('data: '+json.dumps(e)+'\n\n' for e in events),headers={'Content-Type':'text/event-stream'})
    original=httpx.AsyncClient
    monkeypatch.setattr(auth.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler)))
    if complete:
        assert asyncio.run(auth.draft('hello',[],'available-model','account')) == ('draft',{'output_tokens':1})
    else:
        with pytest.raises(ValueError,match='串流中斷'):asyncio.run(auth.draft('hello',[],'available-model','account'))

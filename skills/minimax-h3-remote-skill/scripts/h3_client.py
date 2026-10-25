"""Authenticated MiniMax H3 Motion Context client. No automatic generation retries."""
import argparse
import contextlib
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

PROTOCOL = 'h3-motion-context-1'

class Client:
    def __init__(self):
        self.url = os.environ.get('H3_API_URL', '').rstrip('/')
        token = os.environ.get('H3_API_TOKEN', '')
        parsed = urlparse(self.url)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1')):
            raise ValueError('請設定 HTTPS H3_API_URL（本機可用 localhost HTTP）')
        if not token: raise ValueError('請設定 H3_API_TOKEN')
        self.session = requests.Session()
        self.session.headers['Authorization'] = 'Bearer ' + token

    def request(self, method, path, **kwargs):
        try:
            r = self.session.request(method, self.url + path, timeout=kwargs.pop('timeout', (15, 120)), **kwargs)
        except requests.RequestException:
            raise RuntimeError('API 連線失敗。若在提交 generate 時失敗，工作可能已接收，請先查 Colab 工作狀態，勿直接重送。') from None
        if not r.ok:
            # Do not log request headers or URLs; authorization is never a query parameter.
            if r.status_code == 401: raise RuntimeError('401：請確認 H3_API_TOKEN 與 Colab Cell 7 相同')
            raise RuntimeError(f'HTTP {r.status_code}: {r.text[:3000]}')
        return r

    def health(self):
        data = self.request('GET', '/health').json()
        if data.get('protocol') != PROTOCOL: raise RuntimeError('API protocol 不符，請啟動本套 notebook Cell 7')
        return data

    def generate(self, args, overrides):
        with contextlib.ExitStack() as stack:
            files = []
            for attr, field in [('image', 'images'), ('video', 'videos'), ('audio', 'audios')]:
                for value in getattr(args, attr):
                    p = Path(value)
                    files.append((field, (p.name, stack.enter_context(p.open('rb')), 'application/octet-stream')))
            if args.previous:
                p = Path(args.previous)
                files.append(('previous', (p.name, stack.enter_context(p.open('rb')), 'video/mp4')))
            # requests uses application/x-www-form-urlencoded without files; FastAPI Form accepts both.
            return self.request('POST', '/generate', data={'prompt': Path(args.prompt_file).read_text(encoding='utf-8-sig'),
                                 'settings': json.dumps(overrides, ensure_ascii=False)}, files=files or None,
                                 timeout=(15, args.upload_timeout)).json()['id']

    def wait(self, ident, timeout, interval):
        deadline = time.monotonic() + timeout
        previous = None
        while True:
            job = self.request('GET', '/jobs/' + ident).json()
            if job['status'] != previous:
                print(f"{ident}: {job['status']}", flush=True); previous = job['status']
            if job['status'] == 'completed': return job
            if job['status'] == 'failed': raise RuntimeError(job.get('error', '生成失敗'))
            if time.monotonic() >= deadline:
                raise TimeoutError(f'本機等待逾時；遠端工作可能仍在執行。Job {ident}；請用 status 或 resume 接續，勿重送 generate。')
            time.sleep(interval)

    def download(self, ident, job, directory, prefix):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        stem = f'{prefix}_{stamp}_seed{job["seed"]}_{ident[:8]}'
        video = directory / (stem + '.mp4')
        txt = video.with_suffix('.txt')
        for dest, endpoint in [(video, '/result/'), (txt, '/info/')]:
            if dest.exists(): raise FileExistsError(f'拒絕覆蓋: {dest}')
            partial = dest.with_suffix(dest.suffix + '.part')
            try:
                with self.request('GET', endpoint + ident, stream=True) as r, partial.open('xb') as out:
                    for chunk in r.iter_content(2**20): out.write(chunk)
                if not partial.stat().st_size: raise RuntimeError('下載內容為空')
                partial.rename(dest)
                print(str(dest.resolve()), flush=True)
            except Exception:
                if partial.exists(): partial.unlink()
                if video.exists(): print(f'MP4 已保留: {video.resolve()}；可用 resume 重新下載配對成品，無需生成。', file=sys.stderr)
                raise
        print(json.dumps(job.get('output', {}), ensure_ascii=False))
        return video, txt


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('health'); sub.add_parser('models')
    status = sub.add_parser('status'); status.add_argument('job_id')
    resume = sub.add_parser('resume'); resume.add_argument('job_id')
    gen = sub.add_parser('generate')
    gen.add_argument('--prompt-file', required=True)
    for key in ('image', 'video', 'audio'): gen.add_argument('--'+key, action='append', default=[])
    gen.add_argument('--previous', help='獨立前段影片；非 Ref2VA Video 參考')
    gen.add_argument('--settings-file', help='UTF-8 JSON 設定覆寫物件，未指定者繼承 Colab Cell 3')
    for key in ('mode', 'model', 'text-encoder', 'video-vae', 'audio-vae', 'sampler', 'scheduler', 'seed', 'ref-image-size', 'reference-video-policy', 'sol-dense-blocks'):
        gen.add_argument('--'+key)
    for key in ('duration', 'previous-start', 'previous-end', 'sol-tau', 'sol-start', 'sol-end', 'shift-video', 'shift-audio'):
        gen.add_argument('--'+key, type=float)
    for key in ('width', 'height', 'steps', 'head-chunks', 'ff-chunks', 'seq-threshold', 'context-length', 'audio-context-length', 'sol-min-tokens', 'sol-extra-tokens', 'crf'):
        gen.add_argument('--'+key, type=int)
    for key in ('motion-context', 'low-vram', 'kitchen-attention', 'sol-attention', 'shift-enabled', 'sol-verbose'):
        gen.add_argument('--'+key, action=argparse.BooleanOptionalAction, default=None)
    chain = gen.add_mutually_exclusive_group()
    chain.add_argument('--loras-file', help='有序 [{"name":"exact.safetensors","strength":1.0}]')
    chain.add_argument('--no-lora', action='store_true')
    gen.add_argument('--upload-timeout', type=float, default=1800)
    gen.add_argument('--submit-only', action='store_true')
    for command in (gen, resume):
        command.add_argument('--output-dir', required=True)
        command.add_argument('--prefix', default='H3')
        command.add_argument('--wait-timeout', type=float, default=21600)
        command.add_argument('--poll-interval', type=float, default=5)
    return p


def build_overrides(args):
    cfg = json.loads(Path(args.settings_file).read_text(encoding='utf-8-sig')) if args.settings_file else {}
    if not isinstance(cfg, dict): raise ValueError('settings-file 必須是 JSON 物件')
    excluded = {'command', 'prompt_file', 'image', 'video', 'audio', 'previous', 'settings_file', 'loras_file',
                'no_lora', 'upload_timeout', 'submit_only', 'output_dir', 'wait_timeout', 'poll_interval'}
    for key, value in vars(args).items():
        if key not in excluded and value is not None: cfg[key] = value
    if args.loras_file:
        cfg['loras'] = json.loads(Path(args.loras_file).read_text(encoding='utf-8-sig'))
    if args.no_lora: cfg['loras'] = []
    if args.previous:
        if cfg.get('motion_context') is False: raise ValueError('--previous 與停用 motion_context 衝突')
        cfg['motion_context'] = True
    elif cfg.get('motion_context') is True:
        raise ValueError('啟用 motion_context 時需要 --previous')
    return cfg


def main(argv=None):
    args = parser().parse_args(argv)
    if hasattr(args, 'prefix') and not re.fullmatch(r'[\w-]{1,80}', args.prefix):
        raise ValueError('prefix 只接受文字、數字、底線或連字號')
    if hasattr(args, 'job_id') and not re.fullmatch(r'[a-f0-9]{32}', args.job_id):
        raise ValueError('無效 job ID')
    if hasattr(args, 'poll_interval') and (args.poll_interval <= 0 or args.wait_timeout <= 0):
        raise ValueError('等待時間與輪詢間隔必須 > 0')
    client = Client()
    if args.command == 'health': print(json.dumps(client.health(), ensure_ascii=False, indent=2)); return
    client.health()
    if args.command == 'models': print(json.dumps(client.request('GET', '/models').json(), ensure_ascii=False, indent=2)); return
    if args.command == 'status': print(json.dumps(client.request('GET', '/jobs/'+args.job_id).json(), ensure_ascii=False, indent=2)); return
    if args.command == 'generate':
        ident = client.generate(args, build_overrides(args))
        print('Job ID:', ident, flush=True)
        if args.submit_only: return
    else: ident = args.job_id
    job = client.wait(ident, args.wait_timeout, args.poll_interval)
    client.download(ident, job, args.output_dir, args.prefix)

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, RuntimeError, requests.RequestException) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

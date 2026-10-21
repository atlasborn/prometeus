import json, os, re, subprocess, sys, threading, uuid, zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT / 'downloads'
DOWNLOADS.mkdir(exist_ok=True)
JOBS = {}
LOCK = threading.Lock()
POOL = ThreadPoolExecutor(max_workers=2)

def youtube_url(value):
    u = urlparse(str(value))
    if u.scheme != 'https' or u.hostname not in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com') or u.username or u.password:
        raise ValueError('Insira um link HTTPS válido do YouTube.')
    return value

def run_job(key, data):
    job = JOBS[key]
    directory = DOWNLOADS / key
    directory.mkdir()
    job.update(status='processing', progress=0)
    try:
        command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--js-runtimes', 'node', '--no-simulate', '--no-overwrites', '--newline', '--progress-template', 'download:PROGRESS:%(progress._percent_str)s', '--max-filesize', '2G', '--socket-timeout', '30', '--retries', '2', '--no-write-thumbnail', '-P', str(directory), '-o', '%(playlist_index|)s%(id)s - %(title).150B.%(ext)s']
        if data['format'] == 'mp3':
            command += ['-x', '--audio-format', 'mp3', '--audio-quality', data['quality'] + 'K']
        else:
            command += ['-f', f'bv*[height<={data["quality"]}][ext=mp4]+ba[ext=m4a]/b[height<={data["quality"]}][ext=mp4]', '--merge-output-format', 'mp4']
        if data.get('items'):
            command += ['--playlist-items', ','.join(str(x) for x in data['items'])]
        command += ['--', data['url']]
        errors = []
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as process:
            for line in process.stdout:
                if line.startswith('PROGRESS:'):
                    match = re.search(r'([\d.]+)%', line)
                    if match: job['progress'] = float(match.group(1))
                elif 'ERROR:' in line:
                    errors.append(line.strip()[:300])
            result = process.wait()
        files = [p for p in directory.iterdir() if p.suffix in ('.mp3', '.mp4')]
        if result or not files:
            raise RuntimeError('Não foi possível concluir a conversão. O vídeo pode estar indisponível ou o YouTube pode exigir autenticação.' if errors else 'Verifique se yt-dlp e FFmpeg estão instalados no servidor.')
        if len(files) > 1:
            output = directory / 'Prometeus.zip'
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
                for file in files: archive.write(file, file.name)
        else:
            output = files[0]
        job.update(status='completed', progress=100, filename=output.name, file=str(output), count=len(files))
    except Exception as error:
        job.update(status='error', error=str(error))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/health':
            import shutil
            import importlib.util
            self.send_json({'ffmpeg': bool(shutil.which('ffmpeg')), 'ytdlp': importlib.util.find_spec('yt_dlp') is not None})
        elif path == '/api/jobs':
            self.send_json([{k:v for k,v in job.items() if k != 'file'} for job in list(JOBS.values())])
        elif path.startswith('/api/download/'):
            job = JOBS.get(path.rsplit('/', 1)[-1])
            if not job or job['status'] != 'completed':
                self.send_error(404); return
            file = Path(job['file'])
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(file.stat().st_size))
            from urllib.parse import quote
            self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(file.name))
            self.end_headers()
            with file.open('rb') as source:
                import shutil
                shutil.copyfileobj(source, self.wfile)
        else:
            super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 16384: raise ValueError('Requisição muito grande.')
            data = json.loads(self.rfile.read(length))
            url = youtube_url(data.get('url', ''))
            if self.path == '/api/inspect':
                result = subprocess.run([sys.executable, '-m', 'yt_dlp', '--ignore-config', '--js-runtimes', 'node', '--flat-playlist', '--dump-single-json', '--skip-download', '--socket-timeout', '20', '--playlist-end', '500', '--', url], capture_output=True, text=True, encoding='utf-8', timeout=90)
                if result.returncode: raise ValueError('Não foi possível carregar este link. Verifique se o vídeo ou a playlist é público e tente novamente.')
                info = json.loads(result.stdout)
                entries = info.get('entries') or [info]
                self.send_json({'title': info.get('title'), 'playlist': 'entries' in info, 'items': [{'id': e.get('id'), 'title': e.get('title', 'Vídeo indisponível'), 'duration': e.get('duration'), 'channel': e.get('channel') or e.get('uploader'), 'index': i + 1, 'available': e.get('availability') not in ('private', 'premium_only', 'subscriber_only') and e.get('title') not in ('[Private video]', '[Deleted video]')} for i,e in enumerate(entries) if e], 'limited': len(entries) >= 500})
            elif self.path == '/api/jobs':
                fmt = data.get('format')
                quality = str(data.get('quality'))
                if fmt not in ('mp3', 'mp4') or quality not in ({'128', '192', '320'} if fmt == 'mp3' else {'360', '720', '1080'}): raise ValueError('Formato ou qualidade inválidos.')
                items = data.get('items')
                if not isinstance(items, list) or not items or len(items) > 500 or any(type(x) is not int or x < 1 or x > 500 for x in items): raise ValueError('Selecione pelo menos um vídeo.')
                with LOCK:
                    if sum(j['status'] in ('queued','processing') for j in JOBS.values()) >= 10: raise ValueError('Fila cheia. Aguarde uma conversão terminar.')
                    key = uuid.uuid4().hex
                    JOBS[key] = {'id': key, 'title': str(data.get('title', 'Conversão'))[:200], 'format': fmt, 'status': 'queued', 'progress': 0, 'count': len(items)}
                POOL.submit(run_job, key, {**data, 'url': url})
                self.send_json(JOBS[key], 202)
            else: self.send_error(404)
        except (ValueError, subprocess.TimeoutExpired) as error:
            self.send_json({'error': str(error)}, 400)
        except Exception:
            self.send_json({'error': 'O servidor não conseguiu processar o pedido. Verifique a instalação do yt-dlp.'}, 500)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    print(f'Prometeus disponível em http://localhost:{port}', flush=True)
    ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), port), Handler).serve_forever()

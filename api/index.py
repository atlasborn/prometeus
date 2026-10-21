"""Stateless Vercel adapter; each conversion streams its result to the browser."""
import asyncio
import base64
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server import youtube_url

app = FastAPI()
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


class Link(BaseModel):
    url: str = Field(max_length=4096)


class Conversion(Link):
    format: str
    quality: str


def validate_url(url):
    try:
        return youtube_url(url)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


def process_environment():
    return {**os.environ, 'PYTHONPATH': os.pathsep.join(str(path) for path in sys.path)}


def command():
    return [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--js-runtimes', 'node', '--socket-timeout', '20', '--retries', '1']


@app.get('/api/health')
def health():
    return {'ffmpeg': Path(FFMPEG).is_file(), 'ytdlp': True, 'mode': 'serverless', 'maxDuration': 45, 'node': bool(shutil.which('node'))}


@app.get('/api/jobs')
def jobs():
    return []


@app.post('/api/inspect')
async def inspect(data: Link):
    url = validate_url(data.url)
    process = await asyncio.create_subprocess_exec(*command(), '--flat-playlist', '--dump-single-json', '--skip-download', '--playlist-end', '500', '--', url, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=process_environment())
    try:
        output, error_output = await asyncio.wait_for(process.communicate(), timeout=45)
    except (TimeoutError, asyncio.CancelledError):
        process.kill()
        await process.wait()
        raise HTTPException(504, 'O YouTube demorou para responder. Tente novamente.')
    if process.returncode:
        logging.warning('YouTube inspection failed: %s', error_output.decode(errors='replace')[-1400:])
        raise HTTPException(422, 'O YouTube não disponibilizou este conteúdo ao servidor. Verifique o link ou tente novamente mais tarde.')
    info = json.loads(output)
    entries = info.get('entries') or [info]
    return {'title': info.get('title'), 'playlist': 'entries' in info, 'limited': len(entries) >= 500, 'items': [
        {'id': entry.get('id'), 'title': entry.get('title', 'Vídeo indisponível'), 'channel': entry.get('channel') or entry.get('uploader'), 'duration': entry.get('duration'), 'index': index + 1,
         'available': entry.get('availability') not in ('private', 'premium_only', 'subscriber_only') and entry.get('title') not in ('[Private video]', '[Deleted video]')}
        for index, entry in enumerate(entries) if entry]}


def event(kind, **values):
    return (json.dumps({'type': kind, **values}) + '\n').encode()


async def conversion_stream(data):
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='prometeus-', ignore_cleanup_errors=True) as temporary:
            directory = Path(temporary)
            # yt-dlp recognizes the executable by its canonical filename.
            binary = directory / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
            if os.name == 'nt':
                shutil.copyfile(FFMPEG, binary)
            else:
                binary.symlink_to(FFMPEG)
            args = command() + ['--no-playlist', '--newline', '--progress-template', 'download:PROGRESS:%(progress._percent_str)s', '--max-filesize', '200M', '--ffmpeg-location', str(binary), '-P', str(directory), '-o', '%(title).120B [%(id)s].%(ext)s']
            if data.format == 'mp3':
                args += ['-x', '--audio-format', 'mp3', '--audio-quality', data.quality + 'K']
            else:
                args += ['-f', f'bv*[height<={data.quality}][ext=mp4]+ba[ext=m4a]/b[height<={data.quality}][ext=mp4]', '--merge-output-format', 'mp4']
            args += ['--', data.url]
            yield event('progress', value=0)
            process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=process_environment())
            started = time.monotonic()
            while True:
                if time.monotonic() - started > 45:
                    process.kill()
                    await process.wait()
                    yield event('error', message='Este vídeo excedeu o tempo de conversão online. Tente uma qualidade menor ou use a versão local.')
                    return
                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=5)
                except TimeoutError:
                    yield event('heartbeat')
                    continue
                if not line:
                    break
                if line.startswith(b'PROGRESS:'):
                    percent = re.search(rb'([\d.]+)%', line)
                    if percent:
                        yield event('progress', value=float(percent.group(1)))
            await process.wait()
            files = list(directory.glob('*.' + data.format))
            if process.returncode or not files:
                yield event('error', message='O YouTube não permitiu concluir o download neste servidor. O vídeo pode estar restrito ou temporariamente indisponível.')
                return
            file = files[0]
            if file.stat().st_size > 256 * 1024 * 1024:
                yield event('error', message='O arquivo excede 256 MB. Escolha uma qualidade menor ou use a versão local.')
                return
            yield event('file', name=file.name, size=file.stat().st_size)
            with file.open('rb') as source:
                while chunk := source.read(65536):
                    yield event('chunk', data=base64.b64encode(chunk).decode())
                    await asyncio.sleep(0)
            yield event('done')
    except asyncio.CancelledError:
        raise
    except Exception:
        yield event('error', message='Não foi possível concluir a conversão. Tente novamente mais tarde.')
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()


@app.post('/api/convert')
async def convert(data: Conversion):
    validate_url(data.url)
    allowed = {'mp3': {'128', '192', '320'}, 'mp4': {'360', '720', '1080'}}
    if data.format not in allowed or data.quality not in allowed[data.format]:
        raise HTTPException(400, 'Formato ou qualidade inválidos.')
    return StreamingResponse(conversion_stream(data), media_type='application/x-ndjson', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

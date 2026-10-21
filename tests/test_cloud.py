import base64
import functools
import io
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import wave
import zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

try:
    from fastapi.testclient import TestClient
    from api.index import app, Conversion, conversion_stream
except ImportError:
    app = None


@unittest.skipUnless(app, 'Requires requirements.txt and requirements-dev.txt')
class CloudTests(unittest.IsolatedAsyncioTestCase):
    def test_rejects_external_download_url(self):
        with TestClient(app) as client:
            response = client.post('/api/convert', json={'url': 'https://example.com/file', 'format': 'mp3', 'quality': '320'})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(client.get('/api/health').json()['mode'], 'serverless')

    async def test_stream_delivers_complete_real_mp3(self):
        with tempfile.TemporaryDirectory() as temporary:
            with wave.open(str(Path(temporary) / 'source.wav'), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b'\x00\x00' * 8000)
            http = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(SimpleHTTPRequestHandler, directory=temporary))
            threading.Thread(target=http.serve_forever, daemon=True).start()
            try:
                events = [json.loads(packet) async for packet in conversion_stream(Conversion(url=f'http://127.0.0.1:{http.server_port}/source.wav', format='mp3', quality='128'))]
                self.assertNotIn('error', [event['type'] for event in events], [event for event in events if event['type'] == 'error'])
                metadata = next(event for event in events if event['type'] == 'file')
                content = b''.join(base64.b64decode(event['data']) for event in events if event['type'] == 'chunk')
                self.assertEqual(len(content), metadata['size'])
                self.assertGreater(len(content), 0)
                self.assertTrue(metadata['name'].endswith('.mp3'))
                self.assertEqual(events[-1]['type'], 'done')
            finally:
                http.shutdown()
                http.server_close()


@unittest.skipUnless(shutil.which('node'), 'Requires Node')
class BrowserZipTests(unittest.TestCase):
    def test_browser_zip_is_readable_with_unicode_names(self):
        script = """
const fs=require('node:fs'), vm=require('node:vm');
const context={Blob,TextEncoder,setTimeout,fetch:async()=>({json:async()=>({})})};
vm.createContext(context);
vm.runInContext(fs.readFileSync('public/cloud.js','utf8')+';this.zipFiles=zipFiles;',context);
(async()=>{const zip=await context.zipFiles([{name:'Música.mp3',blob:new Blob(['audio'])},{name:'video.mp4',blob:new Blob(['video'])}]);process.stdout.write(Buffer.from(await zip.arrayBuffer()).toString('base64'));})();
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True, timeout=10)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(result.stdout))) as archive:
            self.assertEqual(archive.read('Música.mp3'), b'audio')
            self.assertEqual(archive.read('video.mp4'), b'video')
            self.assertIsNone(archive.testzip())

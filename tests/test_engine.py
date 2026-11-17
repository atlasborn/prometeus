import functools
import importlib.util
import shutil
import tempfile
import threading
import unittest
import wave
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch
import server


@unittest.skipUnless(importlib.util.find_spec('yt_dlp') and shutil.which('ffmpeg'), 'Requires yt-dlp and FFmpeg')
class EngineTests(unittest.TestCase):
    def test_real_audio_download_and_mp3_conversion(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with wave.open(str(directory / 'source.wav'), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b'\x00\x00' * 8000)
            http = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(SimpleHTTPRequestHandler, directory=temporary))
            threading.Thread(target=http.serve_forever, daemon=True).start()
            try:
                job = {'id': 'engine-check', 'status': 'queued'}
                with patch.object(server, 'DOWNLOADS', directory / 'output'), patch.object(server, 'JOBS', {'engine-check': job}):
                    server.DOWNLOADS.mkdir()
                    server.run_job('engine-check', {'url': f'http://127.0.0.1:{http.server_port}/source.wav', 'format': 'mp3', 'quality': '128', 'items': [1]})
                self.assertEqual(job['status'], 'completed', job.get('error'))
                self.assertTrue(Path(job['file']).is_file())
                self.assertEqual(Path(job['file']).suffix, '.mp3')
                self.assertGreater(Path(job['file']).stat().st_size, 0)
            finally:
                http.shutdown()
                http.server_close()


if __name__ == '__main__':
    unittest.main()

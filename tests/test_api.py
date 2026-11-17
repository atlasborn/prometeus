import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
from types import SimpleNamespace

import server


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def request(self, path, data=None):
        request = Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        return response.status, response.read()

    def test_home_is_served(self):
        status, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'PROMETEUS', body)

    def test_download_requires_completed_job(self):
        self.assertEqual(self.request('/api/download/unknown')[0], 404)

    def test_external_url_never_starts_extractor(self):
        with patch('server.subprocess.run') as extractor:
            status, _ = self.request('/api/inspect', {'url': 'https://youtube.com.attacker.example/watch?v=test'})
            self.assertEqual(status, 400)
            extractor.assert_not_called()

    def test_playlist_exposes_only_needed_metadata(self):
        metadata = {'title': 'Playlist', 'entries': [{'id': 'one', 'title': '<Title>', 'duration': 61, 'channel': 'Channel'}, {'id': 'two', 'title': '[Private video]', 'availability': 'private'}]}
        with patch('server.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(metadata))):
            status, body = self.request('/api/inspect', {'url': 'https://www.youtube.com/playlist?list=PLtest'})
        info = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([item['index'] for item in info['items']], [1, 2])
        self.assertTrue(info['items'][0]['available'])
        self.assertFalse(info['items'][1]['available'])

    def test_empty_selection_is_rejected(self):
        status, _ = self.request('/api/jobs', {'url': 'https://youtu.be/abc', 'format': 'mp3', 'quality': '320', 'items': []})
        self.assertEqual(status, 400)

    def test_valid_job_queues_sorted_user_selection(self):
        with patch.object(server.POOL, 'submit') as submit:
            status, body = self.request('/api/jobs', {'url': 'https://www.youtube.com/playlist?list=PLtest', 'title': 'Playlist', 'format': 'mp4', 'quality': '1080', 'items': [1, 3]})
            job = json.loads(body)
            self.assertEqual(status, 202)
            self.assertEqual(job['status'], 'queued')
            self.assertEqual(submit.call_args.args[2]['items'], [1, 3])
            self.assertNotIn('file', job)
            server.JOBS.pop(job['id'])


if __name__ == '__main__':
    unittest.main()

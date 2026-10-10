"""Регрессии HTTP-клиента Jenkins без Docker и запуска QEMU."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import jenkins_api as api


class Response:
    def __init__(self, body, headers=None):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


class ClientTests(unittest.TestCase):
    def run_client(self, args, route, queue=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / 'results'
            out.mkdir()
            (root / '.env').write_text('JENKINS_ADMIN_USER=admin\nJENKINS_ADMIN_PASSWORD=test-secret\n')
            if queue:
                (out / 'queue.json').write_text(json.dumps(queue))
            class Opener:
                def open(self, request, timeout):
                    return route(request)
            with patch.object(api, 'ROOT', root), patch.object(api, 'OUT', out), \
                 patch.object(api.urllib.request, 'build_opener', return_value=Opener()), \
                 patch('sys.argv', ['jenkins_api.py', *args]), patch.object(api.time, 'sleep'), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = api.main()
            saved = json.loads((out / 'queue.json').read_text()) if (out / 'queue.json').exists() else None
            return result, saved

    def test_startup_503_then_ready(self):
        attempts = []
        def route(request):
            attempts.append(request.full_url)
            if len(attempts) == 1:
                raise urllib.error.HTTPError(request.full_url, 503, 'Starting', {}, None)
            return Response({'mode': 'NORMAL'})
        self.assertEqual(self.run_client(['status'], route)[0], 0)
        self.assertEqual(len(attempts), 2)

    def test_auth_error_not_retried(self):
        def route(request):
            raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', {}, None)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.run_client(['status'], route)
        caught.exception.close()

    def test_parameterized_and_initial_job_endpoints(self):
        for parameterized in (True, False):
            posts = []
            def route(request):
                url = request.full_url
                if request.get_method() == 'POST':
                    posts.append(url)
                    return Response(b'', {'Location': '/queue/item/42/'})
                if '/crumbIssuer/' in url:
                    return Response({'crumbRequestField': 'Jenkins-Crumb', 'crumb': 'test'})
                if url.startswith(api.JOB):
                    return Response({'property': [{'parameterDefinitions': [{'name': 'BMC_USER'}]}] if parameterized else []})
                return Response({'mode': 'NORMAL'})
            _, saved = self.run_client(['build'], route)
            self.assertEqual(posts, [api.JOB + ('/buildWithParameters' if parameterized else '/build')])
            self.assertEqual(saved['id'], 42)

    def test_expired_queue_matches_queue_id_not_latest_build(self):
        def route(request):
            url = request.full_url
            if '/queue/' in url:
                raise urllib.error.HTTPError(url, 404, 'Expired', {}, None)
            if 'builds[number' in url:
                return Response({'builds': [{'number': 9, 'queueId': 99}, {'number': 7, 'queueId': 42}]})
            if '/7/wfapi/' in url:
                return Response({'stages': []})
            if '/7/api/' in url:
                return Response({'number': 7, 'building': False, 'result': 'UNSTABLE', 'duration': 10})
            return Response({'mode': 'NORMAL'})
        _, saved = self.run_client(['watch'], route, {'url': api.BASE + '/queue/item/42/'})
        self.assertEqual(saved['number'], 7)

    def test_expired_queue_without_match_is_actionable(self):
        def route(request):
            if '/queue/' in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 404, 'Expired', {}, None)
            if 'builds[number' in request.full_url:
                return Response({'builds': []})
            return Response({'mode': 'NORMAL'})
        with self.assertRaisesRegex(RuntimeError, '--number'):
            self.run_client(['watch'], route, {'url': api.BASE + '/queue/item/42/'})


if __name__ == '__main__':
    unittest.main()

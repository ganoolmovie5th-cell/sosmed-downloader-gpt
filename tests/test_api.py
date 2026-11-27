import json
import subprocess
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
from api import resolve

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1',0), resolve.handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def setUp(self): resolve._recent.clear()
    def request(self, data, headers=None, method='POST'):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        body = data if isinstance(data,str) else json.dumps(data)
        conn.request(method,'/api/resolve',body,{'Content-Type':'application/json',**(headers or {})})
        response=conn.getresponse(); result=response.status,json.loads(response.read());conn.close();return result
    @patch('api.resolve.subprocess.run')
    def test_invalid_input_never_starts_worker(self, run):
        for value in [[],{}, {'url':'https://127.0.0.1/a'},'{']:
            self.assertEqual(self.request(value)[0],400)
        run.assert_not_called()
    @patch('api.resolve.subprocess.run')
    def test_origin_and_content_type(self, run):
        self.assertEqual(self.request({}, {'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request({}, {'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('a'*5000)[0],413)
        self.assertEqual(self.request({}, method='GET')[0],405)
        run.assert_not_called()
    @patch('api.resolve.subprocess.run')
    def test_success_and_normalized_url(self,run):
        run.return_value = SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'items':[]}))
        code,data=self.request({'url':'https://twitter.com/user/status/123?tracking=1'})
        self.assertEqual(code,200);self.assertTrue(data['ok'])
        self.assertEqual(run.call_args.args[0][-1],'https://x.com/user/status/123')
        self.assertEqual(run.call_args.kwargs['timeout'],23)
    @patch('api.resolve.subprocess.run')
    def test_timeout_and_provider_error_do_not_leak(self,run):
        run.side_effect=subprocess.TimeoutExpired('private-command',23)
        code,data=self.request({'url':'https://x.com/u/status/123'})
        self.assertEqual(code,504);self.assertNotIn('private-command',str(data))
        run.side_effect=RuntimeError('secret-token')
        code,data=self.request({'url':'https://x.com/u/status/123'})
        self.assertEqual(code,502);self.assertNotIn('secret-token',str(data))
    def test_budget(self):
        from time import monotonic
        resolve._recent.extend([monotonic()]*12)
        self.assertEqual(self.request({'url':'https://x.com/u/status/123'})[0],429)

if __name__ == '__main__':unittest.main()

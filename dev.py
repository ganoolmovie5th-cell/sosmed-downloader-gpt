"""Local server uses the same API handler as Vercel. Run: python dev.py"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from api.resolve import handler

class LocalHandler(handler, SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent / 'public'), **kwargs)
    def do_GET(self):
        if urlsplit(self.path).path.startswith('/api/'):
            return handler.do_GET(self)
        return SimpleHTTPRequestHandler.do_GET(self)
    def do_POST(self):
        if self.path != '/api/resolve':
            return self.reply(404, {'ok': False, 'error': 'Endpoint tidak ditemukan.'})
        return handler.do_POST(self)

if __name__ == '__main__':
    print('Sosmed Downloader: http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), LocalHandler).serve_forever()

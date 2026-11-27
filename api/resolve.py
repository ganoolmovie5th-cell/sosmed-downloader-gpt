import json
import os
import subprocess
import sys
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from server.core import ResolveError, validate_post

ROOT = Path(__file__).resolve().parents[1]
_slots = threading.BoundedSemaphore(2)
_lock = threading.Lock()
_recent = deque()

class handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Robots-Tag', 'noindex, nofollow')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(405, {'ok': False, 'error': 'Gunakan formulir untuk memproses postingan.'})

    def do_POST(self):
        acquired = False
        try:
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                raise ResolveError('Permintaan harus berasal dari website ini.', 403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ResolveError('Format permintaan harus JSON.', 415)
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                raise ResolveError('Ukuran permintaan tidak valid.')
            if not 0 < size <= 4096:
                raise ResolveError('Permintaan terlalu besar atau kosong.', 413)
            try:
                payload = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeDecodeError):
                raise ResolveError('JSON tidak valid.')
            if not isinstance(payload, dict):
                raise ResolveError('Permintaan harus berupa objek JSON.')
            _, url = validate_post(payload.get('url'))
            # shortcut: warm-instance budget only; add Vercel Firewall rules for public traffic at scale.
            with _lock:
                now = monotonic()
                while _recent and now - _recent[0] > 60:
                    _recent.popleft()
                if len(_recent) >= 12:
                    raise ResolveError('Terlalu banyak permintaan. Coba lagi dalam satu menit.', 429)
                _recent.append(now)
            acquired = _slots.acquire(blocking=False)
            if not acquired:
                raise ResolveError('Server sedang memproses permintaan lain. Coba sebentar lagi.', 429)
            # Vercel adds vendored dependencies to sys.path only in the parent process.
            env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT), *sys.path]),
                   'PYTHONDONTWRITEBYTECODE': '1'}
            completed = subprocess.run([sys.executable, '-m', 'server.worker', url],
                                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=23)
            if completed.returncode or len(completed.stdout) > 300000:
                raise ResolveError('Pemrosesan media gagal. Coba lagi nanti.', 502)
            data = json.loads(completed.stdout)
            self.reply(200 if data.get('ok') else data.get('status', 422), data)
        except ResolveError as exc:
            self.reply(exc.status, {'ok': False, 'error': str(exc)})
        except subprocess.TimeoutExpired:
            self.reply(504, {'ok': False, 'error': 'Sumber belum merespons dalam 23 detik. Coba lagi atau gunakan postingan lain.'})
        except Exception:
            self.reply(502, {'ok': False, 'error': 'Layanan sementara gagal. Silakan coba lagi.'})
        finally:
            if acquired:
                _slots.release()

    def log_message(self, *_):
        pass

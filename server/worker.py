"""One isolated extraction process per request; never downloads media files."""
import ipaddress
import json
import logging
import re
import socket
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlencode, urlunsplit
import requests
from server.core import ResolveError, allowed_url, NETWORK_DOMAINS, validate_post, media_item, finish

# All requests, including redirects issued by extractors, stay on known services.
_original_send = requests.Session.send

def guarded_send(self, request, **kwargs):
    if not allowed_url(request.url, NETWORK_DOMAINS):
        raise ResolveError('Sumber mengarahkan permintaan ke alamat yang tidak diizinkan.', 422)
    host = urlsplit(request.url).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ResolveError('Alamat jaringan sumber tidak diizinkan.', 422)
    self.max_redirects = 4
    kwargs['timeout'] = 6
    kwargs['stream'] = True
    response = _original_send(self, request, **kwargs)
    chunks, size = [], 0
    try:
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 6 * 1024 * 1024:
                raise ResolveError('Data postingan terlalu besar untuk diproses.', 422)
            chunks.append(chunk)
        response._content = b''.join(chunks)
        response._content_consumed = True
        return response
    finally:
        response.close()

class JSONScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reading, self.parts, self.documents = False, [], []
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.reading = dict(attrs).get('type') == 'application/json'
            self.parts = []
    def handle_data(self, data):
        if self.reading:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.reading:
            try:
                self.documents.append(json.loads(''.join(self.parts)))
            except (ValueError, RecursionError):
                pass
            self.reading = False

def structured_media(documents, code):
    stack, visited = list(documents), 0
    while stack and visited < 100000:
        node = stack.pop()
        visited += 1
        if isinstance(node, dict):
            if node.get('code', node.get('shortcode')) == code:
                entries = node.get('carousel_media') or [e.get('node', {}) for e in node.get('edge_sidecar_to_children', {}).get('edges', [])] or [node]
                items = []
                for entry in entries:
                    videos = entry.get('video_versions') or []
                    photos = (entry.get('image_versions2') or {}).get('candidates') or []
                    if videos or entry.get('video_url'):
                        best = max(videos, key=lambda x: (x.get('width') or 0)*(x.get('height') or 0)) if videos else {'url': entry['video_url']}
                        items.append(media_item(best.get('url'), 'video', best.get('width') or entry.get('original_width'), best.get('height') or entry.get('original_height')))
                    elif photos or entry.get('display_url'):
                        best = max(photos, key=lambda x: (x.get('width') or 0)*(x.get('height') or 0)) if photos else {'url': entry['display_url']}
                        items.append(media_item(best.get('url'), 'image', best.get('width') or entry.get('original_width'), best.get('height') or entry.get('original_height')))
                if any(items):
                    caption = node.get('caption') or {}
                    return items, caption.get('text', '') if isinstance(caption, dict) else ''
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return [], ''

def instagram(url):
    session = requests.Session()
    response = session.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    code = urlsplit(url).path.rstrip('/').split('/')[-1]
    match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', response.text)
    if not match:
        raise ResolveError('Instagram belum menyediakan akses publik untuk postingan ini.', 422)
    token = match[1]
    media_id = 0
    for char in code:
        media_id = media_id * 64 + 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'.index(char)
    # shortcut: Instagram public-web query ID can change; update against upstream when extraction fails.
    response = session.post('https://www.instagram.com/api/graphql', data={
        'lsd': token, 'doc_id': '27130156389949648',
        'variables': json.dumps({'media_id': str(media_id)}),
        'fb_api_caller_class': 'RelayModern',
        'fb_api_req_friendly_name': 'PolarisLoggedOutDesktopWWWPostRootContentQuery',
        'server_timestamps': 'true',
    }, headers={'X-FB-LSD': token, 'Referer': url,
                'X-FB-Friendly-Name': 'PolarisLoggedOutDesktopWWWPostRootContentQuery'})
    response.raise_for_status()
    data = response.json().get('data') or {}
    media = data.get('xig_polaris_media') or {}
    public = media.get('if_not_gated_logged_out')
    if not public:
        raise ResolveError('Instagram membatasi postingan ini untuk pengunjung tanpa login.', 422)
    return structured_media([public], code)

def public_page(url):
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    parser = JSONScripts()
    parser.feed(response.text)
    return structured_media(parser.documents, urlsplit(url).path.rstrip('/').split('/')[-1])

def x_media(data):
    items = []
    details = data.get('mediaDetails') or data.get('photos') or []
    for entry in details:
        if entry.get('type', 'photo') == 'photo':
            url = entry.get('media_url_https') or entry.get('url')
            if allowed_url(url, ('twimg.com',)):
                parts = urlsplit(url)
                ext = parts.path.rsplit('.', 1)[-1]
                url = urlunsplit((parts.scheme, parts.netloc, parts.path.rsplit('.', 1)[0], urlencode({'format': ext, 'name': 'orig'}), ''))
                size = entry.get('original_info') or entry
                items.append(media_item(url, 'image', size.get('width'), size.get('height')))
        else:
            variants = (entry.get('video_info') or {}).get('variants', [])
            videos = [v for v in variants if v.get('content_type') == 'video/mp4' and allowed_url(v.get('url'))]
            if videos:
                best = max(videos, key=lambda v: v.get('bitrate', 0))
                items.append(media_item(best['url'], 'video'))
    # Older syndication responses expose a single video outside mediaDetails.
    if not items and data.get('video'):
        variants = [v for v in data['video'].get('variants', []) if v.get('type') == 'video/mp4' and allowed_url(v.get('src'))]
        if variants:
            def resolution(v):
                import re
                m = re.search(r'/(\d+)x(\d+)/', v['src'])
                return int(m[1])*int(m[2]) if m else 0
            items.append(media_item(max(variants, key=resolution)['src'], 'video'))
    return items

def gallery(url):
    from gallery_dl import config, extractor
    from gallery_dl.extractor.message import Message
    config.clear()
    for key, val in {'retries': 0, 'timeout': 6, 'sleep-request': 0, 'sleep-429': 0,
                     'fallback-retries': 0, 'audio': False, 'comments': False,
                     'cookies': None, 'cache': False}.items():
        config.set(('extractor',), key, val)
    config.set(('cache',), 'file', ':memory:')
    ext = extractor.find(url)
    if ext is None:
        raise ResolveError('Format postingan ini belum didukung. Coba tautan foto, video, atau reel langsung.', 422)
    items, title = [], ''
    for message in ext:
        if message[0] == Message.Url:
            _, media_url, data = message
            extension = data.get('extension', '').lower()
            kind = 'video' if extension in ('mp4', 'webm', 'mov') else 'audio' if extension in ('m4a', 'mp3', 'aac') else 'image' if extension in ('jpg', 'jpeg', 'png', 'webp', 'gif', 'avif') else None
            item = media_item(media_url, kind, data.get('width'), data.get('height'))
            if item:
                items.append(item)
                title = data.get('title') or data.get('description') or title
            if len(items) >= 21:
                break
    return items, title

def resolve(url):
    platform, url = validate_post(url)
    warnings = []
    if platform == 'x':
        response = requests.get('https://cdn.syndication.twimg.com/tweet-result',
                                params={'id': url.rsplit('/', 1)[-1], 'token': '1'},
                                headers={'User-Agent': 'Googlebot'})
        response.raise_for_status()
        data = response.json()
        items, title = x_media(data), data.get('text', '')
        warnings.append('X menyediakan data embed publik; media tertentu mungkin tidak tersedia.')
    elif platform == 'instagram':
        items, title = instagram(url)
    elif platform == 'threads':
        items, title = public_page(url)
    else:
        items, title = gallery(url)
    if any(i and i['type'] == 'audio' for i in items):
        warnings.append('Sumber memisahkan video dan audio. Unduh keduanya; video dapat tidak memiliki suara. Aplikasi ini tidak menggabungkan berkas.')
        for i in items:
            if i and i['type'] == 'video':
                i['label'] = 'Video · audio terpisah'
    return finish(platform, url, items, title, warnings)

if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    requests.Session.send = guarded_send
    try:
        result = resolve(sys.argv[1])
        print(json.dumps({'ok': True, **result}))
    except ResolveError as exc:
        print(json.dumps({'ok': False, 'error': str(exc), 'status': exc.status}))
    except Exception:
        print(json.dumps({'ok': False, 'status': 422, 'error': 'Platform menolak akses publik atau format media berubah. Coba postingan lain; tidak perlu memasukkan akun atau cookie.'}))

"""Strict post URLs and safe, bounded media results shared by API and worker."""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode

class ResolveError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

HOSTS = {
    'instagram.com': 'instagram', 'www.instagram.com': 'instagram',
    'tiktok.com': 'tiktok', 'www.tiktok.com': 'tiktok',
    'facebook.com': 'facebook', 'www.facebook.com': 'facebook', 'm.facebook.com': 'facebook',
    'x.com': 'x', 'www.x.com': 'x', 'twitter.com': 'x', 'www.twitter.com': 'x',
    'threads.com': 'threads', 'www.threads.com': 'threads',
    'threads.net': 'threads', 'www.threads.net': 'threads',
}
MEDIA_DOMAINS = ('fbcdn.net', 'cdninstagram.com', 'twimg.com', 'tiktokcdn.com',
                 'tiktokcdn-us.com', 'tiktokcdn-eu.com', 'tiktokv.com',
                 'tiktokv.us', 'tiktok.com', 'byteoversea.com', 'ibytedtos.com',
                 'muscdn.com', 'byteimg.com')
NETWORK_DOMAINS = MEDIA_DOMAINS + ('instagram.com', 'facebook.com', 'threads.com',
                                    'threads.net', 'x.com', 'twitter.com')

def allowed_url(value, domains=MEDIA_DOMAINS):
    if not isinstance(value, str) or len(value) > 12000 or re.search(r'[\x00-\x20\\]', value):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == 'https' and not u.username and not u.password
                and u.port in (None, 443) and bool(u.hostname)
                and any(u.hostname == d or u.hostname.endswith('.' + d) for d in domains))
    except ValueError:
        return False

def validate_post(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ResolveError('Masukkan URL postingan publik yang valid.')
    value = value.strip()
    if re.search(r'[\x00-\x20\\]', value):
        raise ResolveError('URL mengandung karakter yang tidak valid.')
    try:
        u = urlsplit(value)
        platform = HOSTS.get(u.hostname)
        valid = u.scheme == 'https' and not u.username and not u.password and u.port in (None, 443)
    except ValueError:
        valid, platform = False, None
    if not valid or not platform:
        raise ResolveError('Gunakan URL https dari Instagram, TikTok, Facebook, X, atau Threads.')
    p, query = u.path.rstrip('/'), ''
    if platform == 'instagram':
        match = re.fullmatch(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', p)
        host = 'www.instagram.com'
    elif platform == 'tiktok':
        match = re.fullmatch(r'/@[\w.-]+/(?:video|photo)/(\d+)', p, re.ASCII)
        host = 'www.tiktok.com'
    elif platform == 'x':
        match = re.fullmatch(r'/[A-Za-z0-9_]+/status/(\d+)(?:/(?:photo|video)/\d+)?', p)
        host = 'x.com'
        if match:
            p = p.split('/status/')[0] + '/status/' + match[1]
    elif platform == 'threads':
        match = re.fullmatch(r'/@[A-Za-z0-9_.]+/post/([A-Za-z0-9_-]+)(?:/[A-Za-z0-9_-]+)?', p)
        host = 'www.threads.com'
        if match:
            p = '/'.join(p.split('/')[:4])
    else:
        host = 'www.facebook.com'
        match = re.fullmatch(r'/(?:reel/(\d+)|[A-Za-z0-9_.]+/videos/(\d+)|[A-Za-z0-9_.]+/posts/(?:\d+|pfbid[A-Za-z0-9]+))', p)
        if p in ('/watch', '/video.php', '/photo.php', '/photo'):
            key = 'fbid' if p.startswith('/photo') else 'v'
            value = parse_qs(u.query).get(key, [''])[0]
            match = re.fullmatch(r'\d+', value)
            query = urlencode({key: value})
    if not match:
        raise ResolveError('Gunakan URL postingan lengkap, bukan profil, story, atau tautan pendek. Buka postingannya lalu salin URL dari browser.')
    return platform, urlunsplit(('https', host, p + ('/' if p == '/watch' else ''), query, ''))

def media_item(url, kind, width=0, height=0, label=None):
    if not allowed_url(url) or kind not in ('image', 'video', 'audio'):
        return None
    def dimension(x):
        return int(x) if isinstance(x, (int, float)) and 0 < x < 100000 else 0
    return {'url': url, 'type': kind, 'width': dimension(width), 'height': dimension(height),
            'label': label or ('Foto' if kind == 'image' else 'Video' if kind == 'video' else 'Audio terpisah')}

def finish(platform, url, items, title='', warnings=None):
    unique = {i['url']: i for i in items if i}
    if not unique:
        raise ResolveError('Media belum dapat diambil. Postingan mungkin dibatasi, dihapus, tanpa media, atau membutuhkan login. Coba postingan publik lain.', 422)
    warnings = list(warnings or [])
    if len(unique) > 20:
        warnings.append('Hanya 20 media pertama ditampilkan untuk membatasi waktu proses.')
    return {'platform': platform, 'source': url, 'title': str(title or 'Media postingan')[:400],
            'items': list(unique.values())[:20], 'warnings': warnings,
            'quality': 'Kualitas tertinggi yang tersedia dari sumber; tanpa kompresi ulang.'}

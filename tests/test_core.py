import json
import unittest
from unittest.mock import patch
from server.core import validate_post, allowed_url, media_item, finish, ResolveError
from server.worker import structured_media, x_media, guarded_send

class URLTests(unittest.TestCase):
    def test_supported_posts_and_tracking_removed(self):
        cases = {
            'https://www.instagram.com/p/DgM8G2gH3gz/?utm_source=foo': ('instagram', 'https://www.instagram.com/p/DgM8G2gH3gz'),
            'https://www.tiktok.com/@a/video/123': ('tiktok', 'https://www.tiktok.com/@a/video/123'),
            'https://twitter.com/a/status/123/photo/1?s=20': ('x', 'https://x.com/a/status/123'),
            'https://threads.net/@user/post/ABC/slug': ('threads', 'https://www.threads.com/@user/post/ABC'),
            'https://m.facebook.com/watch/?v=123&tracking=x': ('facebook', 'https://www.facebook.com/watch/?v=123'),
            'https://www.facebook.com/photo.php?fbid=456': ('facebook', 'https://www.facebook.com/photo.php?fbid=456'),
        }
        for url, expected in cases.items():
            with self.subTest(url=url): self.assertEqual(validate_post(url), expected)
    def test_rejects_profiles_shortlinks_ssrf_and_ambiguous_urls(self):
        for url in [None, [], 'http://x.com/a/status/1', 'https://127.0.0.1/a', 'https://x.com.evil.test/a/status/1',
                    'https://x.com@evil.test/a/status/1', 'https://user@x.com/a/status/1',
                    'https://x.com:444/a/status/1', 'https://x.com/a', 'https://www.instagram.com/user/',
                    'https://vm.tiktok.com/abc', 'https://x.com/a/status/1/../../foo', 'https://x.com/a/status/1\nfoo',
                    'https://www.facebook.com/watch/?v=http://127.0.0.1', 'https://x.com:bad/a/status/1',
                    'https://x.com/a\\status/1', 'https://www.facebook.com/flx/warn/?u=https://evil.test']:
            with self.subTest(url=url), self.assertRaises(ResolveError): validate_post(url)
    def test_cdn_allowlist(self):
        self.assertTrue(allowed_url('https://video.xx.fbcdn.net/a.mp4?token=123'))
        for url in ['http://pbs.twimg.com/a.jpg','https://pbs.twimg.com.evil.test/a','https://evil.test/a',
                    'javascript:alert(1)', 'https://pbs.twimg.com:81/a','https://user@pbs.twimg.com/a']:
            self.assertFalse(allowed_url(url), url)
    def test_private_dns_denied_before_network(self):
        import requests
        request = requests.Request('GET', 'https://pbs.twimg.com/a').prepare()
        with patch('server.worker.socket.getaddrinfo', return_value=[(2,1,6,'',('127.0.0.1',443))]), self.assertRaises(ResolveError):
            guarded_send(requests.Session(), request)

class MediaTests(unittest.TestCase):
    def test_structured_media_ignores_other_posts_and_selects_largest(self):
        source = [{'code':'other','display_url':'https://s.cdninstagram.com/wrong.jpg'},
                  {'data': {'post': {'code':'wanted', 'carousel_media':[
                      {'image_versions2': {'candidates': [
                          {'url':'https://s.cdninstagram.com/small.jpg','width':100,'height':100},
                          {'url':'https://s.cdninstagram.com/full.jpg','width':1080,'height':1350}]}},
                      {'video_versions':[{'url':'https://s.cdninstagram.com/v.mp4','width':1080,'height':1920}]}]}}}]
        media, _ = structured_media(source, 'wanted')
        self.assertEqual([m['type'] for m in media], ['image','video'])
        self.assertTrue(media[0]['url'].endswith('full.jpg'))
        self.assertEqual(structured_media(source, 'absent'), ([],''))
    def test_x_uses_original_photo_and_highest_bitrate(self):
        items = x_media({'mediaDetails':[
            {'type':'photo','media_url_https':'https://pbs.twimg.com/media/photo.jpg'},
            {'type':'video','video_info':{'variants':[
                {'content_type':'video/mp4','url':'https://video.twimg.com/low.mp4','bitrate':100},
                {'content_type':'video/mp4','url':'https://video.twimg.com/high.mp4','bitrate':200},
                {'content_type':'application/x-mpegURL','url':'https://video.twimg.com/hls.m3u8','bitrate':500}]}}]})
        self.assertIn('name=orig',items[0]['url']); self.assertIn('high.mp4', items[1]['url'])
    def test_dedup_limit_and_no_preview_as_photo(self):
        item = media_item('https://pbs.twimg.com/a.jpg','image')
        self.assertEqual(len(finish('x','source',[item,item])['items']),1)
        result = finish('x','source',[media_item(f'https://pbs.twimg.com/{i}.jpg','image') for i in range(22)])
        self.assertEqual(len(result['items']),20);self.assertTrue(result['warnings'])
        with self.assertRaises(ResolveError): finish('x','source',[None])
        self.assertIsNone(media_item('https://evil.test/a.jpg','image'))


class InstagramTests(unittest.TestCase):
    def test_uses_only_logged_out_public_payload(self):
        from server.worker import instagram
        from unittest.mock import MagicMock
        session=MagicMock()
        session.get.return_value.text='<script>["LSD",[],{"token":"public-token"}]</script>'
        session.post.return_value.json.return_value={'data':{'xig_polaris_media':{'code':'ABC','if_not_gated_logged_out':None}}}
        with patch('server.worker.requests.Session', return_value=session), self.assertRaises(ResolveError):
            instagram('https://www.instagram.com/p/ABC')
        self.assertIn('public-token',session.post.call_args.kwargs['data'].values())
    def test_dimensionless_candidates_preserve_original_first(self):
        items,_=structured_media([{'code':'ABC','original_width':3075,'original_height':4096,
            'image_versions2':{'candidates':[{'url':'https://s.cdninstagram.com/original.jpg'},{'url':'https://s.cdninstagram.com/small.jpg'}]}}],'ABC')
        self.assertTrue(items[0]['url'].endswith('original.jpg'))
        self.assertEqual((items[0]['width'],items[0]['height']),(3075,4096))

if __name__ == '__main__': unittest.main()

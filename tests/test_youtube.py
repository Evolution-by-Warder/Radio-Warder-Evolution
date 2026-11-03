import io
import json
import ssl
import unittest
from urllib.parse import parse_qs, urlsplit
from WarderRadio.youtube import Transport, song_query, search_results, find_video, allowed_url


def page(*items):
    document={'contents':{'twoColumnSearchResultsRenderer':{'primaryContents':{
        'sectionListRenderer':{'contents':[{'itemSectionRenderer':{'contents':list(items)}}]}}}}}
    return '<script>var ytInitialData = '+json.dumps(document)+';</script>'


def video(identifier='abcdefghijk', title='Singer - Song'):
    return {'videoRenderer':{'videoId':identifier,'title':{'runs':[{'text':title}]}}}


class YouTubeTests(unittest.TestCase):
    def test_query_cleans_file_tags_but_keeps_remix_year_and_artist_identity(self):
        self.assertEqual(song_query('JASON_DERULO','13. WANT_TO_WANT_ME_WESTFUNK_REMIX'),
                         'JASON DERULO WANT TO WANT ME WESTFUNK REMIX')
        self.assertEqual(song_query('U2','1984'),'U2 1984')
        self.assertEqual(song_query('21 Pilots','99 Luftballons'),'21 Pilots 99 Luftballons')
        self.assertEqual(song_query('', 'Announcement'),'')
        self.assertEqual(song_query('Singer',''),'')

    def test_search_parses_json_without_execution_skips_ads_duplicates_and_invalid_ids(self):
        html=page({'adSlotRenderer':{'content':video('advert12345','Advertisement')}},
                  video(),video(),video('bad'),video('lmnopqrstuv','Second Song'))
        self.assertEqual(search_results(html),[{'id':'abcdefghijk','title':'Singer - Song'},
                                               {'id':'lmnopqrstuv','title':'Second Song'}])
        for value in ('<html>Consent required</html>', 'var ytInitialData = alert(1);',
                      'var ytInitialData = null;', 'var ytInitialData = {};'):
            self.assertEqual(search_results(value),[])

    def test_worker_uses_first_organic_result_and_validates_the_extracted_media_url(self):
        calls=[]
        class Network:
            def page(self,url,*a,**k):calls.append(url);return page(video())
        class Resolver:
            def extract(self,identifier):
                calls.append(identifier)
                self._download_webpage('https://www.youtube.com/iframe_api')
                return 'https://rr1.googlevideo.com/videoplayback?token=test'
        self.assertEqual(find_video('Singer','Song',Network(),Resolver)['id'],'abcdefghijk')
        self.assertEqual(parse_qs(urlsplit(calls[0]).query)['search_query'],['Singer Song'])
        self.assertIn('abcdefghijk',calls)
        class BadResolver:
            def extract(self,identifier):return 'file:///etc/passwd'
        with self.assertRaises(ValueError):find_video('Singer','Song',Network(),BadResolver)
        with self.assertRaises(ValueError):find_video('','',Network(),Resolver)
        class Empty:
            def page(self,*a,**k):return '<html>No results</html>'
        with self.assertRaises(LookupError):find_video('Singer','Song',Empty(),Resolver)

    def test_network_is_verified_bounded_and_does_not_follow_untrusted_final_origins(self):
        class Response(io.BytesIO):
            url='https://www.youtube.com/results'
        requests=[]
        def opener(request,timeout):
            requests.append((request,timeout));return Response(b'hello')
        network=Transport(opener,clock=lambda:0)
        self.assertEqual(network.page('https://www.youtube.com/results'),'hello')
        self.assertEqual(requests[0][1],5)
        network.deadline=-1
        with self.assertRaises(TimeoutError):network.page('https://www.youtube.com/results')
        too_big=Transport(lambda *a,**k:Response(b'A'*(3*1024*1024+1)))
        with self.assertRaises(ValueError):too_big.page('https://www.youtube.com/results')
        for url in ('http://www.youtube.com/results','file:///etc/passwd',
                    'https://www.youtube.com.attacker.example/', 'https://user@www.youtube.com/',
                    'https://www.youtube.com:8000/'):
            with self.assertRaises(ValueError):allowed_url(url)
        with self.assertRaises(ValueError):allowed_url('https://www.youtube.com/watch?v=abcdefghijk',media=True)

    def test_bundled_resolver_selects_combined_format_and_keeps_image_config_and_tls_unchanged(self):
        before=ssl._create_default_https_context
        from WarderRadio.youtube_engine.extractor import YouTubeVideoUrl
        from WarderRadio.youtube_engine.jsinterp import JSInterpreter
        self.assertIs(ssl._create_default_https_context,before)
        resolver=YouTubeVideoUrl()
        response={'videoDetails':{'videoId':'abcdefghijk'},'playabilityStatus':{'status':'OK'},
                  'streamingData':{'formats':[{'itag':18,'mimeType':'video/mp4',
                      'url':'https://rr1.googlevideo.com/video'}]}}
        resolver._extract_player_response=lambda *a,**k:(response,None)
        self.assertEqual(resolver.extract('abcdefghijk'),'https://rr1.googlevideo.com/video')
        js = JSInterpreter('function f(a){return a.split("").reverse().join("");}')
        self.assertEqual(js.extract_function_from_code(*js.extract_function_code('f'))(['abc']), 'cba')

    def test_retired_client_falls_back_and_hls_master_is_left_to_native_demuxer(self):
        from WarderRadio.youtube_engine.extractor import YouTubeVideoUrl
        resolver=YouTubeVideoUrl(); calls=[]
        def response(video_id, auth, client, lang, *args):
            calls.append(client)
            if client==3:
                return {'playabilityStatus':{'status':'ERROR','reason':'Retired client'}},None
            return {'videoDetails':{'videoId':video_id},'playabilityStatus':{'status':'OK'},
                    'streamingData':{'hlsManifestUrl':'https://manifest.googlevideo.com/master.m3u8'}},None
        resolver._extract_player_response=response
        self.assertEqual(resolver.extract('abcdefghijk'),'https://manifest.googlevideo.com/master.m3u8')
        self.assertEqual(calls,[3,101])

    def test_sign_in_demand_is_reported_without_embedded_retries_or_navigation(self):
        from WarderRadio.youtube_engine.extractor import YouTubeVideoUrl
        resolver=YouTubeVideoUrl(); calls=[]
        def response(video_id, auth, client, lang, *args):
            calls.append(client)
            return {'playabilityStatus':{'status':'LOGIN_REQUIRED','reason':'Sign in to confirm you are not a bot'}},None
        resolver._extract_player_response=response
        with self.assertRaisesRegex(RuntimeError,'not a bot'):
            resolver.extract('abcdefghijk')
        self.assertEqual(calls,[3,101])

import pycurl
import threading
import time
from StringIO import StringIO
import random
from urlparse import urljoin
import re


CURL_OPT_MAX_NUM_REDIRECT = 12
CURL_OPT_USER_AGENT_LIST = [ 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2224.3 Safari/537.36', # Windows XP Chrome
                             'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36', # Windows 7 Chrome
                             'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36', # OSX Chrome
                             'Mozilla/4.0 (Compatible; MSIE 8.0; Windows NT 5.2; Trident/6.0)', # Windows Server 2003 IE 10
                             'Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; SLCC1; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET CLR 1.1.4322)' # Windows XP IE 8
                             ]
LEN_USER_AGENT_LIST = len(CURL_OPT_USER_AGENT_LIST)
KEY_CURL_HEADER_RESPONSE = '_response'
KEY_CURL_HEADER_LOCATION = 'location'
KEY_META_REDIRECT_PATH = 'redirect_url'
KEY_META_IS_REDIRECT_COMPLETE = 'is_redirect_complete'
KEY_META_SUCCESSFULLY_DOWNLOAD = 'successfully_download'
KEY_META_FAILED_DOWNLOAD_REASON = 'failed_download_reason'
KEY_META_CONTENT_LENGTH = 'final_url_content_length'
KEY_META_HTTP_CODE = 'http_code'

RE_JAVASCRIPT = re.compile('<\s*script\s*>(.*?)</\s*script\s*>')
RE_META_TAG = re.compile('<\s*meta\s+([^>]+?)/\s*>')
RE_BEFORE_BODY = re.compile('^(.*?)<\s*body')
RE_REFRESH_IN_META = re.compile('http-equiv\s*=\s*[\'"]?refresh[\'"]?')
RE_CONTENT_URL_IN_META = re.compile('content\s*=\s*[\'"]?[0-9]*\s*;\s*url\s*=\s*[\'"]?([^\'">]+)')
RE_WINDOW_LOCATION_REDIRECT = re.compile('window.location=[\'"]([^\'"]+)[\'"]')
RE_DOCUMENT_LOCATION_HREF_REDIRECT = re.compile('document.location.href=[\'"](^\'"]+)[\'"]')
RE_FORM_SUBMIT_REDIRECT = re.compile('document.forms\[[0-9]+\].submit()')

''' Cache structure
cache (content cache): cache[input_url][each_redirect_url] = str(page content)
header_cache: header_cache[input_url][each_redirect_url] = dict(response header)
meta_cache: meta_cache[input_url] = dict(meta data)
'''
class DlerError(Exception): pass
class Dler(object):
    def __init__(self, max_thread = 5, cache = None, header_cache = None, meta_cache = None):
        self.max_thread = max_thread
        self.thread_pool = {}
        self.condition = threading.Condition()
        self.event = threading.Event()
        self.cache = {} if cache is None else cache
        self.header_cache = {} if header_cache is None else header_cache
        self.meta_cache = {} if meta_cache is None else meta_cache
        self.extractor = None

    def set_extractor(self, extractor):
        self.extractor = extractor
        
    def download(self, url_iterable, does_content_redirect=False, timeout_seconds=30):
        begin_time = time.time()
        try:
            url_iterator = iter(url_iterable)
        except TypeError as e:
            raise DlerError(e)

        url_set = set(url_iterator)
        user_agent_num = random.randint(0, LEN_USER_AGENT_LIST-1)

        while len(self.thread_pool) != 0 or len(url_set) != 0 :
            round_time = time.time()
            if abs(round_time - begin_time) > int(timeout_seconds) :
                raise DlerError('Get timeout when downloading')

            _len_thread_pool = len(self.thread_pool)
            _len_url_set = len(url_set)

            if _len_thread_pool < self.max_thread and _len_url_set > 0:
                self._parallel_download(url_set, _len_thread_pool, _len_url_set, user_agent_num, does_content_redirect)

            ''' TODO check if this sleep is better to keep '''
            time.sleep(0.1) 

        return self

    def _parallel_download(self, url_set, len_thread_pool, len_url_set, user_agent_num, does_content_redirect):
        quota = self.max_thread - len_thread_pool
        for i in xrange(min(quota, len_url_set)):
            url = url_set.pop()
            self.cache[url] = {}
            self.header_cache[url] = {}
            self.meta_cache[url] = {}
            self.thread_pool[url] = DlerThread(url, self.condition, self.event, self.thread_pool, self.cache[url], self.header_cache[url], self.meta_cache[url], user_agent_num, does_content_redirect)
            self.thread_pool[url].start()


class DlerThreadError(Exception): pass
class DlerThread(threading.Thread):
    def __init__(self, url, condition, event, thread_pool, content_dict, header_dict, meta_dict, user_agent_num, does_content_redirect, max_redirect = None):
        threading.Thread.__init__(self)
        self.content_dict = content_dict
        self.header_dict = header_dict
        self.meta_dict = meta_dict
        self.url = url
        self.url_chain = [url]
        self.con = condition
        self.event  = event
        self.thread_pool = thread_pool
        self.user_agent_num = user_agent_num
        self.max_redirect = 12 if max_redirect is None else max_redirect
        self.does_content_redirect = does_content_redirect
        ''' TODO accept langauge will be used to target regional, e.g. only open for zh-cn and block if there is ja-jp '''
        self.custom_header = ['Accept-Language:zh-tw,zh-cn,zh-hk,zh-mo,en-us,en-gb,en-ca,fr-fr,de-de,it-it,ja-jp,ru-ru,es-es,pt-br,es-mx,bn-in,da-dk']

    def run(self):
        try:
            self.download_url()
            self.thread_pool.pop(self.url, None)
        except Exception as e:
            self.meta_dict[KEY_META_SUCCESSFULLY_DOWNLOAD] = False
            self.meta_dict[KEY_META_FAILED_DOWNLOAD_REASON] = '%s:%s' % (e.__class__.__name__, str(e))
            self.thread_pool.pop(self.url, None)

    def download_url(self):
        download_chain = [self.url]
        redirected_num = 0

        while(len(download_chain) != 0):
            do_redirect = False

            url = download_chain.pop(0)
            self.content_dict[url], self.header_dict[url], http_code = self._curl(url, self.user_agent_num)

            if KEY_CURL_HEADER_LOCATION in self.header_dict[url] and http_code >= 300 and http_code < 400:
                next_url = urljoin(url, self.header_dict[url][KEY_CURL_HEADER_LOCATION])
                if not next_url or url == next_url: continue
                do_redirect = True

            ''' 
            This function aggressively find redirect URL
            by parse content and find the possible auto triggerring connect URL.
            Lower the content for regular expression match, but it might wrongly update URL and cause 404
            ''' 
            if not do_redirect and self.does_content_redirect:
                url_set = find_redirect(self.content_dict[url].lower())
                len_url_set = len(url_set)

                if len_url_set == 1: 
                    next_url = urljoin(url, url_set.pop())
                    do_redirect = True
                elif len_url_set > 1:
                    raise DlerThreadError('Get more than 1 URL to redirect from content parsing')

            if do_redirect:
                download_chain.append(next_url)
                self.url_chain.append(next_url)
                redirected_num += 1

                if redirected_num >= self.max_redirect:
                    self.meta_dict[KEY_META_IS_REDIRECT_COMPLETE] = False
                    break

        self.meta_dict[KEY_META_IS_REDIRECT_COMPLETE] = self.meta_dict.get(KEY_META_IS_REDIRECT_COMPLETE, True)
        self.meta_dict[KEY_META_REDIRECT_PATH] = self.url_chain
        self.meta_dict[KEY_META_CONTENT_LENGTH] = len(self.content_dict[self.url_chain[-1]]) if self.url_chain[-1] in self.content_dict else -1

    def _compose_url_from_location(self, url, location_url):
        if location_url.startswith('http'):
            return location_url

        url_tok = urlparse(url)
        return '%s://%s%s'%(url_tok.scheme, url_tok.netloc, location_url)

    def _curl(self, url, user_agent_num=0):
        string_buffer = StringIO()
        header_buffer = list()
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.HTTPHEADER, self.custom_header)
        c.setopt(c.WRITEFUNCTION, string_buffer.write)
        c.setopt(c.FOLLOWLOCATION, False)
        c.setopt(c.USERAGENT, CURL_OPT_USER_AGENT_LIST[user_agent_num])
        c.setopt(c.MAXREDIRS, CURL_OPT_MAX_NUM_REDIRECT)
        c.setopt(c.HEADERFUNCTION, header_buffer.append)
        c.setopt(c.SSL_VERIFYPEER, 0)
        try:
            c.perform()
        except Exception as e:
            self.meta_dict[KEY_META_SUCCESSFULLY_DOWNLOAD] = False
            self.meta_dict[KEY_META_FAILED_DOWNLOAD_REASON] = '%s:%s' % (e.__class__.__name__, str(e))
            raise DlerThreadError(e)

        http_code = int(c.getinfo(c.HTTP_CODE))
        self.meta_dict[KEY_META_HTTP_CODE] = http_code
        self.meta_dict[KEY_META_SUCCESSFULLY_DOWNLOAD] = True

        c.close()

        return string_buffer.getvalue(),  self._header_line_to_dict(header_buffer), http_code

    def _header_line_to_dict(self, _list):
        _tmp = {}

        _list = [line.strip() for line in _list if line.strip()]
        first_line = _list.pop(0)
        _tmp[KEY_CURL_HEADER_RESPONSE] = first_line
        for line in _list:
            line = line.strip()
            if not line: continue
            name, value = line.split(':', 1)
            name = name.strip().lower()
            value = value.strip()
            _tmp[name] = value

        return _tmp


def find_redirect(lower_page):
    redirect_url = set()

    #meta refresh url
    if self.extractor:
        try:
            url_extractor = self.extractor.Extractor(self.content_dict[url])
            for url in url_extractor.get_meta_refresh_url_list():
                url = url.strip()
                if url: redirect_url.add(url)
        except Exception as e:
            raise DlerThreadError(e)
    else:
        before_body = RE_BEFORE_BODY.findall(lower_page)
        page = ' '.join(before_body) if before_body else lower_page
        metas = RE_META_TAG.findall(page)
        for meta in metas:
            refresh_meta = RE_REFRESH_IN_META.search(meta)
            if not refresh_meta: continue
            urls = RE_CONTENT_URL_IN_META.findall(meta)
            if urls:
                redirect_url.add(urls[0])

    # javascript redirect
    scripts = RE_JAVASCRIPT.findall(lower_page)
    for item in scripts:
        for url in RE_WINDOW_LOCATION_REDIRECT.findall(item): redirect_url.add(url)
        for url in RE_DOCUMENT_LOCATION_HREF_REDIRECT.findall(item): redirect_url.add(url)
        for url in RE_FORM_SUBMIT_REDIRECT.findall(item): redirect_url.add(url)

    return set([url.strip() for url in redirect_url if url.strip()])
            

if __name__ == '__main__':
    dler = Dler()
    #dler.download(['1', '2', '3', '4', '5'])
    print time.time()
    #dler.download(['https://facebook.com', 'http://google.com', 'http://github.com', 'http://twitch.tv', 'http://paypal.com'])
    #print dler.cache
    #print dler.header_cache
    #print time.time()
    #print dler.meta_cache['http://google.com'][KEY_META_REDIRECT_PATH]
    #print dler.meta_cache['http://paypal.com'][KEY_META_REDIRECT_PATH]

    import sys
    dler.download([sys.argv[1]], True)
    print dler.meta_cache

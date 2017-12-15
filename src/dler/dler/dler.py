import pycurl
import threading
import time
from StringIO import StringIO
import random
from urlparse import urljoin
import re
import hashlib


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

KEY_META_REDIRECT_PATH = 'redirect_url_list'
KEY_META_IS_REDIRECT_COMPLETE = 'is_redirect_complete'
KEY_META_FINISH_DOWNLOAD = 'finish_download'
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
    def __init__(self, max_thread = 10, cache = None, header_cache = None, meta_cache = None, extractor = None):
        self.max_thread = max_thread
        self.thread_pool = {}
        self.condition = threading.Condition()
        self.event = threading.Event()

        cache = {} if cache is None else cache
        header_cache = {} if header_cache is None else header_cache
        meta_cache = {} if meta_cache is None else meta_cache
        self.dler_cache = DlerCache(cache, header_cache, meta_cache)

        self.extractor = extractor if extractor else None

    def set_extractor(self, extractor):
        self.extractor = extractor

    def clean(self):
        self.condition = threading.Condition()
        self.event = threading.Event()
        self.thread_pool = {}
        self.cache = {}
        self.header_cache = {}
        self.meta_cache = {}

    def close_curl_model(self, url=None):
        if url:
            dler_thread = self.thread_pool.get(url, None)
            if dler_thread:
                dler_thread.close_curl_model()

        else:
            for url in self.thread_pool:
                dler_thread = self.thread_pool[url]
                dler_thread.close_curl_model()

    def get_archive_data(self, url):
        cache_map = {}
        content_sha1_map = {}
        header_map = {}
        header_sha1_map = {}
        meta_map = {}
        meta_sha1_map = {}

        # divide content to store
        url_cache = self.cache.get(url, {})
        for redirect_url in url_cache:
            content_str = url_cache[redirect_url]
            content_sha1 = hashlib.sha1(content_str).hexdigest()
            cache_map[redirect_url] = content_sha1
            content_sha1_map[sha1] = content_str

        header_cache = self.header_cache.get(url, {})
        for redirect_url in header_cache:
            header_json = json.dumps(header_cache[redirect_url])
            header_sha1 = hashlib.sha1(header_json).hexdigest()
            header_map[redirect_url] = header_sha1
            header_sha1_map[sha1] = header_json

        meta_json = json.dumps(self.meta_cache.get(url, {}))
        meta_sha1 = hashlib.sha1(meta_json)
        meta_map[url] = meta_sha1
        meta_sha1_map[meta_sha1] = meta_json

        return cache_map, content_sha1_map, header_map, header_sha1_map, meta_map, meta_sha1_map
        
    def download(self, url_iterable, does_content_redirect=False, timeout_seconds=30, header_only=False):
        begin_time = time.time()
        try:
            url_iterator = iter(url_iterable)
        except TypeError as e:
            raise DlerError(e)

        url_set = set(url_iterator)
        user_agent_num = random.randint(0, LEN_USER_AGENT_LIST-1)

        while len(self.thread_pool) != 0 or len(url_set) != 0 :
            round_time = time.time()
            if abs(round_time - begin_time) > int(timeout_seconds):
                self.close_curl_model()
                raise DlerError('Get timeout when downloading')

            _len_thread_pool = len(self.thread_pool)
            _len_url_set = len(url_set)

            if _len_thread_pool < self.max_thread and _len_url_set > 0:
                self._parallel_download(url_set, _len_thread_pool, _len_url_set, user_agent_num, does_content_redirect, header_only)

            ''' TODO check if this sleep is better to keep '''
            time.sleep(0.05) 

        return self

    def _parallel_download(self, url_set, len_thread_pool, len_url_set, user_agent_num, does_content_redirect, header_only):
        quota = self.max_thread - len_thread_pool
        for i in xrange(min(quota, len_url_set)):
            url = url_set.pop()
            self.thread_pool[url] = DlerThread(url, self.condition, self.event, self.thread_pool, self.dler_cache, user_agent_num, does_content_redirect, extractor=self.extractor, header_only=header_only)
            self.thread_pool[url].start()


def valid_dict(func):
    def funciton_with_dict_input(*args, **kwargs):
        for arg in args[1:]:
            if not isinstance(arg, dict):
                raise DlerCacheError('The input %s should be a dict but is %s.' % (arg, type(arg)))

        for k in kwargs:
            if not isinstance(kwargs[k], dict):
                raise DlerCacheError('The input %s should be a dict but is %s.' % (k, type(arg)))

        return func(*args, **kwargs)

    return funciton_with_dict_input

def init_meta_cache(func):
    def checked_meta_cache_function(*args, **kwargs):
        try:
            self = args[0]
            url = args[1]
        except KeyError as e:
            raise DlerCacheError('get key error: %s' % e)

        if url not in self.meta_cache:
            self.meta_cache[url] = {}

        return func(*args, **kwargs)

    return checked_meta_cache_function

class DlerCacheError(DlerError):pass
class DlerCache(object):
    def __init__(self, content_cache=None, header_cache=None, meta_cache=None):
        # key: url
        # value: downloaded content
        self.content_cache = content_cache if content_cache else {}
        # key: url
        # value: header from response
        self.header_cache = header_cache if header_cache else {}
        # key: url
        # value: defined meta data of URL
        self.meta_cache = meta_cache if meta_cache else {}

    #@valid_dict
    def set_content_cache(self, _dict):
        self.content_cache = _dict

    #@valid_dict
    def set_header_cache(self, _dict):
        self.header_cache = _dict

    #@valid_dict
    def set_meta_cache(self, _dict):
        self.meta_cache = _dict

    def set_header_dict(self, url, header):
        if not isinstance(url, str):
            raise DlerCacheError('url should be a str but input is %s' % (type(url)))

        if not isinstance(header, dict):
            raise DlerCacheError('header should be a dict but input is %s' % (type(header)))

        self.header_cache[url] = header

    def get_header_dict(self, url):
        return self.header_cache.get(url, {})

    def set_content(self, url, content):
        self.content_cache[url] = content

    def get_content(self, url):
        return self.content_cache.get(url, None)

    def get_final_content(self, url):
        final_url = self.get_final_url(url)
        if final_url:
            return self.get_content(final_url)
        else:
            return self.get_content(url)

    def get_final_url(self, url):
        return self.meta_cache.get(url, {}).get(KEY_META_REDIRECT_PATH, [])[-1]

    @init_meta_cache
    def set_redirect_url_list(self, url, redirect_url_list):
        if not isinstance(redirect_url_list, list):
            raise DlerCacheError('redirect_url_list should be a list but %s' % type(redirect_url_list))

        self.meta_cache[url][KEY_META_REDIRECT_PATH] = redirect_url_list

    def get_redirect_url_list(self, url):
        return self.meta_cache.get(url, {}).get(KEY_META_REDIRECT_PATH, None)

    @init_meta_cache
    def set_is_redirect_completed(self, url, is_compeleted):
        is_compeleted_boolean = True if is_compeleted else False
        self.meta_cache[url][KEY_META_IS_REDIRECT_COMPLETE] = is_compeleted_boolean

    def is_redirect_completed(self, url):
        return self.meta_cache.get(url, {}).get(KEY_META_IS_REDIRECT_COMPLETE, None)

    @init_meta_cache
    def set_is_download_finish(self, url, is_finish):
        is_finish_boolean = True if is_finish else False
        self.meta_cache[url][KEY_META_FINISH_DOWNLOAD] = is_finish_boolean

    def is_download_finish(self, url):
        return self.meta_cache.get(url, {}).get(KEY_META_FINISH_DOWNLOAD, None)

    @init_meta_cache
    def set_failed_download_reason(self, url, reason):
        self.meta_cache[url][KEY_META_FAILED_DOWNLOAD_REASON] = reason

    def get_failed_download_reason(self, url):
        self.meta_cache.get(url, {}).get(KEY_META_FAILED_DOWNLOAD_REASON, '')

    @init_meta_cache
    def set_content_length(self, url, content_length):
        try:
            content_length = int(content_length)
        except (ValueError, TypeError) as e:
            raise DlerCacheError('Invalid content length type. %s'%e)

        self.meta_cache[url][KEY_META_CONTENT_LENGTH] = content_length

    def get_content_length(self, url):
        return self.meta_cache.get(url, {}).get(KEY_META_CONTENT_LENGTH, -1)

    @init_meta_cache
    def set_final_http_code(self, url, http_code):
        try:
            http_code = int(http_code)
        except (ValueError, TypeError) as e:
            raise DlerCacheError('Invalid http code type. %s'%e)

        self.meta_cache[url][KEY_META_HTTP_CODE] = http_code

    def get_final_http_code(self, url):
        return self.meta_cache.get(url, {}).get(KEY_META_HTTP_CODE, -1)




class DlerThreadError(DlerError): pass
class DlerThread(threading.Thread):
    def __init__(self, url, condition, event, thread_pool, dler_cache, user_agent_num, does_content_redirect, max_redirect = None, extractor = None, header_only=False):
        threading.Thread.__init__(self)
        if not isinstance(dler_cache, DlerCache):
            raise DlerThreadError('dler_cache should be instance of DlerCache but %s'%type(dler_cache))
        self.dler_cache = dler_cache
        self.url = url
        self.url_chain = [url]
        self.con = condition
        self.event  = event
        self.thread_pool = thread_pool
        self.user_agent_num = user_agent_num
        self.max_redirect = 12 if max_redirect is None else max_redirect
        self.extractor = extractor if extractor else None
        self.does_content_redirect = does_content_redirect
        self.header_only = header_only
        ''' TODO accept langauge will be used to target regional, e.g. only open for zh-cn and block if there is ja-jp '''
        self.custom_header = ['Accept-Language:zh-tw,zh-cn,zh-hk,zh-mo,en-us,en-gb,en-ca,fr-fr,de-de,it-it,ja-jp,ru-ru,es-es,pt-br,es-mx,bn-in,da-dk']
        self.curl_model_list = []

    def close_curl_model(self):
        for c in self.curl_model_list:
            try:
                c.close()
            except:
                pass

    def run(self):
        try:
            self.download_url()
            self.thread_pool.pop(self.url, None)
        except Exception as e:
        #except ValueError as e:
            self.dler_cache.set_is_download_finish(self.url, False)
            failed_reason = '%s:%s' % (e.__class__.__name__, str(e))
            self.dler_cache.set_failed_download_reason(self.url, failed_reason)
            self.close_curl_model()
            self.thread_pool.pop(self.url, None)

    def download_url(self):
        to_be_download_list = [self.url]
        redirected_num = 0

        while(len(to_be_download_list) != 0):
            do_redirect = False

            url = to_be_download_list.pop(0)
            content, header_dict, http_code = self._curl(url, self.user_agent_num)
            self.dler_cache.set_content(url, content)
            self.dler_cache.set_header_dict(url, header_dict)
            # use the begining url as key for meta information
            self.dler_cache.set_final_http_code(self.url, http_code)

            if KEY_CURL_HEADER_LOCATION in header_dict and http_code >= 300 and http_code < 400:
                next_url = urljoin(url, header_dict[KEY_CURL_HEADER_LOCATION])
                if not next_url or url == next_url: continue
                do_redirect = True

            ''' 
            This function aggressively find redirect URL
            by parse content and find the possible auto triggerring connect URL.
            Lower the content for regular expression match, but it might wrongly update URL and cause 404
            ''' 
            if not do_redirect and self.does_content_redirect:
                url_set = self.find_redirect(content)
                len_url_set = len(url_set)

                if len_url_set == 1: 
                    next_url = urljoin(url, url_set.pop())
                    do_redirect = True

                elif len_url_set > 1:
                    raise DlerThreadError('Get more than 1 URL to redirect from content parsing')

            if do_redirect:
                to_be_download_list.append(next_url)
                self.url_chain.append(next_url)
                redirected_num += 1

                if redirected_num >= self.max_redirect:
                    self.dler_cache.set_is_download_finish(self.url, False)
                    self.dler_cache.set_is_redirect_completed(self.url, False)
                    break
            elif not to_be_download_list:
                self.dler_cache.set_is_redirect_completed(self.url, True)


        self.dler_cache.set_redirect_url_list(self.url, self.url_chain)
    
        final_content = self.dler_cache.get_final_content(self.url)
        len_final_content = len(final_content) if final_content is not None else -1
        self.dler_cache.set_content_length(self.url, len_final_content)

    def _curl(self, url, user_agent_num=0):
        string_buffer = StringIO()
        header_buffer = list()
        c = pycurl.Curl()
        self.curl_model_list.append(c)
        c.setopt(c.URL, url)
        c.setopt(c.HTTPHEADER, self.custom_header)
        if self.header_only:
            c.setopt(c.NOBODY, 1)
        else:
            c.setopt(c.WRITEFUNCTION, string_buffer.write)
        c.setopt(c.FOLLOWLOCATION, False)
        c.setopt(c.USERAGENT, CURL_OPT_USER_AGENT_LIST[user_agent_num])
        c.setopt(c.MAXREDIRS, CURL_OPT_MAX_NUM_REDIRECT)
        c.setopt(c.HEADERFUNCTION, header_buffer.append)
        c.setopt(c.SSL_VERIFYPEER, 0)

        try:
            c.perform()

        except Exception as e:
            self.dler_cache.set_is_download_finish(self.url, False)

            failed_reason = '%s:%s' % (e.__class__.__name__, str(e))
            self.dler_cache.set_failed_download_reason(self.url, failed_reason)

            raise DlerThreadError(e)

        http_code = int(c.getinfo(c.HTTP_CODE))
        self.dler_cache.set_final_http_code(self.url, http_code)
        self.dler_cache.set_is_download_finish(self.url, True)

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

    def find_redirect(self, page):
        lower_page = page.lower()
        redirect_url = set()
    
        #meta refresh url
        if self.extractor:
            try:
                url_extractor = self.extractor.Extractor(page)
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
    sys.path.append('/Users/paul_lin/python_small_function/src/extractor/extractor/')
    import extractor
    dler.set_extractor(extractor)
    dler.download([sys.argv[1]], True, header_only=False)
    #dler.download([sys.argv[1]], True, header_only=False)
    #print dler.dler_cache.get_final_content(sys.argv[1])
    print dler.dler_cache.content_cache
    print dler.dler_cache.header_cache
    print ''
    print dler.dler_cache.meta_cache

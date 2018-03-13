import pycurl
import threading
import time
from StringIO import StringIO
import random
from urlparse import urljoin
import re
import hashlib


CURL_OPT_MAX_NUM_REDIRECT = 12
CURL_OPT_USER_AGENT_LIST = [ 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36', # Windows 10 Chrome 63
                             'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.2224.3 Safari/537.36', # Windows XP Chrome 62
                             'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.2228.0 Safari/537.36', # Windows 7 Chrome 62
                             'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.2227.1 Safari/537.36', # OSX Chrome 62
                             'Mozilla/4.0 (Compatible; MSIE 8.0; Windows NT 5.2; Trident/6.0)', # Windows Server 2003 IE 10
                             'Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; SLCC1; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET CLR 1.1.4322)' # Windows XP IE 8
                             ]
LEN_USER_AGENT_LIST = len(CURL_OPT_USER_AGENT_LIST)
DEFAULT_USER_AGENT_NUMBER = 0
KEY_CURL_HEADER_RESPONSE = '_response'

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
    def __init__(self, max_connection = 10, cache = None, header_cache = None, meta_cache = None, extractor = None, proxy = None):
        self.custom_header = ['Accept-Language:zh-tw,zh-cn,zh-hk,zh-mo,en-us,en-gb,en-ca,fr-fr,de-de,it-it,ja-jp,ru-ru,es-es,pt-br,es-mx,bn-in,da-dk']        
        try:
            self.max_connection = int(max_connection)
        except ValueError as e:
            raise DlerError('invalid value of max_connection', e)

        if self.max_connection <= 0:
            raise DlerError('max_connection should be at least 1')

        cache = {} if cache is None else cache
        header_cache = {} if header_cache is None else header_cache
        meta_cache = {} if meta_cache is None else meta_cache
        self.dler_cache = DlerCache(cache, header_cache, meta_cache)

        self.extractor = extractor if extractor else None

        try:
            import signal
            from signal import SIGPIPE, SIG_IGN
        except ImportError:
            pass
        else:
            signal.signal(SIGPIPE, SIG_IGN)

        self.proxy = proxy


    def set_extractor(self, extractor):
        self.extractor = extractor


    def set_proxy(self, proxy):
        self.proxy = proxy


    def clean(self):
        # TODO
        self.dler_cache = DlerCache()


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
        

    def download(self, url_iterable, does_content_redirect=False, timeout_seconds=10, header_only=False):
        begin_time = time.time()
        expected_timeout_time = timeout_seconds + begin_time
        try:
            url_iterator = iter(url_iterable)
        except TypeError as e:
            raise DlerError(e)

        #redirect_list_dict = {'root url': [redirect urls]}
        redirect_list_dict = {}
        #url_tuple_to_download = list(tuple(root_url, url))
        url_tuple_to_download = []
        for url in list(set(url_iterator)):
            url_tuple_to_download.append((url, url))
            redirect_list_dict[url] = [url]

        num_url_to_download = len(url_tuple_to_download)

        multi_curl = self._get_prepared_multi_curl(num_url_to_download)
        free_curl_list = multi_curl.handles[:]
        url_string_buffer_dict = {}
        url_header_buffer_dict = {}
        url_map_root_url_dict = {}

        while num_url_to_download != 0:
            remain_timeout = expected_timeout_time - time.time()
            if remain_timeout < 0:
                raise DlerError('Get timeout when downloading')

            while free_curl_list and url_tuple_to_download:
                root_url, url = url_tuple_to_download.pop()
                url_map_root_url_dict[url] = root_url
                curl_module = free_curl_list.pop()

                string_buffer = StringIO()
                header_buffer = list()
                url_string_buffer_dict[url] = string_buffer
                url_header_buffer_dict[url] = header_buffer

                curl_module = self._set_url_curl_module(url, curl_module, remain_timeout, string_buffer, header_buffer, header_only)
                multi_curl.add_handle(curl_module)

            while True:
                # MultiCurl.perform() is asynchronized
                ret, num_handles = multi_curl.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break

            while True:
                num_q, ok_list, err_list = multi_curl.info_read()

                for c in ok_list:
                    multi_curl.remove_handle(c)
                    url = c.url
                    root_url = url_map_root_url_dict[url]
                    redirect_url = self.get_redirect_url(url, url_string_buffer_dict, redirect_list_dict[root_url])

                    if redirect_url:
                        url_tuple_to_download.append((root_url, redirect_url))
                        num_url_to_download += 1

                    self._update_ok_url(root_url, c, url_string_buffer_dict, url_header_buffer_dict, redirect_url, redirect_list_dict[root_url])
                    free_curl_list.append(c)
                    
                for c, errno, errmsg in err_list:
                    multi_curl.remove_handle(c)
                    root_url = url_map_root_url_dict[url]
                    self._update_err_url(root_url, c, errmsg)
                    free_curl_list.append(c)

                num_url_to_download -= (len(ok_list) + len(err_list))

                if num_q <= 0:
                    break

            multi_curl.select(0.5)


    def _update_ok_url(self, root_url, curl_module, url_string_buffer_dict, url_header_buffer_dict, redirect_url, redirect_list):
        url = curl_module.url
        final_url = curl_module.getinfo(pycurl.EFFECTIVE_URL)
        http_code = curl_module.getinfo(pycurl.HTTP_CODE)
        is_download_finish = False if redirect_url else True
        
        if url not in redirect_list:
            redirect_list.append(url)
        if url != final_url:
            redirect_list.append(final_url)
        if redirect_url and redirect_url not in redirect_list:
            redirect_list.append(redirect_url)

        try:
            string_buffer = url_string_buffer_dict[url]
        except KeyError as e:
            return self._update_err_url(root_url, curl_module, 'Get no string buffer in string buffer dictionary. (%s)'%url)

        try:
            header_buffer = url_header_buffer_dict[url]
        except KeyError as e:
            return self._update_err_url(root_url, curl_module, 'Get no header in header buffer dictionary. (%s)'%url)

        content_string = string_buffer.getvalue()
        self.dler_cache.set_content(final_url, content_string)
        self.dler_cache.set_content_length(final_url, len(content_string))

        header_dict = self._header_line_to_dict(header_buffer)
        self.dler_cache.set_header_dict(final_url, header_dict)

        self.dler_cache.set_redirect_url_list(root_url, redirect_list)
        self.dler_cache.set_is_download_finish(root_url, is_download_finish)
        self.dler_cache.set_is_redirect_completed(root_url, is_download_finish)
        self.dler_cache.set_final_http_code(root_url, http_code)
        
        return self


    def _update_err_url(self, root_url, curl_module, error_msg):
        url = curl_module.url
        self.dler_cache.set_is_download_finish(url, False)
        self.dler_cache.set_failed_download_reason(url, error_msg)
        if url != root_url:
            self.dler_cache.set_is_download_finish(root_url, False)
            self.dler_cache.set_failed_download_reason(root_url, error_msg)


    def _set_url_curl_module(self, url, curl_module, timeout, string_buffer, header_buffer, header_only):
        curl_module.url = url
        curl_module.setopt(curl_module.URL, url)
        if header_only:
            curl_module.setopt(curl_module.NOBODY, 1)
        else:
            curl_module.setopt(curl_module.WRITEFUNCTION, string_buffer.write)
        curl_module.setopt(curl_module.HEADERFUNCTION, header_buffer.append)
        curl_module.setopt(curl_module.TIMEOUT, int(timeout))

        return curl_module
        

    def _get_prepared_multi_curl(self, len_url_list):
        num_connection = min(len_url_list, self.max_connection)
        multi_curl = pycurl.CurlMulti()
        multi_curl.handles = []

        if num_connection <= 0:
            return multi_curl

        #user_agent_num = random.randint(0, LEN_USER_AGENT_LIST-1)
        user_agent_string = CURL_OPT_USER_AGENT_LIST[DEFAULT_USER_AGENT_NUMBER]

        for i in xrange(num_connection):
            curl_module = self._get_prepared_curl_module(user_agent_string)
            multi_curl.handles.append(curl_module)

        return multi_curl


    def _get_prepared_curl_module(self, user_agent_string):
        c = pycurl.Curl()
        c.setopt(c.HTTPHEADER, self.custom_header)
        c.setopt(c.FOLLOWLOCATION, True)
        c.setopt(c.USERAGENT, user_agent_string)
        c.setopt(c.MAXREDIRS, CURL_OPT_MAX_NUM_REDIRECT)
        c.setopt(c.SSL_VERIFYPEER, 0)
        c.setopt(c.SSL_VERIFYHOST, 0)
        c.setopt(pycurl.NOSIGNAL, 1)

        if self.proxy is not None:
            c.setopt(c.PROXY, self.proxy)

        return c


    def get_redirect_url(self, url, url_string_buffer_dict, redirect_url_list):
        if url not in url_string_buffer_dict: return None

        content = url_string_buffer_dict[url].getvalue()
        redirect_url = urljoin(url, self.find_redirect(content))
        if not redirect_url or redirect_url == url or redirect_url in redirect_url_list: return None

        return redirect_url


    def find_redirect(self, page):
        if not page: return None

        lower_page = page.lower()
    
        #meta refresh url
        if self.extractor:
            try:
                url_extractor = self.extractor.Extractor(page)
                for url in url_extractor.get_meta_refresh_url_list():
                    url = url.strip()
                    if url: 
                        return url                   
            except Exception as e:
                raise DlerError(e)
        else:
            before_body = RE_BEFORE_BODY.findall(lower_page)
            page = ' '.join(before_body) if before_body else lower_page
            metas = RE_META_TAG.findall(page)
            for meta in metas:
                refresh_meta = RE_REFRESH_IN_META.search(meta)
                if not refresh_meta: continue
                urls = RE_CONTENT_URL_IN_META.findall(meta)
                if urls:
                    url = urls[0].strip()
                    return url
    
        # javascript redirect
        scripts = RE_JAVASCRIPT.findall(lower_page)
        for item in scripts:
            for url in RE_WINDOW_LOCATION_REDIRECT.findall(item): return url.strip()
            for url in RE_DOCUMENT_LOCATION_HREF_REDIRECT.findall(item): return url.strip()
            for url in RE_FORM_SUBMIT_REDIRECT.findall(item): return url.strip()
    
        return None

    def _header_line_to_dict(self, _list):
        _tmp = {}
        _list = [line.strip() for line in _list if line.strip()]

        for line in _list:
            line = line.strip()
            if not line: continue
            if ':' not in line:
                _tmp = {}
                _tmp[KEY_CURL_HEADER_RESPONSE] = line
                continue
            name, value = line.split(':', 1)
            name = name.strip().lower()
            value = value.strip()
            _tmp[name] = value

        return _tmp


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
        try:
            return self.meta_cache.get(url, {}).get(KEY_META_REDIRECT_PATH, [])[-1]
        except IndexError as e:
            return url

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
            

if __name__ == '__main__':
    #dler = Dler(proxy='http://165.84.167.54:8080/')
    dler = Dler()
    #dler.download(['1', '2', '3', '4', '5'])
    print time.time()
    #dler.download(['https://facebook.com', 'http://google.com', 'http://github.com', 'http://twitch.tv', 'http://paypal.com'])
    #dler.download(['http://github.com'])
    #print dler.dler_cache.content_cache
    #print dler.dler_cache.header_cache
    #print dler.dler_cache.meta_cache
    #print time.time()
    #print dler.meta_cache['http://google.com'][KEY_META_REDIRECT_PATH]
    #print dler.meta_cache['http://paypal.com'][KEY_META_REDIRECT_PATH]

    import sys
    #sys.exit(0)
    sys.path.append('/Users/paul_lin/python_small_function/src/extractor/extractor/')
    import extractor
    dler.set_extractor(extractor)
    dler.download([sys.argv[1]], True, header_only=False)
    #dler.download([sys.argv[1]], True, header_only=False)
    #print dler.dler_cache.get_final_content(sys.argv[1])
    #print dler.dler_cache.content_cache
    print dler.dler_cache.header_cache
    print dler.dler_cache.meta_cache

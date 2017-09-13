import pycurl
import threading
import time
from StringIO import StringIO
import random
from urlparse import urlparse

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

''' TODO
1. make a singleton
2. add timeout to pycurl opt 
3. remove __main__
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
    
    def download(self, url_iterable):
        try:
            url_iterator = iter(url_iterable)
        except TypeError as e:
            raise DlerError(e)

        url_set = set(url_iterator)
        user_agent_num = random.randint(0,LEN_USER_AGENT_LIST-1)

        while len(self.thread_pool) != 0 or len(url_set) != 0 :
            _len_thread_pool = len(self.thread_pool)
            _len_url_set = len(url_set)

            if _len_thread_pool < self.max_thread and _len_url_set > 0:
                self._parallel_download(url_set, _len_thread_pool, _len_url_set, user_agent_num)

            time.sleep(0.1) 

        return self

    def _parallel_download(self, url_set, len_thread_pool, len_url_set, user_agent_num=0):
        quota = self.max_thread - len_thread_pool
        for i in xrange(min(quota, len_url_set)):
            url = url_set.pop()
            self.cache[url] = {}
            self.header_cache[url] = {}
            self.meta_cache[url] = {}
            self.thread_pool[url] = DlerThread(url, self.condition, self.event, self.thread_pool, self.cache[url], self.header_cache[url], self.meta_cache[url], user_agent_num)
            self.thread_pool[url].start()


class DlerThread(threading.Thread):
    def __init__(self, url, condition, event, thread_pool, content_dict, header_dict, meta_dict, user_agent_num):
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

    def run(self):
        self.download_url()
        self.thread_pool.pop(self.url, None)

    def download_url(self):
        download_chain = [self.url]
        while(len(download_chain) != 0):
            url = download_chain.pop(0)
            self.content_dict[url], self.header_dict[url], http_code = self._curl(url, self.user_agent_num)
            #print http_code, url, self.header_dict[url]
            if KEY_CURL_HEADER_LOCATION in self.header_dict[url] and http_code >= 300 and http_code < 400:
                next_url = self._compose_url_from_location(url, self.header_dict[url][KEY_CURL_HEADER_LOCATION])
                download_chain.append(next_url)
                self.url_chain.append(next_url)
        self.meta_dict[KEY_META_REDIRECT_PATH] = self.url_chain

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
        c.setopt(c.WRITEFUNCTION, string_buffer.write)
        c.setopt(c.FOLLOWLOCATION, False)
        c.setopt(c.USERAGENT, CURL_OPT_USER_AGENT_LIST[user_agent_num])
        c.setopt(c.MAXREDIRS, CURL_OPT_MAX_NUM_REDIRECT)
        c.setopt(c.HEADERFUNCTION, header_buffer.append)
        ''' might needs to handle exceptions '''
        c.perform()
        http_code = int(c.getinfo(c.HTTP_CODE))

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
        

if __name__ == '__main__':
    dler = Dler()
    #dler.download(['1', '2', '3', '4', '5'])
    print time.time()
    dler.download(['https://facebook.com', 'http://google.com', 'http://github.com', 'http://twitch.tv', 'http://paypal.com'])
    #print dler.cache
    #print dler.header_cache
    print time.time()
    print dler.meta_cache['http://google.com'][KEY_META_REDIRECT_PATH]
    print dler.meta_cache['http://paypal.com'][KEY_META_REDIRECT_PATH]

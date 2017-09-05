import pycurl
import threading
import time
import random

''' TODO
1. make a singleton
2. implement download by pycurl 
3. remove __main__

'''

class DlerError(Exception): pass
class Dler(object):
    def __init__(self, max_thread = 5, cache = None):
        self.max_thread = 5
        self.thread_pool = {}
        self.condition = threading.Condition()
        self.event = threading.Event()
        self.cache = {} if cache is None else cache
    
    def download(self, url_iterable):
        try:
            url_iterator = iter(url_iterable)
        except TypeError as e:
            raise DlerError(e)
        url_set = set(url_iterator)

        while len(self.thread_pool) != 0 or len(url_set) != 0 :
            _len_thread_pool = len(self.thread_pool)
            _len_url_set = len(url_set)

            if _len_thread_pool < self.max_thread and _len_url_set > 0:
                self._parallel_download(url_set, _len_thread_pool, _len_url_set)

            time.sleep(0.1) 

    def _parallel_download(self, url_set, len_thread_pool, len_url_set):
        quota = self.max_thread - len_thread_pool
        for i in xrange(min(quota, len_url_set)):
            url = url_set.pop()
            self.thread_pool[url] = DlerThread(url, self.condition, self.event, self.thread_pool, self.cache)
            self.thread_pool[url].start()
        


class DlerThread(threading.Thread):
    def __init__(self, url, condition, event, thread_pool, cache=None):
        threading.Thread.__init__(self)
        self.cache = cache if cache is not None else {}
        self.url = url
        self.con = condition
        self.event  = event
        self.thread_pool = thread_pool

    def run(self):
        self.download_url()

        self.con.acquire()
        self.thread_pool.pop(self.url, None)
        self.con.release()
       
        return self.cache

    def download_url(self):
        time.sleep(random.randint(1,5))
        self.cache[self.url] = self.url
        

if __name__ == '__main__':
    dler = Dler()
    dler.download(['1', '2', '3', '4', '5'])
    print dler.cache

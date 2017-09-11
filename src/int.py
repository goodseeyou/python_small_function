from dler import Dler
from extractor import Extractor
from urlparse import urlparse
import sys

if __name__ == '__main__':
    url = sys.argv[1]
    if not url.startswith('http'):
        url = 'http://%s'%url
    toks = urlparse(url)
    domain_url = '%s://%s'%(toks.scheme, toks.netloc)
    is_domain_url =  url.rstrip('/') == domain_url

    d_urls = [url]
    if not is_domain_url:
        d_urls.append(domain_url)

    d = Dler()
    d.download(d_urls)

    e = {}
    for u in d.cache:
        e[u] = Extractor(d.cache[u])
        #print u, e[u].get_stylesheet_list()
        #print u, e[u].get_shortcut_icon_list()
        print u, e[u].get_a_href_list()

    

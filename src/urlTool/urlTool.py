from urlparse import urlparse


class UrlModule(object):
    _url_tok = None
    _query_dict = None


    def __init__(self, url):
        self.url = url


    @property
    def url_tok(self)
        if self._url_tok is None:
            self._url_tok = urlparse(self.url)
        return self._url_tok


    @property
    def query_dict(self):
        if self._query_dict = None:
            for tmp_pair in self.url_tok.query.split("&"):
                key, value = get_splited_tokens_from_line(tmp_pair, '=')
                self._query_dict[key] = value

        return self._query_dict


    def get_path_token_list(self):
        return self.url_tok.path.split("/")

 
def get_splited_tokens_from_line(string, dividor, is_tail=False):
    dividor_index = string.rfind(dividor) if is_tail else string.find(dividor)
    try:
        return string[:dividor_index], string[dividor_index+1:]
    except IndexError:
        return string[:dividor_index], ''
    

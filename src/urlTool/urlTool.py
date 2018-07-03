from urlparse import urlparse
from string import maketrans

TRANS_NUMBER_TO_ZERO = maketrans(''.join([str(i) for i in range(10)]), ''.join((str(0),)*10))
PREFIX_LENGTH = 8

class UrlModule(object):
    _url_tok = None
    _query_dict = None


    def __init__(self, url):
        self.url = url


    @property
    def url_tok(self):
        if self._url_tok is None:
            self._url_tok = urlparse(self.url)
        return self._url_tok


    @property
    def query_dict(self):
        if self._query_dict is None:
            self._query_dict = {}

            for tmp_pair in self.url_tok.query.split("&"):
                key, value = get_splited_tokens_from_line(tmp_pair, '=')
                key = key.strip()
                if not key: continue
                self._query_dict[key] = value.strip()

        return self._query_dict


    def get_hostname_token_list(self, is_normalize=False, is_prefix_value=False):
        if is_normalize:
            hostname = self._token_normalize(self.url_tok.hostname)
        else:
            hostname = self.url_tok.hostname

        return [tok.strip() for tok in hostname.split(".") if tok.strip()]


    def get_path_token_list(self, is_normalize=False):
        if is_normalize:
            path = self._token_normalize(self.url_tok.path)
        else:
            path = self.url_tok.path

        path_tok = path.split("/")
        if not path.endswith('/'):
            path_token = ['/%s/'%tok.strip() for tok in path_tok[:-1] if tok.strip()]
            last_tok = path_tok[-1].strip()
            if last_tok:
                dot_index = last_tok.rfind('.')
                if dot_index > 0:
                    filename, file_extension = last_tok[:dot_index], last_tok[dot_index:]
                    path_token.append(filename)
                    path_token.append(file_extension)
                else:
                    filename = last_tok
                    path_token.append(filename)
        else:
            path_token = ['/%s/'%tok.strip() for tok in path_tok if tok.strip()]
        
        return path_token


    def get_query_key_value_list(self, is_normalize=False, is_prefix_value=False):
        if is_normalize:
            kv_list = [ (self._token_normalize(k), self._token_normalize(self.query_dict[k]))
                for k in self.query_dict if k]
        else:
            kv_list = [(k, self.query_dict[k]) for k in self.query_dict if k]

        if is_prefix_value:
            kv_list = [(k,v[:PREFIX_LENGTH]) for k, v in kv_list]

        return kv_list


    def _token_normalize(self, text):
        return text.translate(TRANS_NUMBER_TO_ZERO).strip()

 
def get_splited_tokens_from_line(text, dividor, is_tail=False):
    dividor_index = text.rfind(dividor) if is_tail else text.find(dividor)

    if dividor_index < 0:
        return text, ''

    try:
        return text[:dividor_index], text[dividor_index+1:]
    except IndexError:
        return text[:dividor_index], ''
    

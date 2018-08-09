from urlparse import urlparse
from string import maketrans
import socket

TRANS_NUMBER_TO_ZERO = maketrans(''.join((str(i) for i in range(10))), ''.join((str(0),)*10))
PREFIX_LENGTH = 8


class UrlModuleError(Exception): pass
class UrlModule(object):
    _url_tok = None
    _query_dict = None

    def __init__(self, url):
        self.url = url

    @property
    def url_tok(self):
        if self._url_tok is None:
            try:
                self._url_tok = urlparse(self.url)
            except ValueError as e:
                raise UrlModuleError(e)

        return self._url_tok

    @property
    def query_dict(self):
        if self._query_dict is None:
            self._query_dict = {}

            for tmp_pair in self.url_tok.query.split("&"):
                key, value = get_split_tokens_from_line(tmp_pair, '=')
                key = key.strip()
                if not key: continue
                self._query_dict[key] = value.strip()

        return self._query_dict

    def get_hostname_token_list(self, is_normalize=False, is_prefix_value=False):
        if is_normalize:
            hostname = token_normalize(self.url_tok.hostname)
        else:
            hostname = self.url_tok.hostname

        if is_prefix_value:
            return [tok.strip()[:PREFIX_LENGTH] for tok in hostname.split(".") if tok.strip()]
        else:
            return [tok.strip() for tok in hostname.split(".") if tok.strip()]

    def get_path_token_list(self, is_normalize=False, append_file_extension=True):
        if is_normalize:
            path = token_normalize(self.url_tok.path)
        else:
            path = self.url_tok.path

        path_tok = path.split("/")
        last_tok = path_tok[-1].strip()
        path_token = ['/%s/' % tok.strip() for tok in path_tok[:-1] if tok.strip()]
        if path.endswith('/'):
            path_token.append('/%s/' % last_tok)
        elif last_tok:
            path_token.append(last_tok)

            if append_file_extension:
                filename, file_extension = get_last_dot_split_tuple(last_tok)
                if file_extension: path_token.append(file_extension)

        return path_token

    def get_query_key_value_list(self, is_normalize=False, is_prefix_value=False):
        if is_normalize:
            kv_list = [(token_normalize(k), token_normalize(self.query_dict[k])) for k in self.query_dict if k]
        else:
            kv_list = [(k, self.query_dict[k]) for k in self.query_dict if k]

        if is_prefix_value:
            kv_list = [(k, v[:PREFIX_LENGTH]) for k, v in kv_list]

        return kv_list

    def is_ip(self):
        return is_ip(self.url_tok.hostname)


def get_last_dot_split_tuple(text):
    dot_index = text.rfind('.')
    if dot_index > 0:
        left_part, right_part_with_dot = text[:dot_index], text[dot_index:]
        return left_part, right_part_with_dot

    return text, ''


def token_normalize(text):
    return translate_digit_to_zero(text)


def translate_digit_to_zero(text):
    return text.translate(TRANS_NUMBER_TO_ZERO).strip()


def get_split_tokens_from_line(text, dividor, is_tail=False):
    dividor_index = text.rfind(dividor) if is_tail else text.find(dividor)

    if dividor_index < 0:
        return text, ''

    try:
        return text[:dividor_index], text[dividor_index+1:]
    except IndexError:
        return text[:dividor_index], ''


def is_ipv4(_ip):
    try:
        socket.inet_pton(socket.AF_INET, _ip)
        return True
    except socket.error:
        return False


def is_ipv6(_ip):
    try:
        socket.inet_pton(socket.AF_INET6, _ip)
        return True
    except socket.error:
        return False


def is_ip(addr):
    netloc_toks = addr.split(":")
    len_netloc_toks = len(netloc_toks)

    if len_netloc_toks > 2:
        if '[' in addr and ']' in addr and netloc_toks[-1].isdigit():
            return is_ipv6(':'.join(netloc_toks[:-1]).strip('[]'))
        else:
            return is_ipv6(addr)
    if len_netloc_toks == 2 and netloc_toks[-1].isdigit():
        return is_ipv4(netloc_toks[0])
    else:
        return is_ipv4(addr)

import lxml
import re
from urlparse import urljoin
from urlparse import urlparse


RE_A_TAG_HREF = re.compile('<\s*a\s+[^>]*\s+href=[\'"]([^\'"]*)[\'"]')
RE_HREF = re.compile('<\s*[^>]+\s+href=[\'"]([^\'"]*)[\'"]')
RE_SRC = re.compile('<\s*[^>]+\s+src=[\'"]([^\'"]*)[\'"]')
RE_TITLE_TAG = re.compile('<\s*title\s*>([^<>]*)<\s*/\s*title\s*>')
RE_SHORTCUT_ICON = re.compile('<\s*link\s+[^>]*rel\s*=\s*[\'"]shortcut icon[\'"][^>]*?>')
RE_STYLESHEET = re.compile('<\s*link\s+[^>]*rel\s*=\s*[\'"]stylesheet[\'"][^>]*?>')
RE_SCRIPT = re.compile('<\s*script\s+[^>]*type\s*=\s*[\'"]text/javascript[\'"][^>]*?>\s*</script>')
RE_INPUT_TAG_PASSWORD_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]password[\'"][^>]*>')
RE_INPUT_TAG_TEXT_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]text[\'"][^>]*>')
RE_LIMITED_VISIBLE_TEXT = re.compile('<\s*(label|p|h[0-9]|div|span|td|a|br)\s*[^>]*>([^<>]+)')

DEFAULT_SHORTCUT_ICON = 'favicon.ico'


class ExtractorError(Exception): pass
class ExtractorAnalyzeError(Exception): pass
class Extractor(object):
    def __init__(self, page):
        self.page = page.replace('\n', '').lower()

    def get_a_href_list(self):
        return RE_A_TAG_HREF.findall(self.page)
    def get_href_list(self):
        return RE_HREF.findall(self.page)
    def get_title_list(self):
        return RE_TITLE_TAG.findall(self.page)
    def get_shortcut_icon_list(self):
        return self._get_href_from_tag(RE_SHORTCUT_ICON.findall(self.page))
    def get_stylesheet_href_list(self):
        return self._get_href_from_tag(RE_STYLESHEET.findall(self.page))
    def get_script_src_list(self):
        return self._get_src_from_tag(RE_SCRIPT.findall(self.page))
    def get_password_input_list(self):
        return RE_INPUT_TAG_PASSWORD_TYPE.findall(self.page)
    def get_text_input_list(self):
        return RE_INPUT_TAG_TEXT_TYPE.findall(self.page)
    def get_limited_visible_text_list(self):
        return [tok[1].strip() for tok in RE_LIMITED_VISIBLE_TEXT.findall(self.page) if tok[1].strip()]

    def _get_href_from_tag(self, tags):
        return self._get_re_result_from_tag(RE_HREF, tags)
    def _get_src_from_tag(self, tags):
        return self._get_re_result_from_tag(RE_SRC, tags)
    def _get_re_result_from_tag(self, compiled_re, tags):
        _set = set()
        for tag in tags:
           for r in compiled_re.findall(tag):
                if r.strip(): _set.add(r)
        return list(_set) 


# Recognize only by URL
def is_same_icon(url, target_url, url_extractor, target_extractor):
    if does_has_scheme(url) ^ does_has_scheme(target_url): raise ExtractorAnalyzeError('URL and target URL should have the same format.')

    url_icon_set = set([urljoin(url, icon_url.strip()) for icon_url in url_extractor.get_shortcut_icon_list() if icon_url.strip()])
    if not url_icon_set: url_icon_set.add(urljoin(get_domain_url(url), DEFAULT_SHORTCUT_ICON))
    len_url_icon_set = len(url_icon_set)

    target_icon_set = set([urljoin(target_url, icon_url.strip()) for icon_url in target_extractor.get_shortcut_icon_list() if icon_url.strip()])
    if not target_icon_set: target_icon_set.add(urljoin(get_domain_url(target_url), DEFAULT_SHORTCUT_ICON))
    len_target_icon_set = len(target_icon_set)

    does_has_same = False
    for url_icon in url_icon_set:
        if url_icon in target_icon_set:
            does_has_same = True
            break

    return does_has_same, len_url_icon_set, len_target_icon_set


def get_similarity_by_stylesheet(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url, target_url, url_extractor.get_stylesheet_href_list, target_extractor.get_stylesheet_href_list)

def get_similarity_by_script(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url, target_url, url_extractor.get_script_src_list, target_extractor.get_script_src_list)

def _get_similarity_by_extract_function(url, target_url, url_extract_function, target_extract_function):
    if does_has_scheme(url) ^ does_has_scheme(target_url): raise ExtractorAnalyzeError('URL and target URL should have the same format.')

    # use filename to decrease FP [case] "http://012.tw/houvyWZ"
    url_extract_set = set([extract_url.split('/')[-1].split('?')[0] for extract_url in url_extract_function()])
    len_url_extract_set = len(url_extract_set)

    target_extract_set = set([extract_url.split('/')[-1].split('?')[0] for extract_url in target_extract_function()])
    len_target_extract_set = len(target_extract_set)
    
    common_count = _common_item_count(url_extract_set, target_extract_set)

    # Both url have no extractsheet link. It's a common feature, so define the ratio as 1
    common_ratio_of_min = 1 if len_url_extract_set == 0 and len_target_extract_set == 0 \
                            else common_count / float(max(1, min(len_url_extract_set, len_target_extract_set)))

    return common_ratio_of_min, common_count, len_url_extract_set, len_target_extract_set


def _common_item_count(iter_a, iter_b):
    _count = 0
    for a in iter_a:
        if a in iter_b: _count += 1

    return _count


def get_domain_url(url):
    tok = urlparse(url)
    return '%s://%s/' % (tok.scheme, tok.netloc)


def get_path(url):
    tok = urlparse(url)
    return tok.path.split('?')[0]


def does_has_scheme(url):
    tok = urlparse(url)
    return str(tok.scheme).strip() != ''
    

if __name__ == '__main__':
    import sys
    with open(sys.argv[1],'r') as data:
        extractor = Extractor(data.read())

    #print extractor.get_a_href_list()
    #print extractor.get_href_list()
    #print extractor.get_title_list()
    #print extractor.get_shortcut_icon_list()
    print extractor.get_stylesheet_href_list()
    print extractor.get_script_src_list()
    #print extractor.get_password_input_list()
    #print extractor.get_limited_visible_text_list()

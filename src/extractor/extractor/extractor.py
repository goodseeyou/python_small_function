import lxml
from bs4 import BeautifulSoup
from bs4.element import Comment
import re
from urlparse import urljoin
from urlparse import urlparse


RE_A_TAG_HREF = re.compile('<\s*a\s+[^>]*\s+href\s*=\s*[\'"]([^\'"]*)[\'"]')
RE_HREF = re.compile('<\s*[^>]+\s+href\s*=\s*[\'"]([^\'"]*)[\'"]')
RE_SRC = re.compile('<\s*[^>]+\s+src\s*=\s*[\'"]([^\'"]*)[\'"]')
RE_TITLE_TAG = re.compile('<\s*title\s*>([^<>]*)<\s*/\s*title\s*>')
RE_SHORTCUT_ICON = re.compile('<\s*link\s+[^>]*rel\s*=\s*[\'"]shortcut icon[\'"][^>]*?>')
RE_STYLESHEET = re.compile('<\s*link\s+[^>]*rel\s*=\s*[\'"]stylesheet[\'"][^>]*?>')
RE_SCRIPT = re.compile('<\s*script\s+[^>]*type\s*=\s*[\'"]text/javascript[\'"][^>]*?>\s*</script>')
RE_IMG = re.compile('<\s*img\s+[^>]*src\s*=\s*[\'"][^\'"<>]+[\'"][^>]*?>')
RE_INPUT_TAG_PASSWORD_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]password[\'"][^>]*>')
RE_INPUT_TAG_TEXT_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]text[\'"][^>]*>')
RE_INPUT_TAG_SUBMIT_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]submit[\'"][^>]*>')
RE_SELECT_TAG = re.compile('<\s*select\s*[^>]+>')
RE_OPTION_TAG = re.compile('<\s*option\s*[^>]+>')
RE_ENG_NUM_TEXT = re.compile('[0-9a-zA-Z]+')
RE_DISPLAY_NONE = re.compile('display\s*:\s*[^;]*none')
RE_URL_FROM_META_REFRESH = re.compile('(URL|url)\s*=\s*(.*)')

STOP_WORD = ('div', 'span', 'input', 'form', 'link', 'script', 'meta', 'style', 'img', 'h1', 'h2', 'h3', 'p', 'br', 'class', 'id', 'tr', 'td', 'label', 'a')

DEFAULT_SHORTCUT_ICON = 'favicon.ico'


class ExtractorError(Exception): pass
class ExtractorAnalyzeError(Exception): pass
class Extractor(object):
    def __init__(self, page):
        self.soup = BeautifulSoup(page, 'lxml')
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
    def get_img_src_list(self):
        return self._get_src_from_tag(RE_IMG.findall(self.page))
    def get_password_input_list(self):
        return RE_INPUT_TAG_PASSWORD_TYPE.findall(self.page)
    def get_text_input_list(self):
        return RE_INPUT_TAG_TEXT_TYPE.findall(self.page)
    def get_submit_input_list(self):
        return RE_INPUT_TAG_SUBMIT_TYPE.findall(self.page)
    def get_select_list(self):
        return RE_SELECT_TAG.findall(self.page)
    def get_option_list(self):
        return RE_OPTION_TAG.findall(self.page)
    def get_limited_visible_text_list(self):
        try:
            return self.text_from_html()
        except (TypeError, UnicodeDecodeError) as e:
            raise ExtractorError(e)
    def get_title_text_list(self):
        return self.get_lower_eng_num_text_list(text = ' '.join(self.get_title_list()))
    def get_lower_eng_num_text_list(self, text=None):
        if text is None:
            return [tok.lower().strip() for tok in RE_ENG_NUM_TEXT.findall(self.page) if tok not in STOP_WORD]
        else:
            return [tok.lower().strip() for tok in RE_ENG_NUM_TEXT.findall(text)]

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


    def _tag_visible(self, element):
        if element.parent.name in ('style', 'script', 'head', 'title', 'meta', '[document]', 'noscript', ):
            return False

        if isinstance(element, Comment):
            return False

        if self._is_hiden(element):
            return False

        return True
    

    def _is_hiden(self, element):
        if not element: return False

        for parent in element.parents:
            if not parent: return False

            if parent.name in ('style', 'script', 'head', 'title', 'meta', 'noscript', ):
                return True

            if parent.name in ('body', 'html', ):
                return False

            if parent.attrs.get('aria-hidden', '').lower() == 'true':
                return True

            if RE_DISPLAY_NONE.search(parent.attrs.get('style', '')):
                return True
    
        return False
    

    def text_from_html(self):
        texts = self.soup.findAll(text=True)
        visible_texts = filter(self._tag_visible, texts)  

        return u" ".join(t.strip() for t in visible_texts if t.strip() and t)


    def _meta_refresh(self, element):
        if not element: return False

        if element.parent.name not in ('head', 'html', '[document]', ):
            return False

        if element.attrs.get('http-equiv', '').strip().lower() == 'refresh':
            return True

        return False
    

    def meta_fresh_tag(self):
        metas = self.soup.findAll('meta')
        return filter(self._meta_refresh, metas)


    def get_meta_fresh_url_list(self):
        meta_refreshes = self.meta_fresh_tag()

        redirect_url_list = []
        for value in [t.attrs.get('content','') for t in meta_refreshes] :
            re_value = RE_URL_FROM_META_REFRESH.search(value)
            if re_value:
                redirect_url_list.append(re_value.group(2))
            
        return redirect_url_list


def _reduced_normalize_url(url):
    tok = urlparse(url)

    netloc_tok = tok.netloc.split(":")
    if netloc_tok[-1].isdigit():
        port = netloc_tok[-1]
        domain = ':'.join(netloc_tok[:-1])
    else:
        port = ''
        domain = ':'.join(netloc_tok)
    domain = domain.strip('[]')

    path = tok.path
    query = tok.query

    return '%s%s?%s' % (domain, path, query)
    

# Recognize only by URL
def is_same_icon(url, target_url, url_extractor, target_extractor):
    if does_has_scheme(url) ^ does_has_scheme(target_url): raise ExtractorAnalyzeError('URL and target URL should have the same format.')

    url_icon_set = set([_reduced_normalize_url(urljoin(url, icon_url.strip())) \
        for icon_url in url_extractor.get_shortcut_icon_list() if icon_url.strip()])
    len_url_icon_set = len(url_icon_set)

    target_icon_set = set([_reduced_normalize_url(urljoin(target_url, icon_url.strip())) \
        for icon_url in target_extractor.get_shortcut_icon_list() if icon_url.strip()])
    len_target_icon_set = len(target_icon_set)

    does_has_same_without_default = _does_has_same_item(url_icon_set, target_icon_set)

    does_has_same_with_default = True if does_has_same_without_default else False
    if not does_has_same_with_default:
        tmp_url_icon_set = set([url for url in url_icon_set])
        tmp_target_icon_set = set([url for url in target_icon_set])
        if not tmp_url_icon_set: tmp_url_icon_set.add(_reduced_normalize_url(urljoin(get_domain_url(url), DEFAULT_SHORTCUT_ICON)))
        if not tmp_target_icon_set: tmp_target_icon_set.add(_reduced_normalize_url(urljoin(get_domain_url(target_url), DEFAULT_SHORTCUT_ICON)))
        does_has_same_with_default = _does_has_same_item(tmp_url_icon_set, tmp_target_icon_set)

    return does_has_same_without_default, does_has_same_with_default, len_url_icon_set, len_target_icon_set, url_icon_set, target_icon_set

def _does_has_same_item(iter_a, iter_b):
    for a in iter_a:
        if a in iter_b:
            return True
    return False

def get_similarity_by_stylesheet(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url, target_url, url_extractor.get_stylesheet_href_list, target_extractor.get_stylesheet_href_list, is_filename_only=True)

def get_similarity_by_script(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url, target_url, url_extractor.get_script_src_list, target_extractor.get_script_src_list, is_filename_only=True)

def get_similarity_by_title_text(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url, target_url, url_extractor.get_title_text_list, target_extractor.get_title_text_list)

def get_similarity_by_img(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url, target_url, url_extractor.get_img_src_list, target_extractor.get_img_src_list, is_path_only=True)

def _get_similarity_by_extract_function(url, target_url, url_extract_function, target_extract_function, is_filename_only=False, is_path_only=False):
    if does_has_scheme(url) ^ does_has_scheme(target_url): raise ExtractorAnalyzeError('URL and target URL should have the same format.')

    # use filename to decrease FP [case] "http://012.tw/houvyWZ"
    if is_filename_only:
        url_extract_collection = set([extract_url.split('/')[-1].split('?')[0] for extract_url in url_extract_function()])
        target_extract_collection = set([extract_url.split('/')[-1].split('?')[0] for extract_url in target_extract_function()])
    elif is_path_only:
        url_extract_collection = set(['/'.join(_reduced_normalize_url(urljoin(url, extract_url)).split('/')[:-1]) for extract_url in url_extract_function()])
        target_extract_collection = set(['/'.join(_reduced_normalize_url(urljoin(target_url, extract_url)).split('/')[:-1]) for extract_url in target_extract_function()])
    else:
        url_extract_collection = [extract_item for extract_item in url_extract_function()]
        target_extract_collection = [extract_item for extract_item in target_extract_function()]

    len_url_extract_collection = len(url_extract_collection)
    len_target_extract_collection = len(target_extract_collection)
    
    common_count = _common_item_count(url_extract_collection, target_extract_collection)

    # Both url have no extractsheet link. It's a common feature, so define the ratio as 1
    common_ratio_of_min = -1000 if len_url_extract_collection == 0 and len_target_extract_collection == 0 \
                            else common_count / float(max(1, min(len_url_extract_collection, len_target_extract_collection)))

    return common_ratio_of_min, common_count, len_url_extract_collection, len_target_extract_collection


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


def is_potential_creditcard_form(extractor):
    len_text_input = len(extractor.get_text_input_list())
    len_password_input = len(extractor.get_password_input_list())
    len_submit_input = len(extractor.get_submit_input_list())
    len_select = len(extractor.get_select_list())
    len_option = len(extractor.get_option_list())
    if len_submit_input > 0:
        has_enough_select = True if len_select >= 2 and len_option >= 17 else False
        sum_of_input = len_text_input + len_password_input
        if has_enough_select:
            return sum_of_input >= 2
        else:
            return sum_of_input >= 4

    return False


def is_potential_email_form(extractor):
    len_submit_input = len(extractor.get_submit_input_list())
    text_input_list = extractor.get_text_input_list()
    if len(text_input_list) == 1 and len_submit_input == 1 and 'mail' in text_input_list[0]:
        return True

    return False



if __name__ == '__main__':
    import sys
    with open(sys.argv[1],'r') as data:
        extractor = Extractor(data.read())
    '''
    with open(sys.argv[2],'r') as data:
        t_ext = Extractor(data.read())
    #'''
    #print get_similarity_by_img('http://google.com/','http://google.com', extractor, t_ext)
    #print is_same_icon('http://www.telecomsource.net:80/showthread.php?3121-What-is-reference-signals-in-LTE','http://www.telecomsource.net/',extractor,t_ext)
    #print extractor.get_a_href_list()
    #print extractor.get_href_list()
    #print extractor.get_title_list()
    #print extractor.get_shortcut_icon_list()
    #print extractor.get_stylesheet_href_list()
    #print extractor.get_script_src_list()
    #print extractor.get_img_src_list()
    #print extractor.get_password_input_list()
    #print extractor.get_limited_visible_text_list()
    #print is_potential_creditcard_form(extractor)
    print extractor.get_meta_fresh_url_list()

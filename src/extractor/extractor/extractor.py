import lxml
from lxml import etree
from bs4 import BeautifulSoup
from bs4.element import Comment, Tag
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
RE_INPUT_TAG_IMAGE_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]image[\'"][^>]*>')
RE_INPUT_TAG_SUBMIT_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]submit[\'"][^>]*>')
RE_SELECT_TAG = re.compile('<\s*select\s*[^>]+>')
RE_OPTION_TAG = re.compile('<\s*option\s*[^>]+>')
RE_ENG_NUM_TEXT = re.compile('[0-9a-zA-Z]+')
RE_DISPLAY_NONE = re.compile('display\s*:\s*[^;]*none')
RE_URL_FROM_META_REFRESH = re.compile('(URL|url)\s*=\s*(.*)')
RE_WRITE_UNESCAPE = re.compile('document.write\s*\(\s*unescape\s*\([^)]+')


STOP_WORD = ('div', 'span', 'input', 'form', 'link', 'script', 'meta', 'style', 'img', 'h1', 'h2', 'h3', 'p', 'br', 'class', 'id', 'tr', 'td', 'label', 'a')

DEFAULT_SHORTCUT_ICON = 'favicon.ico'

COMPARE_TARGET_FULL = 'full'
COMPARE_TARGET_PATH_NO_QUERY = 'path_no_query'
COMPARE_TARGET_NO_FILENAME = 'no_filename'
COMPARE_TARGET_FILENAME = 'filename'


class ExtractorError(Exception): pass
class ExtractorAnalyzeError(ExtractorError): pass
class Extractor(object):
    def __init__(self, page):
        if not page: page = ''
        self.base_url_cache = {}
        self.page = page
        self._soup = None
        self.page_lower = page.replace('\n', '').lower()


    @property
    def soup(self):
        if self._soup is None:
            try:
                self._soup = BeautifulSoup(self.page, 'lxml')
            except (TypeError, ValueError) as e:
                raise ExtractorError('Failed to initialize Extractor due to %s' % e)
            
        return self._soup


    def get_href_list(self):
        return RE_HREF.findall(self.page_lower)


    def get_title_list(self, case_sensitive=False):
        if case_sensitive:
            return [title_tag.string for title_tag in self.soup.findAll('title') if title_tag.string is not None]
        else:
            return [title_tag.string.lower() for title_tag in self.soup.findAll('title') if title_tag.string is not None]


    def get_shortcut_icon_list(self):
        return self._get_href_from_tag(RE_SHORTCUT_ICON.findall(self.page_lower))


    def get_stylesheet_href_list(self):
        link_tag = self.soup.findAll('link')
        if not link_tag: return []
        css_tag = filter(lambda tag: ''.join(tag.attrs.get('rel', [])).lower() == 'stylesheet', link_tag)
        return self.get_non_empty_attributes_str_list(css_tag, 'href')


    def get_script_src_list(self):
        script_tag = self.soup.findAll('script')
        js_tag = filter(lambda tag: tag.attrs.get('type', '').lower() == 'text/javascript', script_tag)
        return self.get_non_empty_attributes_str_list(js_tag, 'src')


    def get_div_style_attributes_key_tuple_list(self, threshold=3):
        div_tag = self.soup.findAll('div')
        if not div_tag: return []
        div_attr_tuple_list = []
        for tag in div_tag:
            if not tag: continue
            item = tuple(key for key in sorted(set(tok.split(":")[0].strip() for tok in tag.attrs.get('style', '').split(";"))) if key)
            if len(item) >= threshold:
                div_attr_tuple_list.append(item)
        return div_attr_tuple_list


    # @depreciated
    #def get_img_src_list(self):
    #    return self._get_src_from_tag(RE_IMG.findall(self.page_lower))
    def get_password_input_list(self):
        return self.get_visible_input_tag_element_list(('password', ))
    def get_text_input_list(self):
        return self.get_visible_input_tag_element_list(('text', ))
    def get_submit_input_list(self):
        return self.get_visible_input_tag_element_list(('submit', ))
    def get_email_input_list(self):
        return self.get_visible_input_tag_element_list(('email', ))
    def get_image_input_list(self):
        return RE_INPUT_TAG_IMAGE_TYPE.findall(self.page_lower)
    def get_select_list(self):
        return RE_SELECT_TAG.findall(self.page_lower)
    def get_option_list(self):
        return RE_OPTION_TAG.findall(self.page_lower)
    def get_limited_visible_text_list(self):
        try:
            return self.text_from_html()
        except (TypeError, UnicodeDecodeError) as e:
            raise ExtractorError(e)
    def get_title_text_list(self):
        return self.get_lower_eng_num_text_list(text = ' '.join(self.get_title_list()))
    def get_lower_eng_num_text_list(self, text=None):
        if text is None:
            return [tok.lower().strip() for tok in RE_ENG_NUM_TEXT.findall(self.page_lower) if tok not in STOP_WORD]
        else:
            return [tok.lower().strip() for tok in RE_ENG_NUM_TEXT.findall(text)]

    def does_have_long_document_write_unescape(self, threshold=15):
        result = RE_WRITE_UNESCAPE.search(self.page_lower)
        txt = result.group(0) if result else ''
        return result is not None and txt.count('%') > threshold


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
        if element.parent.name in ('style', 'script', 'head', 'title', 'meta', '[document]', 'noscript', 'select', 'option', ):
            return False

        if isinstance(element, Comment):
            return False

        if self._is_hiden(element):
            return False

        return True
    

    def _is_hiden(self, element):
        if not element: 
            return False
        elif self.is_hiden_element(element):
            return True

        for parent in element.parents:
            if not parent: 
                return False
            elif self.is_hiden_element(parent):
                return True
    
        return False


    def is_hiden_element(self, element):
        if not isinstance(element, Tag): return False
        
        if element.name in ('style', 'script', 'head', 'title', 'meta', 'noscript', ):
            return True

        if element.name in ('body', 'html', ):
            return False

        if element.attrs.get('aria-hidden', '').lower() == 'true':
            return True

        if RE_DISPLAY_NONE.search(element.attrs.get('style', '')):
            return True

        return False


    def _is_cover_img(self, element):
        if not element: return False

        for child in element.findChildren():
            if not child: continue

            if child.name in ('img',):
                return True
    
        return False


    def text_from_html(self):
        texts = self.soup.findAll(text=True)
        visible_texts = filter(self._tag_visible, texts)  

        return [t.strip() for t in visible_texts if t.strip() and t]


    def _meta_refresh(self, element):
        if not element: return False

        if element.parent.name not in ('head', 'html', '[document]', ):
            return False

        if element.attrs.get('http-equiv', '').strip().lower() == 'refresh':
            return True

        return False
    

    def meta_refresh_tag(self):
        metas = self.soup.findAll('meta')
        return filter(self._meta_refresh, metas)


    def get_meta_refresh_url_list(self):
        meta_refreshes = self.meta_refresh_tag()

        redirect_url_list = []
        for value in [t.attrs.get('content','') for t in meta_refreshes] :
            re_value = RE_URL_FROM_META_REFRESH.search(value)
            if re_value:
                redirect_url_list.append(re_value.group(2))
            
        return redirect_url_list


    def get_non_empty_attributes_str_list(self, elements, attribute_key):
        return self.get_attributes_str_list(elements, attribute_key, does_accept_empty=False)


    def get_attributes_str_list(self, elements, attribute_key, does_accept_empty=True):
        _list = []
        for e in elements:
            if attribute_key not in e.attrs: continue
            _value = e.attrs[attribute_key].strip()
            if not does_accept_empty and not _value: continue
            _list.append(e.attrs[attribute_key])

        return _list


    def get_visible_input_tag_element_list(self, type_tuple=None, exclude_type_tuple=None):
        input_tags = self.soup.findAll('input')
        visible_input_tags = filter(self._tag_visible, input_tags)
        visible_input_tags = list(visible_input_tags)

        if type_tuple is not None:
            if not isinstance(type_tuple, tuple):
                raise ExtractorError('type_tuple should be type of tuple but %s is %s' % (type_tuple, type(type_tuple)))
            visible_input_tags = filter(lambda tag:tag.attrs.get('type', 'text') in type_tuple, visible_input_tags[:])

        if exclude_type_tuple is not None:
            if not isinstance(exclude_type_tuple, tuple):
                raise ExtractorError('exclude_type_tuple should be type of tuple but %s is %s' % (exclude_type_tuple, type(exclude_type_tuple)))
            visible_input_tags = filter(lambda tag: not tag.attrs.get('type', 'text') in exclude_type_tuple, visible_input_tags[:])

        return visible_input_tags


    def get_base_url(self, url, base_tag_only=False):
        cache_url = self.base_url_cache.get(url, '')
        if cache_url and not base_tag_only:
            return cache_url

        base_tags = self.soup.findAll('base')
        if not base_tags:
            if base_tag_only: return None
            else: 
                self.base_url_cache[url] = url
                return url

        base_tag = base_tags[0]
        base_href = base_tag.attrs.get('href', '')
        base_url = urljoin(url, base_href)

        if len(self.base_url_cache) > 100:
            self.self.base_url_cache = {}

        self.base_url_cache[url] = base_url

        return base_url


    def get_textarea_element_list(self):
        textarea_tags = self.soup.findAll('textarea')
        visible_textarea = filter(self._tag_visible, textarea_tags)
        return list(visible_textarea)


    def get_a_href_list(self):
        a_tags = self.soup.findAll('a')
        visible_a_tags = filter(self._tag_visible, a_tags)
        a_links = self.get_attributes_str_list(visible_a_tags, 'href')
        return a_links


    def get_a_href_under_img_list(self):
        a_tags = self.soup.findAll('a')
        visible_a_tags = filter(self._tag_visible, a_tags)
        a_links_including_img = filter(self._is_cover_img, visible_a_tags)
        return self.get_non_empty_attributes_str_list(a_links_including_img, 'href')


    def get_form_action_list(self):
        form_tags = self.get_form_element_list()
        action_urls = self.get_non_empty_attributes_str_list(form_tags, 'action')
        return action_urls


    def get_form_element_list(self):
        form_tags = self.soup.findAll('form')
        return form_tags


    def get_img_src_list(self, is_visible=False):
        img_tags = self.soup.findAll('img')
        if is_visible:
            img_tags = filter(self._tag_visible, img_tags)
        img_src_list = self.get_non_empty_attributes_str_list(img_tags, 'src')
        return img_src_list


    def is_xml_format(self):
        try:
            etree.fromstring(self.page_lower)
            return True
        except lxml.etree.XMLSyntaxError as e:
            return False    


    def does_have_keyword_search(self):
        return self.does_have_keyword_lower('search')


    def does_have_keyword_subscri(self):
        return self.does_have_keyword_lower('subscri')


    def does_have_keyword_lower(self, keyword):
        return keyword in self.page_lower


    def is_email_form(self):
        len_accept_input_tag = len(self.get_visible_input_tag_element_list(('email', 'text')))
        return len_accept_input_tag == 1 and 'mail' in self.page_lower

    def does_have_form_tag(self):
        is_existed = True if self.soup.findAll('form') else False
        return is_existed
    

def _get_path_structure(reduced_normalize_url):
    url = reduced_normalize_url
    return '/%s' % '/'.join(url.split('?')[0].split('/')[1:-1] + [''])


def get_path_level_len(url):
    tok = urlparse(url)
    path = tok.path.strip()
    path_tok = [tok.strip() for tok in path.split('/') if tok.strip()]
    len_path_level = len(path_tok)
    if not path.endswith('/'):
        len_path_level += -0.5
    return len_path_level
    

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


def trim_www(_str):
    previous = None
    while previous != _str:
        previous = _str
        if _str.startswith('www.'):
            _str = _str[4:]

    return _str


def is_reduced_equal(url, target, does_trim=False):
    url = _reduced_normalize_url(url).strip()
    target = _reduced_normalize_url(target).strip()

    if does_trim:
        url = url.split("?")[0].strip()
        url = trim_www(url)
        target = target.split("?")[0].strip()
        target = trim_www(target)

    return url == target


# Recognize only by URL
def is_same_icon(url, target_url, url_extractor, target_extractor):
    base_url = url_extractor.get_base_url(url)
    target_base_url = target_extractor.get_base_url(target_url)

    if does_has_scheme(base_url) ^ does_has_scheme(target_base_url): raise ExtractorAnalyzeError('base URL and target base URL should have the same format.')

    url_icon_set = set([_reduced_normalize_url(urljoin(base_url, icon_url.strip())) \
        for icon_url in url_extractor.get_shortcut_icon_list() if icon_url.strip()])
    len_url_icon_set = len(url_icon_set)

    target_icon_set = set([_reduced_normalize_url(urljoin(target_base_url, icon_url.strip())) \
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


def get_similarity_by_div_style(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url_extractor.get_base_url(url), target_extractor.get_base_url(target_url), url_extractor.get_div_style_attributes_key_tuple_list, target_extractor.get_div_style_attributes_key_tuple_list, compare_target=COMPARE_TARGET_FULL)


def get_similarity_by_stylesheet(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url_extractor.get_base_url(url), target_extractor.get_base_url(target_url), url_extractor.get_stylesheet_href_list, target_extractor.get_stylesheet_href_list, compare_target=COMPARE_TARGET_PATH_NO_QUERY)


def get_similarity_by_script(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url_extractor.get_base_url(url), target_extractor.get_base_url(target_url), url_extractor.get_script_src_list, target_extractor.get_script_src_list, compare_target=COMPARE_TARGET_PATH_NO_QUERY)


def get_similarity_by_title_text(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url_extractor.get_base_url(url), target_extractor.get_base_url(target_url), url_extractor.get_title_text_list, target_extractor.get_title_text_list)


def get_similarity_by_img(url, target_url, url_extractor, target_extractor):
    return _get_similarity_by_extract_function(url_extractor.get_base_url(url), target_extractor.get_base_url(target_url), url_extractor.get_img_src_list, target_extractor.get_img_src_list, compare_target=COMPARE_TARGET_NO_FILENAME)


def _get_similarity_by_extract_function(base_url, target_base_url, url_extract_function, target_extract_function, compare_target=COMPARE_TARGET_FULL):
    if does_has_scheme(base_url) ^ does_has_scheme(target_base_url): raise ExtractorAnalyzeError('base URL and target base URL should have the same format.')

    if compare_target == COMPARE_TARGET_FULL:
        url_extract_collection = [extract_item for extract_item in url_extract_function()]
        target_extract_collection = [extract_item for extract_item in target_extract_function()]
    elif compare_target == COMPARE_TARGET_NO_FILENAME:
        url_extract_collection = set(['/'.join(_reduced_normalize_url(urljoin(base_url, extract_url)).split('/')[:-1]) for extract_url in url_extract_function()])
        target_extract_collection = set(['/'.join(_reduced_normalize_url(urljoin(target_base_url, extract_url)).split('/')[:-1]) for extract_url in target_extract_function()])
    elif compare_target == COMPARE_TARGET_FILENAME:
        url_extract_collection = set([extract_url.split('/')[-1].split('?')[0] for extract_url in url_extract_function()])
        target_extract_collection = set([extract_url.split('/')[-1].split('?')[0] for extract_url in target_extract_function()])
    elif compare_target == COMPARE_TARGET_PATH_NO_QUERY:
        url_extract_collection = set([_get_path_structure(_reduced_normalize_url(urljoin(base_url, extract_url))) for extract_url in url_extract_function()])
        target_extract_collection = set([_get_path_structure(_reduced_normalize_url(urljoin(target_base_url, extract_url))) for extract_url in target_extract_function()])
    else:
        raise ExtractorError('invalid compare target %s for target_url: %s' % (compare_taret, target_url))

    return get_similarity(url_extract_collection, target_extract_collection)


def get_similarity(url_extract_collection, target_extract_collection):
    len_url_extract_collection = len(url_extract_collection)
    len_target_extract_collection = len(target_extract_collection)
    
    common_count = _common_item_count(url_extract_collection, target_extract_collection)

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


def is_single_signin_form(extractor):
    len_submit_input = len(extractor.get_submit_input_list())
    len_text_input = len(extractor.get_text_input_list())
    len_image_input = len(extractor.get_image_input_list())
    if len_text_input == 1 and (len_submit_input == 1 or len_image_input == 1):
        return True

    return False


# data source: http://data.iana.org/TLD/tlds-alpha-by-domain.txt
def parse_top_level_domain(file_path):
    tld_list = []
    try:
        with open (file_path, 'r') as data:
            for line in data:
                line = line.strip().lower()
                if not line: continue
                if line.startswith('#'): continue
                tld_list.append(line)
    except IOError as e:
        raise ExtractorError('Failed to read file of top level domain list. %s' % e)

    return tld_list


if __name__ == '__main__':
    import sys
    #'''
    with open(sys.argv[1],'r') as data:
        extractor = Extractor(data.read())
    #'''
    '''
    with open(sys.argv[2],'r') as data:
        t_ext = Extractor(data.read())
    #'''
    #print get_similarity_by_img('http://google.com/','http://google.com', extractor, t_ext)
    #print is_same_icon('http://www.telecomsource.net:80/showthread.php?3121-What-is-reference-signals-in-LTE','http://www.telecomsource.net/',extractor,t_ext)
    #print extractor.get_href_list()
    #print extractor.get_title_list(True)
    #print extractor.get_shortcut_icon_list()
    #print extractor.get_stylesheet_href_list()
    #print extractor.get_script_src_list()
    #print extractor.get_img_src_list()
    #print extractor.get_password_input_list()
    #print extractor.get_limited_visible_text_list()
    #print is_potential_creditcard_form(extractor)
    #print extractor.get_meta_refresh_url_list()
    #print extractor.get_a_href_list()
    #print extractor.get_form_action_list()
    #print extractor.get_a_href_under_img_list()
    #print extractor.get_img_src_list()
    #print extractor.get_textarea_element_list()
    #print extractor.get_visible_input_tag_element_list(('text', 'image','hidden'), ('hidden', ))
    #print extractor.get_base_url('http://normal.spider-test.com/')
    #print extractor.is_email_form()
    #print extractor.does_have_keyword_search()
    #print extractor.does_have_long_document_write_unescape()
    print extractor.get_div_style_attributes_key_tuple_list()

    

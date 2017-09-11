import lxml
import re

RE_A_TAG_HREF = re.compile('<\s*a\s+[^>]*\s+href=[\'"]([^\'"]*)[\'"]')
RE_HREF = re.compile('<\s*[^>]+\s+href=[\'"]([^\'"]*)[\'"]')
RE_TITLE_TAG = re.compile('<\s*title\s*>([^<>]*)<\s*/\s*title\s*>')
RE_SHORTCUT_ICON = re.compile('<\s*link\s+[^>]*rel\s*=\s*[\'"]shortcut icon[\'"][^>]*>')
RE_STYLESHEET = re.compile('<\s*link\s+[^>]*rel\s*=\s*[\'"]stylesheet[\'"][^>]*>')
RE_INPUT_TAG_PASSWORD_TYPE = re.compile('<\s*input\s+[^>]*type\s*=\s*[\'"]password[\'"][^>]*>')

class ExtractorError(Exception): pass

class Extractor(object):
    def __init__(self, page):
        self.page = page.replace('\n', '')

    def get_a_href_list(self):
        return RE_A_TAG_HREF.findall(self.page)
    def get_href_list(self):
        return RE_HREF.findall(self.page)
    def get_title_list(self):
        return RE_TITLE_TAG.findall(self.page)
    def get_shortcut_icon_list(self):
        return self._get_href_from_tag(RE_SHORTCUT_ICON.findall(self.page))
    def get_stylesheet_list(self):
        return self._get_href_from_tag(RE_STYLESHEET.findall(self.page))
    def get_password_input_list(self):
        return RE_INPUT_TAG_PASSWORD_TYPE.findall(self.page)

    def _get_href_from_tag(self, tags):
        _set = set()
        for tag in tags:
           for href in RE_HREF.findall(tag):
                if href.strip(): _set.add(href)
        return list(_set) 

if __name__ == '__main__':
    import sys
    with open(sys.argv[1],'r') as data:
        extractor = Extractor(data.read())

    #print extractor.get_a_href_list()
    #print extractor.get_href_list()
    #print extractor.get_title_list()
    #print extractor.get_shortcut_icon_list()
    print extractor.get_stylesheet_list()
    print extractor.get_password_input_list()

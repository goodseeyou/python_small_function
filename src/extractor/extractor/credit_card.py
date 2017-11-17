import sys
import re

''' visible input label filter set'''
VSINPUT_RE_PROG = re.compile('''(<input[^>]+type=['"](?!hidden)[^>"']+['"][^>]+>)''')
''' select sections for expiring date '''
SELECT_RE_PROG = re.compile('''<select[^>]+>''')


DOM_PARSE_ATTRS_RE_PROG = re.compile('''([\w]+[ ]*=[ ]*["'][^"']+["'])''')
DOM_PARSE_LABEL_RE_PROG = re.compile('''<\W*(\w+)\W''')

class DomError(Exception):
    pass

class Dom(object):

    def __init__(self,inst, label=None):
        self._parse_string(inst)
        self.label = label if label else self._get_label(inst)
        self.attrs.update({'label':self.label})

    def _get_label(self,inst):
        try:
            return DOM_PARSE_LABEL_RE_PROG.search(inst).group(1)
        except (re.error, TypeError, AttributeError) as e:
            raise DomError(e)

    def _parse_string(self,inst):
        self.attrs = {}
        for kv in DOM_PARSE_ATTRS_RE_PROG.findall(inst):
            toks = [t.strip() for t in kv.split('=')]
            ks = toks[0].split(' ')
            k = ks[-1]
            if len(ks) > 1:
                for singlek in ks[0:-1]:
                    if not singlek: continue
                    self.attrs[singlek] = ''
            v = '='.join(toks[1:])
            self.attrs[k] = v.strip('"\'').strip()

    def _get(self,key,default):
        if key in self.attrs:
            return self.attrs[key]
        else:
            return default

    def show_attrs(self):
        return dict(self.attrs)

    def toString(self):
        return str(self.attrs)

def _is_4_continuous_vsinput_with_maxlength_return_dict_list(dom_list):
    return_list = []
    continuous_count = 0
    maxlength_list = [0,0,0,0]
    type_list = ['','','','']
    size_list = [0,0,0,0]

    #window_size = 4
    window_index = 0
    

    for dom in dom_list:
        type = dom._get('type','')
        if type not in ['password', 'text']:
            continuous_count = 0
            continue
        try:
            maxl = int(dom._get('maxlength',0))
            size = int(dom._get('size',0))
        except TypeError:
            maxl = 0
            size = 0
            maxlength_list = [0,0,0,0]
            size_list = [0,0,0,0]
            pass
        
        type_list[window_index] = type
        maxlength_list[window_index] = maxl    
        size_list[window_index] = size

        window_index += 1
        window_index %= 4
        continuous_count += 1

        if continuous_count >= 4:
            continuous_count -= 1
            #check()
            if (type_list[window_index] != 'text' or type_list[(window_index + 3)%4] != 'text') \
                and (type_list[(window_index +1)%4] != 'password' or type_list[(window_index +2)%4] != 'password'):
                continue
            r_type_list = ['','','','']
            r_maxlength_list = [0,0,0,0]
            r_size_list = [0,0,0,0]
            for index in xrange(4):
                slide_index = (window_index + index) % 4
                r_type_list[index] = type_list[slide_index]
                r_maxlength_list[index] = maxlength_list[slide_index]
                r_size_list[index] = size_list[slide_index]
            return_list.append({'type_list':r_type_list, 'maxlength_list':r_maxlength_list, 'size_list':r_size_list})

    return return_list
    
def _is_cardnumber_security_code_format_return_tuple_dict_list(dom_list):
    set_list = []
    long_input_index = []
    short_input_index = []
    distance = 0
    for i, dom in enumerate(dom_list):
        if dom._get('autocomplete','').lower() != 'off':
            continue
        try:
            size = int(dom._get('size',0))
            maxlength = int(dom._get('maxlength',0))
        except TypeError:
            continue
        if 16 <= size <= 20 or 16 <= maxlength <= 20:
            long_input_index.append(i)
        if 3 <= size <= 4 or 3 <= maxlength <= 4:
            short_input_index.append(i)

    li = 0
    si = 0
    len_li = len(long_input_index)
    len_si = len(short_input_index)
    hold_si = 0
    while li < len_li and len_si and len_li:
        if long_input_index[li] > short_input_index[si]:
            si += 1
            if si >= len_si:
                break
            continue
        if long_input_index[li] +4 < short_input_index[si] :
            li += 1
            si = hold_si
            continue
        if long_input_index[li] - short_input_index[si] <= 3:
            set_list.append((dom_list[long_input_index[li]],dom_list[short_input_index[si]]))
            if long_input_index[li] > short_input_index[hold_si] :
                hold_si = si 
            if si < len_si -1:
                si += 1
            else:
                li += 1
            continue

    return  set_list

def _is_aquire_creditcard(dom_list):
    check_keyword_dict = {'credit':False,'card':False}
    for dom in dom_list:
        if dom._get('label','') != 'input' or dom._get('type','') != 'text' or 'readonly' in dom.show_attrs():
            continue
        name = dom._get('name','').lower()
        id = dom._get('id','').lower()
        for key in check_keyword_dict:
            if key in name or key in id:
                check_keyword_dict[key] = True

    all_key_matched = True
    for key in check_keyword_dict:
         all_key_matched &= check_keyword_dict[key]

    return all_key_matched

def _is_exist_expiring_date_format(dom_list):
    check_select_keyword_dict = {'month':False,'year':False}
    check_text_keyword_dict = {'date':False}

    for dom in dom_list:
        if dom._get('label','') == 'select':
            name = dom._get('name','').lower()
            id = dom._get('id','').lower()
            for key in check_select_keyword_dict:
                if key in name or key in id:
                    check_select_keyword_dict[key] = True
            continue

        if dom._get('label','') == 'input' and dom._get('type','') == 'text':
            name = dom._get('name','').lower()
            id = dom._get('id','').lower()
            for key in check_text_keyword_dict:
                if key in name or key in id:
                    check_text_keyword_dict[key] = True
            continue

    date_format_in_select = True
    date_format_in_text = True
    for key in check_select_keyword_dict:
        date_format_in_select &= check_select_keyword_dict[key]
    for key in check_text_keyword_dict:
        date_format_in_text &= check_text_keyword_dict[key]

    return date_format_in_select | date_format_in_text
                

def _filter_by_dom_info(dom_list):
    if not _is_exist_expiring_date_format(dom_list):
        return None

    continuous_vsinputs = _is_4_continuous_vsinput_with_maxlength_return_dict_list(dom_list)
    for cv in continuous_vsinputs:
        pass_rules = False

        is_all_eqaul = True
        for i in xrange(len(cv['maxlength_list']) - 1):
            if cv['maxlength_list'][i] != cv['maxlength_list'][i+1]:
                is_all_eqaul = False
                break
        if is_all_eqaul and cv['maxlength_list'][0] == 4:
            return '4 continuous vsinputs with equal maxlength'

        is_all_equal = True
        for i in xrange(len(cv['size_list']) - 1):
            if cv['size_list'][i] != cv['size_list'][i+1]:
                is_all_equal = False
                break
        if is_all_equal and 0 < cv['size_list'][0] == 4:
            return '4 continuous vsinputs with equal size'

    if _is_cardnumber_security_code_format_return_tuple_dict_list(dom_list):
        return 'long text with short text in acceptable distance'

    if _is_aquire_creditcard(dom_list):
        return 'require creditcard input form'

    return None

#def is_creditcard_form(page_content_string):
def is_creditcard_form(filepath):
    f = open(filepath)
    page_content_string = f.read()
    f.close()
    r = VSINPUT_RE_PROG.findall(page_content_string)
    r += SELECT_RE_PROG.findall(page_content_string)

    dom_list = []
    if r:
        for i in r:
            dom = Dom(i)
            if dom:
                dom_list.append(dom)

    reason = _filter_by_dom_info(dom_list)
    return reason

if __name__ == '__main__':
    import sys
    print is_creditcard_form(sys.argv[1])

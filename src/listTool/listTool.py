'''
Select kth value number from list in order of (n) time complexity.
However, comparing to sorted list and select kth value (order of nlogn), sorting by build-in function is faster.
'''
import sys

NUMBER_OF_ELEMENT_IN_COLUMN = 7


def select_the_kth_small_element(_list, k):
    len_list = len(_list)
    if k > len_list:
        raise ValueError("parameter k %s have greater then size of list %s", k, len_list)

    if len_list <= NUMBER_OF_ELEMENT_IN_COLUMN:
        return sorted(_list)[k-1]

    l = _list[:]
    number_of_padding = len(l) % NUMBER_OF_ELEMENT_IN_COLUMN
    l += [sys.maxint] * number_of_padding

    median_list = []
    for i in [ii*NUMBER_OF_ELEMENT_IN_COLUMN for ii in range(len(l)/NUMBER_OF_ELEMENT_IN_COLUMN)]:
        column = l[i:i+NUMBER_OF_ELEMENT_IN_COLUMN]
        column.sort()
        i += NUMBER_OF_ELEMENT_IN_COLUMN

        median = column[NUMBER_OF_ELEMENT_IN_COLUMN / 2]
        median_list.append(median)

    median_of_median = select_the_kth_small_element(median_list, len(median_list) / 2)
    smaller, equal, bigger = [], [], []
    for element in l:
        if element < median_of_median:
            smaller.append(element)
        elif element == median_of_median:
            equal.append(element)
        elif element > median_of_median:
            bigger.append(element)
        else:
            raise ValueError("Impossible %s ? %s", element, median_of_median)

    len_smaller, len_equal, len_bigger = len(smaller), len(equal), len(bigger)
    if k <= len_smaller:
        return select_the_kth_small_element(smaller, k)
    elif k <= len_smaller + len_equal:
        return select_the_kth_small_element(equal, k - len_smaller) 
    else:
        return select_the_kth_small_element(bigger, k - len_smaller - len_equal)  


if __name__ == '__main__':
    import json
    import time
    import random
    k = int(sys.argv[1])
    l = [random.randint(0,100000) for i in range(int(sys.argv[2]))][::-1]
    '''
    l = json.loads(sys.argv[2])
    print l
    #'''
    b = time.time()
    print select_the_kth_small_element(l, k)
    e = time.time()
    print '%.3lf' % (e - b)
    
    b = time.time()
    l.sort()
    print l[k-1]
    e = time.time()
    print '%.3lf' % (e - b)


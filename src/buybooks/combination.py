import itertools

items = {
    '地表最強國文課本 1':288,
    '地表最強國文課本 2':277,
    '你的人生難關，三國都發生過':277,
    '史記的讀法：司馬遷的歷史世界':395,
    'OSSO～歐美近代史原來很有事':253,
    '文明衝突與世界秩序的重建':300,
    '流暢的 python':882,
    '順流致富 gps':199,
    '領域驅動設計：軟體核心複雜度的解決方法':612,
    '打不破的玻璃芯：穿越逆境的20個面對':324,
    '木製防潑水螢幕增高收納架淺木色':279,
    '靜音滑鼠藍色':569,
    '彼得原理': 269,
    '教練': 332,
    '我的老闆是總統': 300,
}

choosen = ('木製防潑水螢幕增高收納架淺木色', '靜音滑鼠藍色')
exclude = ('木製防潑水螢幕增高收納架淺木色', '靜音滑鼠藍色', '史記的讀法：司馬遷的歷史世界', 'OSSO～歐美近代史原來很有事', '流暢的 python')

candidates = set(item for item in items.keys() if item not in choosen and item not in exclude)
result = []
threshold = 2000.0/0.88+100 
for i in range(len(candidates)+1):
    item_combination = itertools.combinations(candidates ,i)
    for item_set in item_combination:
        sum_item_set = sum(items[item] for item in item_set) + sum(items[item] for item in choosen)
        if sum_item_set > threshold and sum_item_set < 2* threshold:
            result.append((sum_item_set, choosen, item_set))

result.sort(key=lambda x:x[0])
print('\n'.join([str(tok) for tok in result]))

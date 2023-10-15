from datetime import datetime, timedelta

base = 'https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{}.zip'

now_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

import sys

for i in range(int(sys.argv[1])):
    date_str = (now_date - timedelta(days=i)).strftime("%Y_%m_%d")
    print(base.format(date_str))


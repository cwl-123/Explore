# -*- coding: utf-8 -*-
import json, os
BASE = '/Users/chenweilong/Explore/etf-012538-analysis'
data = json.load(open(f'{BASE}/data/page_data.json'))
tpl = open(f'{BASE}/template.html', encoding='utf-8').read()
html = tpl.replace('__DATA__', json.dumps(data, ensure_ascii=False))
open(f'{BASE}/index.html','w',encoding='utf-8').write(html)
print('written', os.path.getsize(f'{BASE}/index.html'), 'bytes')

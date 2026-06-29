import json, os, sys

code = sys.argv[1]
name = sys.argv[2]
url = sys.argv[3]

with open('data/wiki_sets.json') as f:
    ws = json.load(f)

ws[code] = {'set_name': name, 'set_url': url, 'scraped': False}

with open('data/wiki_sets.json', 'w') as f:
    json.dump(ws, f, ensure_ascii=False, indent=2)

print(f'Added {code} to wiki_sets.json')

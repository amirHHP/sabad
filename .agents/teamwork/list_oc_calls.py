import urllib.request
import re

url = 'https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js'
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')
calls = re.findall(r'oC\.(?:get|post|delete|put)\([\"\'`]([^\"\'`]+)[\"\'`]', js)
print('Total oC calls:', len(calls))
for c in sorted(list(set(calls))):
    print(' ', c)

# also search for templates with backticks like oC.get(`${...}`)
dynamic_calls = re.findall(r'oC\.(?:get|post|delete|put)\(`([^`]+)`', js)
print('\nDynamic calls with backticks:')
for d in sorted(list(set(dynamic_calls))):
    print(' ', d)

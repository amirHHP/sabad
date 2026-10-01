import urllib.request
import re

url = 'https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js'
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')

print('--- mC (GET) calls ---')
for m in set(re.findall(r'mC\([\"\'`]([^\"\'`]+)[\"\'`]', js)):
    print(' ', m)

print('\n--- pC (POST) calls ---')
for m in set(re.findall(r'pC\([\"\'`]([^\"\'`]+)[\"\'`]', js)):
    print(' ', m)

# Also check dynamic calls
print('\n--- Dynamic mC calls ---')
for m in set(re.findall(r'mC\(`([^`]+)`', js)):
    print(' ', m)

print('\n--- Dynamic pC calls ---')
for m in set(re.findall(r'pC\(`([^`]+)`', js)):
    print(' ', m)

import urllib.request
import re

url = 'https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js'
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')

endpoints = set(re.findall(r'["\'`](/(?:search|home|v[0-9]|navigation|category|categories|stores?|products?)[a-zA-Z0-9_\-/]*)["\'`]', js))
print(f"Total catalog endpoints found: {len(endpoints)}")
for ep in sorted(list(endpoints)):
    print(" ", ep)

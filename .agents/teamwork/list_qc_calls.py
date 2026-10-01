import urllib.request
import re

url = 'https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js'
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')

matches = set(re.findall(r'qC\([\"\'`](/[^\"\'`]+)[\"\'`]', js))
print(f"Total literal qC endpoints: {len(matches)}")
for m in sorted(list(matches)):
    print(" ", m)

# Dynamic qC calls
dyn = set(re.findall(r'qC\(`([^`]+)`', js))
print(f"\nTotal dynamic qC endpoints: {len(dyn)}")
for d in sorted(list(dyn)):
    print(" ", d)

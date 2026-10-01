import urllib.request
import re

content = urllib.request.urlopen(urllib.request.Request('https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js', headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')
idx = content.find('has_discount')
snippet = content[max(0, idx-1500):min(len(content), idx+2500)]
paths = re.findall(r'["\'`](/[a-zA-Z0-9_\-/]+)["\'`]', snippet)
print("Paths near search params:")
for p in set(paths):
    print(" ", p)

# Also search for fetch or axios or get( or post(
calls = re.findall(r'(?:get|post|request)\([\"\'`]([^\"\'`]+)[\"\'`]', snippet)
print("Calls near search params:")
for c in calls:
    print(" ", c)

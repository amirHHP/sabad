import urllib.request
import re

html = urllib.request.urlopen(urllib.request.Request('https://www.digikalajet.com', headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})).read().decode('utf-8')
scripts = re.findall(r'src=[\"\'](/assets/[^\"\']+\.js)[\"\']', html)

all_endpoints = set()
for s in scripts:
    url = f"https://www.digikalajet.com{s}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
        js = urllib.request.urlopen(req, timeout=5).read().decode('utf-8', errors='ignore')
        matches = re.findall(r'["\'](/(?:v[0-9]|api|user|cart|search|product|jet)/[a-zA-Z0-9_\-/]+)["\']', js)
        for m in matches:
            all_endpoints.add(m)
    except Exception:
        pass

print(f"Discovered {len(all_endpoints)} endpoints across {len(scripts)} scripts:")
for ep in sorted(list(all_endpoints)):
    print(" ", ep)

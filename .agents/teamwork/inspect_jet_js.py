import urllib.request
import re

urls = [
    "https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js",
    "https://www.digikalajet.com/assets/x-lazy-dynamic-amazing.BWTJ4_TS.js",
    "https://www.digikalajet.com/assets/x-lazy-shop.Br4k63dn.js",
]

for url in urls:
    print(f"\n=== Inspecting {url} ===")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
    content = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    apis = set(re.findall(r'["\'](/(?:api/|v[0-9]/)[a-zA-Z0-9_\-/]+)["\']', content))
    print(f"APIs ({len(apis)}):")
    for a in sorted(list(apis))[:25]:
        print("  ", a)
    hosts = set(re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-z]+', content))
    print("Hosts:", hosts)

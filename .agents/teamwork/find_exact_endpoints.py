import urllib.request
import re
import json

url = "https://static.snapp.express/ren-assests/0cc5f2cb/js/main-4.a52568d54c6a5562.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
content = urllib.request.urlopen(req).read().decode('utf-8')

# Search for patterns like `url:"/..."` or `endpoint` or `baseURL`
matches = set(re.findall(r'["\'](/[a-zA-Z0-9_\-./]+(?:search|product|vendor|cart|auth|promotion|deal|category|banner)[a-zA-Z0-9_\-./]*)["\']', content))
print(f"Total matching paths in main-4: {len(matches)}")
for m in sorted(list(matches))[:40]:
    print(" ", m)

# Look for baseUrl or api config
configs = re.findall(r'(?:baseURL|BASE_URL|baseUrl|apiHost|apiBase|gatewayHost)[^,;}\)]+', content)
print("\nConfigs:")
for c in configs[:10]:
    print(" ", c)

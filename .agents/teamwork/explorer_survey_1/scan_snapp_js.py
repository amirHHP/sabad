import urllib.request
import re

bundles = [
    "https://static.snapp.express/ren-assests/0cc5f2cb/js/runtime.8d2c2bd16c749d67.js",
    "https://static.snapp.express/ren-assests/0cc5f2cb/js/main-0.cb11d120131266d9.js",
    "https://static.snapp.express/ren-assests/0cc5f2cb/js/main-2.bfa0ba36e67fb441.js",
    "https://static.snapp.express/ren-assests/0cc5f2cb/js/main-3.15838023723fda5b.js",
    "https://static.snapp.express/ren-assests/0cc5f2cb/js/main-4.a52568d54c6a5562.js",
    "https://static.snapp.express/ren-assests/0cc5f2cb/js/main-5.5a2828627ca8f162.js",
]

for url in bundles:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        content = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
        name = url.split("/")[-1]
        print(f"=== {name} (size: {len(content)}) ===")
        # search for svc.snapp or api paths
        domains = set(re.findall(r"https?://[a-zA-Z0-9.-]*snapp[a-zA-Z0-9.-]*\.[a-z]+", content))
        if domains:
            print("  Domains:", domains)
        api_paths = set(re.findall(r"[\"'](/[a-zA-Z0-9_/-]*(?:api|v1|v2|v3|product|vendor|cart|auth|promotion|search|deal)[a-zA-Z0-9_/-]*)[\"']", content))
        if api_paths:
            print(f"  Found {len(api_paths)} API paths. Sample:")
            for p in sorted(list(api_paths))[:15]:
                print(f"    {p}")
    except Exception as e:
        print(f"Error {url}: {e}")

import urllib.request
import re

scripts = [
    "https://www.digikalajet.com/assets/x-d-chunk-2.BZHIOJzm.js",
    "https://www.digikalajet.com/assets/x-d-chunk-1.BJ-loFRu.js",
    "https://www.digikalajet.com/assets/x-d-chunk-final.DwjqPQ3c.js",
    "https://www.digikalajet.com/assets/x-lazy-shop.Br4k63dn.js",
    "https://www.digikalajet.com/assets/x-lazy-dynamic-amazing.BWTJ4_TS.js"
]

for s in scripts:
    print(f"\n--- Checking {s.split('/')[-1]} ---")
    try:
        content = urllib.request.urlopen(urllib.request.Request(s, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8', errors='ignore')
        # find references to endpoints
        matches = set(re.findall(r'["\'](/(?:v1|v2|api|user|cart|search|stores?|products?|categories?)[a-zA-Z0-9_\-/]*)["\']', content))
        print("Endpoints found:", len(matches))
        for m in sorted(list(matches))[:15]:
            print("  ", m)
        # find occurrences of query params or keywords
        jet_mentions = set(re.findall(r'[a-zA-Z0-9_\-/]*(?:jet|store|basket|cart|amazing)[a-zA-Z0-9_\-/]*', content))
        interesting = [j for j in jet_mentions if len(j) > 4 and ('api' in j or 'cart' in j or 'search' in j)]
        print("Interesting identifiers:", interesting[:10])
    except Exception as e:
        print("Error:", e)

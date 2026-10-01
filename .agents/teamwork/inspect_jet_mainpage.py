import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
lat = 35.715298
lng = 51.404343
url = f"https://api.digikalajet.ir/v3/main-page/?latitude={lat}&longitude={lng}"
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Origin': 'https://www.digikalajet.com',
    'Referer': 'https://www.digikalajet.com/',
    'Client': 'Pwa',
    'ClientOs': 'web',
    'platform-sso-disable-prod': '1',
})

resp = urllib.request.urlopen(req, timeout=10, context=ctx)
data = json.loads(resp.read().decode('utf-8'))
components = data['data']['components']

print(f"Total components: {len(components)}")
for i, c in enumerate(components):
    ctype = c.get('component_type')
    cdata = c.get('data')
    title = None
    if isinstance(cdata, dict):
        title = cdata.get('title') or cdata.get('header', {}).get('title')
    print(f"[{i}] {ctype}: {title}")
    if 'amazing' in str(ctype).lower() or 'deal' in str(ctype).lower() or 'product' in str(ctype).lower() or 'shop' in str(ctype).lower():
        print(f"    Sample: {json.dumps(c, ensure_ascii=False)[:300]}")

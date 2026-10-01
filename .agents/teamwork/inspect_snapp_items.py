import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
lat = 35.715298
lng = 51.404343
q = urllib.parse.quote("شیر")
url = f"https://svc.snapp.market/mobile/v3/search?query={q}&lat={lat}&lng={lng}"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://snapp.market",
    "Referer": "https://snapp.market/",
}

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    print("Top data keys:", list(data['data'].keys()))
    if 'product' in data['data']:
        products = data['data']['product']
        print(f"Products type: {type(products)}, keys: {list(products.keys()) if isinstance(products, dict) else len(products)}")
        items = products.get('items', []) if isinstance(products, dict) else products
        print(f"Total product items: {len(items)}")
        for it in items[:5]:
            print(f"- Title: {it.get('title')}, Price: {it.get('price')}, Discount: {it.get('discount')}, Vendor: {it.get('vendor_title') or it.get('vendor_id')}")

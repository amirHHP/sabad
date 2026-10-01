import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
lat = 35.715298
lng = 51.404343

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Origin": "https://snapp.market",
    "Referer": "https://snapp.market/",
}

def test(url):
    print(f"\nGET {url}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            print("Status:", resp.status)
            data = json.loads(resp.read().decode('utf-8'))
            print("Keys:", list(data.keys()))
            print("Sample:", json.dumps(data, ensure_ascii=False)[:400])
    except Exception as e:
        print("Failed:", e)

# Test vendors list
test(f"https://svc.snapp.market/express-vendor/general/vendors-list?lat={lat}&lng={lng}")

# Test mobile search
q = urllib.parse.quote("شیر")
test(f"https://svc.snapp.market/mobile/v3/search?query={q}&lat={lat}&lng={lng}")
test(f"https://svc.snapp.market/mobile/v3/product-vendors/search?query={q}&lat={lat}&lng={lng}")
test(f"https://svc.snapp.market/express-search/v1/pb/products?query={q}&lat={lat}&lng={lng}")

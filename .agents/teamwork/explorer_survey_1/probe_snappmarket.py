import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Origin": "https://snapp.market",
    "Referer": "https://snapp.market/",
}

lat = 35.715298
lng = 51.404343

urls_to_test = [
    # snapp.market base paths
    f"https://snapp.market/api/v1/promotions/flash-deals?lat={lat}&lng={lng}",
    f"https://snapp.market/api/v1/search/products?query=%D8%B4%DB%8C%D8%B1&lat={lat}&lng={lng}",
    f"https://snapp.market/api/v1/vendors?lat={lat}&lng={lng}",
    f"https://snapp.market/api/v2/vendors?lat={lat}&lng={lng}",
    f"https://snapp.market/api/v1/cart",
    # api.snapp.market
    f"https://api.snapp.market/api/v1/promotions/flash-deals?lat={lat}&lng={lng}",
    f"https://api.snapp.market/api/v1/search/products?query=%D8%B4%DB%8C%D8%B1&lat={lat}&lng={lng}",
]

for url in urls_to_test:
    print(f"\nProbing: {url}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type")
            body = resp.read()
            print(f"Status: {status}, Content-Type: {content_type}, Length: {len(body)}")
            try:
                data = json.loads(body.decode("utf-8"))
                if isinstance(data, dict):
                    print("Keys:", list(data.keys())[:10])
                    # Print a small sample snippet
                    snippet = json.dumps(data, ensure_ascii=False)[:300]
                    print("Sample:", snippet)
                elif isinstance(data, list):
                    print("List len:", len(data))
                    print("Sample item:", json.dumps(data[0] if data else {}, ensure_ascii=False)[:300])
            except Exception as e:
                print("Body (not json):", body[:200])
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        try:
            err_body = e.read().decode('utf-8')
            print(f"Error body: {err_body[:300]}")
        except Exception:
            pass
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")

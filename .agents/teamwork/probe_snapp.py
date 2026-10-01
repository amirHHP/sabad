import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
lat = 35.715298
lng = 51.404343

def probe(url, headers=None, method="GET", data=None):
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fa,en;q=0.9",
        "Origin": "https://snapp.market",
        "Referer": "https://snapp.market/",
    }
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers, method=method, data=data)
    print(f"\n--- {method} {url} ---")
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            print(f"Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
            body = resp.read().decode('utf-8', errors='ignore')
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    print("JSON keys:", list(parsed.keys()))
                    # print top level preview
                    for k in list(parsed.keys())[:3]:
                        val = str(parsed[k])[:100]
                        print(f"  {k}: {val}")
                elif isinstance(parsed, list):
                    print(f"JSON list len: {len(parsed)}")
                    if parsed:
                        print("  [0]:", str(parsed[0])[:150])
            except Exception:
                print("Raw (first 250 chars):", body[:250])
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        try:
            err = e.read().decode('utf-8', errors='ignore')
            print("Error body:", err[:300])
        except Exception:
            pass
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

query = urllib.parse.quote("شیر")

# SnappMarket search tests on svc.snapp.market
probe(f"https://svc.snapp.market/express-search/products?query={query}&lat={lat}&lng={lng}")
probe(f"https://svc.snapp.market/api/v1/search/products?query={query}&lat={lat}&lng={lng}")
probe(f"https://svc.snapp.market/search/v1/products?query={query}&lat={lat}&lng={lng}")
probe(f"https://svc.snapp.market/express-home/mobile/v3/user/new-home?lat={lat}&lng={lng}")
probe(f"https://svc.snapp.market/belladonna/api/v1/promotions/flash-deals?lat={lat}&lng={lng}")
probe(f"https://svc.snapp.market/promotions/v1/flash-deals?lat={lat}&lng={lng}")

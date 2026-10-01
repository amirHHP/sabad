import urllib.request
import urllib.error
import ssl
import json

ctx = ssl.create_default_context()
lat = 35.715298
lng = 51.404343

def probe(url, headers=None, method="GET", data=None):
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fa,en;q=0.9",
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
                    print("Sample:", json.dumps(parsed, ensure_ascii=False)[:350])
                elif isinstance(parsed, list):
                    print(f"JSON list len: {len(parsed)}")
                    print("Sample item:", json.dumps(parsed[0] if parsed else {}, ensure_ascii=False)[:350])
            except Exception:
                print("Raw response (first 250 chars):", body[:250])
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        try:
            err = e.read().decode('utf-8', errors='ignore')
            print("Error body:", err[:300])
        except Exception:
            pass
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

# 1. Snapp Market (svc.snapp.market)
probe(f"https://svc.snapp.market/express-home/mobile/v3/user/new-home?lat={lat}&lng={lng}", headers={"Origin": "https://snapp.market", "Referer": "https://snapp.market/"})
probe(f"https://svc.snapp.market/express-search/categories?lat={lat}&lng={lng}", headers={"Origin": "https://snapp.market", "Referer": "https://snapp.market/"})
probe(f"https://svc.snapp.market/api/v1/search/products?query=شیر&lat={lat}&lng={lng}", headers={"Origin": "https://snapp.market", "Referer": "https://snapp.market/"})

# 2. Digikala Jet (api.digikalajet.ir & api.digikala.com)
probe(f"https://api.digikalajet.ir/v1/navigation/?lat={lat}&lng={lng}", headers={"Origin": "https://digikalajet.com", "Referer": "https://digikalajet.com/"})
probe(f"https://api.digikala.com/v1/jet/home/?lat={lat}&lng={lng}", headers={"Origin": "https://digikalajet.com", "Referer": "https://digikalajet.com/"})
probe(f"https://api.digikalajet.ir/v1/search/?q=شیر&lat={lat}&lng={lng}", headers={"Origin": "https://digikalajet.com", "Referer": "https://digikalajet.com/"})

# 3. Okala (api.okala.com & okala.com)
probe(f"https://api.okala.com/v1/home?lat={lat}&lng={lng}", headers={"Origin": "https://okala.com", "Referer": "https://okala.com/"})
probe(f"https://api.okala.com/v1/products/search?q=شیر&latitude={lat}&longitude={lng}", headers={"Origin": "https://okala.com", "Referer": "https://okala.com/"})
probe(f"https://okala.com/api/v1/promotions", headers={"Origin": "https://okala.com", "Referer": "https://okala.com/"})

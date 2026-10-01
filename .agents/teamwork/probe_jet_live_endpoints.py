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
    "Origin": "https://www.digikalajet.com",
    "Referer": "https://www.digikalajet.com/",
    "Client": "Pwa",
    "ClientOs": "web",
    "platform-sso-disable-prod": "1",
}

def test(url):
    print(f"\nGET {url}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            print("Status:", resp.status)
            body = resp.read().decode('utf-8')
            try:
                data = json.loads(body)
                print("JSON keys:", list(data.keys()) if isinstance(data, dict) else len(data))
                print("Sample:", json.dumps(data, ensure_ascii=False)[:350])
            except Exception:
                print("Raw (first 200 chars):", body[:200])
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        try:
            print("Error body:", e.read().decode('utf-8')[:300])
        except Exception:
            pass
    except Exception as e:
        print("Error:", e)

# 1. Main page / dark store resolution
test(f"https://api.digikalajet.ir/v3/main-page/?latitude={lat}&longitude={lng}")

# 2. Search
q = urllib.parse.quote("شیر")
test(f"https://api.digikalajet.ir/v2/search/?q={q}&latitude={lat}&longitude={lng}")
test(f"https://api.digikalajet.ir/products/search/?q={q}&latitude={lat}&longitude={lng}")

# 3. Flash deals (amazing list)
test(f"https://api.digikalajet.ir/v4/shop/amazing-list?latitude={lat}&longitude={lng}")

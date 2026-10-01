import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
lat = 35.715298
lng = 51.404343

user_agents = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "okhttp/4.9.2",
    "Okala/4.8.0 (Android 13)"
]

urls = [
    f"https://api.okala.com/v1/store/nearby?latitude={lat}&longitude={lng}",
    f"https://api.okala.com/v1/home?lat={lat}&lng={lng}",
    f"https://api.okala.com/v1/promotions",
    f"https://api-app.okala.com/v1/home",
    f"https://api.okala.com/v1/User/Register",
]

for url in urls:
    for ua in user_agents[:2]:
        req = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": "application/json",
            "Origin": "https://okala.com",
            "Referer": "https://okala.com/",
        })
        try:
            with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                print(f"SUCCESS {url} with {ua[:20]}: {r.status} {r.read()[:150]}")
                break
        except urllib.error.HTTPError as e:
            print(f"HTTPError {url} ({ua[:20]}): {e.code} {e.reason}")
        except Exception as e:
            print(f"Failed {url} ({ua[:20]}): {e}")

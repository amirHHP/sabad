import urllib.request
import urllib.error
import ssl
import json
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers_base = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/json,*/*;q=0.8",
    "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
}

targets = [
    # SnappMarket
    ("SnappMarket Home", "https://snapp.market/"),
    ("SnappMarket API Flash Deals", "https://snapp.market/api/v1/promotions/flash-deals?lat=35.715298&lng=51.404343"),
    ("SnappMarket API Search", "https://snapp.market/api/v1/search/products?query=%D8%B4%DB%8C%D8%B1&lat=35.715298&lng=51.404343"),
    ("SnappMarket API Vendors", "https://snapp.market/api/v1/vendors?lat=35.715298&lng=51.404343"),
    ("SnappMarket api.snapp.market", "https://api.snapp.market/api/v1/promotions/flash-deals?lat=35.715298&lng=51.404343"),
    
    # Digikala Jet
    ("Digikala Jet Home", "https://www.digikalajet.com/"),
    ("Digikala Jet non-www", "https://digikalajet.com/"),
    ("Digikala API Jet", "https://api.digikala.com/v1/jet/"),
    ("Digikala API Search", "https://api.digikala.com/v1/search/?q=%D8%B4%DB%8C%D8%B1"),
    ("Digikala Jet API", "https://api.digikalajet.ir/v1/"),
    
    # Okala
    ("Okala Home", "https://okala.com/"),
    ("Okala API Root", "https://api.okala.com/"),
]

print("=== Starting Live Probes ===")
for name, url in targets:
    print(f"\n--- Testing: {name} ({url}) ---")
    headers = dict(headers_base)
    if "snapp.market" in url:
        headers["Origin"] = "https://snapp.market"
        headers["Referer"] = "https://snapp.market/"
    elif "digikala" in url:
        headers["Origin"] = "https://www.digikalajet.com"
        headers["Referer"] = "https://www.digikalajet.com/"
    elif "okala.com" in url:
        headers["Origin"] = "https://okala.com"
        headers["Referer"] = "https://okala.com/"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            status = resp.status
            c_type = resp.headers.get("Content-Type", "")
            final_url = resp.geturl()
            body = resp.read()
            print(f"Status: {status} | Final URL: {final_url}")
            print(f"Content-Type: {c_type} | Length: {len(body)}")
            if "application/json" in c_type:
                try:
                    data = json.loads(body.decode("utf-8"))
                    preview = json.dumps(data, ensure_ascii=False)[:300]
                    print(f"JSON Preview: {preview}")
                except Exception as ex:
                    print(f"JSON Parse Error: {ex}")
            else:
                body_str = body.decode("utf-8", errors="ignore")
                title_match = re.search(r"<title>(.*?)</title>", body_str, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else "No Title"
                print(f"HTML Title: {title}")
                # Look for script sources or API hints
                scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', body_str)
                if scripts:
                    print(f"Script tags ({len(scripts)}): {scripts[:3]}")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        try:
            err_body = e.read().decode("utf-8", errors="ignore")[:300]
            print(f"Error Body: {err_body}")
        except Exception:
            pass
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")

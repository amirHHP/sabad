import urllib.request
import re

url = "https://okala.com"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa,en;q=0.9",
})

try:
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    print("Okala HTML length:", len(html))
    scripts = re.findall(r'src=[\"\']([^\"\']+\.js)[\"\']', html)
    print("Okala scripts:", len(scripts))
    for s in scripts[:15]:
        print(" ", s)
except Exception as e:
    print("Failed to fetch Okala HTML:", e)

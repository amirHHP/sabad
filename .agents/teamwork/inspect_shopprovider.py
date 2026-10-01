import urllib.request
import re

url = "https://www.digikalajet.com/assets/x-lazy-ShopProvider.08QQcqo4.js"
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')
print("Len:", len(js))
endpoints = re.findall(r'["\'`](/(?:v[0-9]|api|cart|shop|user|product)[a-zA-Z0-9_\-/]+)["\'`]', js)
print("Endpoints:", set(endpoints))
urls = re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-z]+[a-zA-Z0-9_/-]*', js)
print("URLs:", set(urls))

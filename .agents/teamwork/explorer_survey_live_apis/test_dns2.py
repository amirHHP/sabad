import socket
import urllib.request
import urllib.error
import ssl

ctx = ssl.create_default_context()

more_domains = [
    "digikalajet.com",
    "www.digikalajet.com",
    "digikala.com",
    "jet.digikala.com",
    "snapp.express",
    "express.snapp.ir",
    "m.okala.com",
    "api-market.okala.com",
    "okala.express"
]

print("=== More DNS Checks ===")
for d in more_domains:
    try:
        ips = socket.gethostbyname_ex(d)
        print(f"✅ {d} -> {ips[2]}")
    except Exception as e:
        print(f"❌ {d} -> {e}")

import socket
import urllib.request
import urllib.error
import ssl
import json

domains = [
    "snapp.market",
    "api.snapp.market",
    "app.snapp.market",
    "snappexpress.ir",
    "jet.digikala.com",
    "api.digikala.com",
    "api.digikalajet.ir",
    "okala.com",
    "api.okala.com",
    "api-app.okala.com",
    "core.okala.com",
    "api-v2.okala.com"
]

print("=== DNS Resolution Check ===")
for d in domains:
    try:
        ips = socket.gethostbyname_ex(d)
        print(f"✅ {d} -> {ips[2]}")
    except Exception as e:
        print(f"❌ {d} -> {e}")

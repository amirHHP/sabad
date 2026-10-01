import urllib.request
import re

url = 'https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js'
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')

for var_name in ['Ur', 'Xr', 'Kr', 'Gr', 'Hr', 'qr', 'Wr', 'Jr', 'Yr', 'Zr', 'Qr']:
    for m in re.finditer(rf'\b{var_name}\s*=\s*(?:`[^`]+`|"[^"]+"|\'[^\']+\'|\w+\([^)]+\))', js):
        print(f"{var_name}: {m.group(0)}")

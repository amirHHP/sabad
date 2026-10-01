import urllib.request
import re

html = urllib.request.urlopen(urllib.request.Request('https://www.digikalajet.com', headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')
scripts = re.findall(r'src=[\"\'](/assets/[^\"\']+\.js)[\"\']', html)

for s in scripts:
    try:
        content = urllib.request.urlopen(urllib.request.Request('https://www.digikalajet.com' + s, headers={'User-Agent': 'Mozilla/5.0'}), timeout=5).read().decode('utf-8', errors='ignore')
        if 'create(' in content or 'baseURL' in content or 'headers:' in content:
            # find baseURL
            bases = re.findall(r'baseURL[:=]\s*["\'`]?([^,"\'`\s]+)', content)
            if bases:
                print(f"{s}: bases = {bases}")
            # find paths
            apis = re.findall(r'(?:get|post|delete|put)\([\"\'`](/[^\"\'`]+)[\"\'`]', content)
            if apis:
                print(f"{s}: apis = {apis[:10]}")
    except Exception:
        pass

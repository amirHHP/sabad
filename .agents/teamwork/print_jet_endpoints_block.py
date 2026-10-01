import urllib.request

url = 'https://www.digikalajet.com/assets/x-page-root.DIkNBjrT.js'
js = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')
idx = js.find('Wr=e=>')
print(js[idx-100:idx+1200])

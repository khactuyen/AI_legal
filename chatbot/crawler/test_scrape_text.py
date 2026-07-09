import requests
from bs4 import BeautifulSoup
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Test scraping the content of the article instead of the .doc file
url = "https://hoatieu.vn/bieu-mau/hop-dong-mua-ban-hang-hoa-182-27156-article"
url2 = "https://thuvienphapluat.vn/bieu-mau/Mau-hop-dong-mua-ban-hang-hoa"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("=== HOATIEU (if exists) ===")
try:
    r = requests.get('https://hoatieu.vn/mau-hop-dong-mua-ban-hang-hoa-66359', headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    content = soup.find('div', class_='article-body') or soup.find('div', class_='content')
    if content:
        print(content.get_text('\n')[:1500])
    else:
        print("No content found")
except Exception as e:
    print(e)

print("\n=== THUVIENPHAPLUAT ===")
try:
    r = requests.get(url2, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    content = soup.find('div', id='divContentDoc') or soup.find('div', class_='content1')
    if content:
        print(content.get_text('\n')[:1500])
    else:
        print("No content found")
except Exception as e:
    print(e)

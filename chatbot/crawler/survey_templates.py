"""
Khảo sát cấu trúc HTML của các trang biểu mẫu để tìm pattern download (fixed encoding)
"""
import requests
from bs4 import BeautifulSoup
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("=== LUATVIETNAM.VN ===")
try:
    r = requests.get('https://luatvietnam.vn/bieu-mau/hop-dong-mua-ban-hang-hoa-182-27156-article.html', headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)[:80]
        if any(kw in href.lower() for kw in ['.doc', '.docx', 'download', 'tai-ve', 'file', 'attachment']):
            print(f"  LINK: {href} | TEXT: {text}")
            
    for btn in soup.find_all(['button', 'a'], class_=True):
        cls = ' '.join(btn.get('class', []))
        if any(kw in cls.lower() for kw in ['download', 'btn-download', 'tai', 'file']):
            print(f"  BUTTON: class={cls}, href={btn.get('href','N/A')}, text={btn.get_text(strip=True)[:50]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== THUVIENPHAPLUAT.VN ===")
try:
    r = requests.get('https://thuvienphapluat.vn/bieu-mau/Mau-hop-dong-mua-ban-hang-hoa', headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)[:80]
        if any(kw in href.lower() for kw in ['.doc', '.docx', 'download', 'tai-ve', 'file', 'attachment']):
            print(f"  LINK: {href} | TEXT: {text}")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== HOATIEU.VN ===")
try:
    r = requests.get('https://hoatieu.vn/bieu-mau/hop-dong', headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)[:80]
        if any(kw in href.lower() for kw in ['.doc', '.docx', 'download', 'tai-ve', 'file', 'attachment']):
            print(f"  LINK: {href} | TEXT: {text}")
except Exception as e:
    print(f"  Error: {e}")

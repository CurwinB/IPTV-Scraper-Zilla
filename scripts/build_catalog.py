import json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'; DATA.mkdir(exist_ok=True)
UA='BouyonTV/1.0'; TIMEOUT=(5,8); MAX_WORKERS=32
HEADERS={'User-Agent':UA,'Accept':'application/vnd.github+json'}
REMOTE=[
 'https://api.github.com/repos/CurwinB/iptv/contents/streams?ref=master',
]

def attr(h,k):
 m=re.search(rf'{re.escape(k)}="([^"]*)"',h,re.I); return m.group(1).strip() if m else ''

def parse_text(text,source):
 rows=[]; meta=None
 for line in text.splitlines():
  t=line.strip()
  if t.startswith('#EXTINF:'):
   p=t.find(','); h=t if p<0 else t[:p]; n='' if p<0 else t[p+1:].strip()
   meta={'id':attr(h,'tvg-id'),'name':n,'logo':attr(h,'tvg-logo'),'group':attr(h,'group-title'),'country':attr(h,'tvg-country'),'language':attr(h,'tvg-language'),'source':source}
  elif meta and re.match(r'^https?://',t,re.I): rows.append({**meta,'url':t}); meta=None
 return rows

def github_dir(url):
 out=[]; page=1
 while True:
  r=requests.get(url+f'&per_page=100&page={page}',headers=HEADERS,timeout=TIMEOUT); r.raise_for_status(); items=r.json()
  if not items: break
  out += [x for x in items if x.get('type')=='file' and re.search(r'\.(m3u8?|txt)$',x.get('name',''),re.I)]
  if len(items)<100: break
  page+=1
 return out

def remote_file(item):
 try:
  r=requests.get(item['download_url'],headers={'User-Agent':UA},timeout=TIMEOUT); r.raise_for_status()
  return parse_text(r.text,'iptv/'+item['name']) if len(r.content)<=2_000_000 else []
 except Exception: return []

def check(item):
 url=item['url']; started=time.monotonic()
 try:
  r=requests.get(url,headers={'User-Agent':UA,'Accept':'*/*','Range':'bytes=0-131071'},timeout=TIMEOUT,allow_redirects=True,stream=True)
  latency=round((time.monotonic()-started)*1000); status=r.status_code; final=r.url; ct=(r.headers.get('content-type') or '').lower()
  if status>=400: r.close(); return None
  sample=b''
  for part in r.iter_content(16384):
   sample+=part
   if len(sample)>=131072: break
  r.close()
  hls='mpegurl' in ct or '.m3u8' in url.lower() or '.m3u8' in final.lower() or b'#EXTM3U' in sample[:4096]
  if not hls: return {'latency':latency,'status':status,'hls':False} if sample else None
  manifest=sample.decode('utf-8','ignore')
  if '#EXTM3U' not in manifest: return None
  refs=[x.strip() for x in manifest.splitlines() if x.strip() and not x.startswith('#')][:3]
  if not refs: return None
  probe=urljoin(final,refs[0])
  p=requests.get(probe,headers={'User-Agent':UA,'Range':'bytes=0-32767'},timeout=TIMEOUT,allow_redirects=True,stream=True)
  ok=p.status_code<400; chunk=next(p.iter_content(32768),b'') if ok else b''; p.close()
  if not ok or not chunk: return None
  return {'latency':latency,'status':status,'hls':True}
 except Exception: return None

def main():
 rows=[]
 local=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in {'.m3u','.m3u8'} and '.git' not in p.parts and 'data' not in p.parts]
 for p in local:
  try: rows += parse_text(p.read_text(encoding='utf-8',errors='ignore'),p.name)
  except Exception: pass
 for d in REMOTE:
  try:
   files=github_dir(d); print('Found',len(files),'IPTV playlists')
   with ThreadPoolExecutor(max_workers=8) as pool:
    for batch in pool.map(remote_file,files): rows += batch
  except Exception as e: print('IPTV source failed:',e)
 unique={r['url']:r for r in rows if r.get('url')}; print('Unique URLs:',len(unique))
 healthy=[]
 with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
  fs={pool.submit(check,r):r for r in unique.values()}
  for f in as_completed(fs):
   result=f.result()
   if result: healthy.append((fs[f],result))
 channels={}
 for raw,result in healthy:
  name=re.sub(r'\s+',' ',raw.get('name') or raw.get('id') or 'Unknown').strip()
  key=(raw.get('id') or re.sub(r'[^a-z0-9]+','',name.lower()),raw.get('country',''),raw.get('language',''))
  c=channels.setdefault(key,{'id':raw.get('id') or key[0],'name':name,'logo':raw.get('logo',''),'country':raw.get('country',''),'language':raw.get('language',''),'group':raw.get('group',''),'sources':[]})
  if not c['logo'] and raw.get('logo'): c['logo']=raw['logo']
  c['sources'].append({'url':raw['url'],'source':raw.get('source',''),'latency':result['latency'],'status':result['status'],'hls':result['hls']})
 output=[]
 for c in channels.values():
  c['sources'].sort(key=lambda x:x['latency']); c['sourceCount']=len(c['sources']); c['url']=c['sources'][0]['url']; output.append(c)
 output.sort(key=lambda x:x['name'].lower())
 payload={'version':2,'updatedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'count':len(output),'checkedUrls':len(unique),'healthyUrls':sum(x['sourceCount'] for x in output),'channels':output}
 (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 print(f'BouyonTV: {payload["checkedUrls"]} checked, {payload["healthyUrls"]} healthy, {payload["count"]} playable channels')
if __name__=='__main__': main()

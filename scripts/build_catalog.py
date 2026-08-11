import json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
UA='BouyonTV/1.0'; GH={'User-Agent':UA,'Accept':'application/vnd.github+json'}

# Discover playlist files from each repo using one Git tree request. This avoids
# recursive Contents-API calls and prevents rate-limit/empty-catalog failures.
def playlist_urls(repo, ref='master', prefix=''):
    r=requests.get(f'https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1',headers=GH,timeout=60)
    r.raise_for_status(); tree=r.json().get('tree',[])
    urls=[]
    for item in tree:
        p=item.get('path','')
        if item.get('type')!='blob' or not re.search(r'\.(m3u8?|txt)$',p,re.I): continue
        if prefix and not p.lower().startswith(prefix.lower().rstrip('/')+'/'): continue
        urls.append(f'https://raw.githubusercontent.com/{repo}/{ref}/{p}')
    return urls

def parse(text,source):
    rows=[]; meta=None
    for line in text.splitlines():
        t=line.strip()
        if t.startswith('#EXTINF:'):
            p=t.find(','); h=t if p<0 else t[:p]; name='' if p<0 else t[p+1:].strip()
            def a(k):
                m=re.search(rf'{re.escape(k)}="([^"]*)"',h,re.I); return m.group(1).strip() if m else ''
            meta={'id':a('tvg-id'),'name':name,'logo':a('tvg-logo'),'group':a('group-title'),'country':a('tvg-country'),'language':a('tvg-language'),'source':source}
        elif meta and re.match(r'^https?://',t,re.I):
            rows.append({**meta,'url':t}); meta=None
    return rows

def load(url):
    try:
        r=requests.get(url,headers={'User-Agent':UA},timeout=30); r.raise_for_status()
        if len(r.content)>8_000_000: return []
        return parse(r.text,url)
    except Exception as e:
        print('playlist failed:',url,e); return []

def check(r):
    start=time.monotonic()
    try:
        x=requests.get(r['url'],headers={'User-Agent':UA,'Accept':'*/*','Range':'bytes=0-65535'},timeout=(3,6),allow_redirects=True,stream=True)
        latency=round((time.monotonic()-start)*1000); status=x.status_code; final=x.url; ct=(x.headers.get('content-type') or '').lower()
        if status>=400: x.close(); return None
        sample=b''
        for part in x.iter_content(16384):
            sample+=part
            if len(sample)>=65536: break
        x.close()
        if not sample: return None
        hls='mpegurl' in ct or '.m3u8' in final.lower() or '.m3u8' in r['url'].lower() or b'#EXTM3U' in sample[:4096]
        if hls and b'#EXTM3U' not in sample[:8192]: return None
        return {**r,'latency':latency,'status':status,'hls':hls,'finalUrl':final}
    except Exception: return None

def main():
    playlist_urls=[]
    for repo,ref,prefix in [('CurwinB/iptv','master','streams'),('CurwinB/IPTV-Scraper-Zilla','main','')]:
        found=playlist_urls_for(repo,ref,prefix)
        print(f'{repo}: {len(found)} playlists found')
        playlist_urls += found
    playlist_urls=list(dict.fromkeys(playlist_urls))
    print('TOTAL PLAYLISTS:',len(playlist_urls))
    if not playlist_urls: raise SystemExit('ERROR: no playlists discovered')
    rows=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        for batch in pool.map(load,playlist_urls): rows += batch
    unique={r['url']:r for r in rows if r.get('url')}
    print('RAW STREAMS:',len(rows)); print('UNIQUE URLS:',len(unique))
    if not unique: raise SystemExit('ERROR: playlists contained zero stream URLs')
    healthy=[]
    with ThreadPoolExecutor(max_workers=48) as pool:
        fs=[pool.submit(check,r) for r in unique.values()]
        for f in as_completed(fs):
            v=f.result()
            if v: healthy.append(v)
    print('HEALTHY URLS:',len(healthy))
    channels={}
    for r in healthy:
        name=re.sub(r'\s+',' ',r.get('name') or r.get('id') or 'Unknown').strip()
        key=(re.sub(r'[^a-z0-9]+','',name.lower()),r.get('country','').lower(),r.get('language','').lower())
        c=channels.setdefault(key,{'id':r.get('id') or key[0],'name':name,'logo':r.get('logo',''),'country':r.get('country',''),'language':r.get('language',''),'group':r.get('group',''),'sources':[]})
        if not c['logo'] and r.get('logo'): c['logo']=r['logo']
        c['sources'].append({'url':r['url'],'source':r['source'],'latency':r['latency'],'status':r['status'],'hls':r['hls']})
    output=[]
    for c in channels.values():
        c['sources'].sort(key=lambda x:x['latency']); c['sourceCount']=len(c['sources']); c['url']=c['sources'][0]['url']; output.append(c)
    output.sort(key=lambda x:x['name'].lower())
    if not output: raise SystemExit('ERROR: validation produced zero playable channels')
    payload={'version':3,'updatedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'count':len(output),'checkedUrls':len(unique),'healthyUrls':len(healthy),'channels':output}
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'PLAYABLE CHANNELS: {len(output)}')

def playlist_urls_for(repo,ref,prefix):
    r=requests.get(f'https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1',headers=GH,timeout=60); r.raise_for_status(); tree=r.json().get('tree',[])
    out=[]
    for item in tree:
        p=item.get('path','')
        if item.get('type')!='blob' or not re.search(r'\.(m3u8?|txt)$',p,re.I): continue
        if prefix and not p.lower().startswith(prefix.lower().rstrip('/')+'/'): continue
        out.append(f'https://raw.githubusercontent.com/{repo}/{ref}/{p}')
    return out

if __name__=='__main__': main()

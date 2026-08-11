import json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
UA='BouyonTV/1.0'; GH={'User-Agent':UA,'Accept':'application/vnd.github+json'}
COUNTRY_CODES={'us':'United States','usa':'United States','uk':'United Kingdom','gb':'United Kingdom','fr':'France','ca':'Canada','au':'Australia','de':'Germany','es':'Spain','it':'Italy','br':'Brazil','mx':'Mexico','ar':'Argentina','cl':'Chile','co':'Colombia','pt':'Portugal','nl':'Netherlands','be':'Belgium','ch':'Switzerland','at':'Austria','ie':'Ireland','in':'India','jp':'Japan','kr':'South Korea','cn':'China','hk':'Hong Kong','tw':'Taiwan','ph':'Philippines','id':'Indonesia','th':'Thailand','vn':'Vietnam','za':'South Africa','ng':'Nigeria','gh':'Ghana','ke':'Kenya','tz':'Tanzania','ug':'Uganda','jm':'Jamaica','tt':'Trinidad and Tobago','bb':'Barbados','dm':'Dominica','gd':'Grenada','lc':'Saint Lucia','vc':'Saint Vincent and the Grenadines','kn':'Saint Kitts and Nevis','ag':'Antigua and Barbuda','do':'Dominican Republic','pr':'Puerto Rico','ae':'United Arab Emirates','sa':'Saudi Arabia','qa':'Qatar','il':'Israel','tr':'Turkey','ru':'Russia','ua':'Ukraine'}
LANGUAGE_CODES={'en':'English','eng':'English','english':'English','fr':'French','fra':'French','fre':'French','french':'French','es':'Spanish','spa':'Spanish','spanish':'Spanish','pt':'Portuguese','por':'Portuguese','portuguese':'Portuguese','de':'German','deu':'German','ger':'German','it':'Italian','ita':'Italian','nl':'Dutch','nld':'Dutch','ar':'Arabic','ara':'Arabic','zh':'Chinese','zho':'Chinese','chi':'Chinese','ja':'Japanese','jpn':'Japanese','ko':'Korean','kor':'Korean','hi':'Hindi','hin':'Hindi','ru':'Russian','rus':'Russian','tr':'Turkish','tur':'Turkish','pl':'Polish','pol':'Polish','ukr':'Ukrainian','uk':'Ukrainian','sv':'Swedish','swe':'Swedish','no':'Norwegian','nor':'Norwegian','da':'Danish','dan':'Danish','fi':'Finnish','fin':'Finnish','cs':'Czech','ces':'Czech','el':'Greek','ell':'Greek','he':'Hebrew','heb':'Hebrew','idn':'Indonesian','id':'Indonesian','ms':'Malay','msa':'Malay','th':'Thai','tha':'Thai','vi':'Vietnamese','vie':'Vietnamese'}
CATEGORY_MAP={'news':'News','news & information':'News','sports':'Sports','sport':'Sports','movie':'Movies','movies':'Movies','film':'Movies','films':'Movies','entertainment':'Entertainment','kids':'Kids','children':'Kids','cartoon':'Kids','music':'Music','documentary':'Documentary','documentaries':'Documentary','lifestyle':'Lifestyle','religious':'Religious','religion':'Religious','faith':'Religious','business':'Business','finance':'Business','shopping':'Shopping','general':'General','generalist':'General'}

def playlist_urls_for(repo,ref,prefix=''):
    r=requests.get(f'https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1',headers=GH,timeout=60); r.raise_for_status(); tree=r.json().get('tree',[])
    return [f'https://raw.githubusercontent.com/{repo}/{ref}/{x["path"]}' for x in tree if x.get('type')=='blob' and re.search(r'\.(m3u8?|txt)$',x.get('path',''),re.I) and (not prefix or x['path'].lower().startswith(prefix.lower().rstrip('/')+'/'))]

def clean_name(name):
    name=re.sub(r'\s+',' ',name or '').strip(); name=re.sub(r'^[-–—_\s]+','',name); name=re.sub(r'^\s*\d+\s*(?:,|:|\|)\s*','',name)
    return name.strip(' ,|-') or 'Unknown'

def norm_language(value):
    if not value: return ''
    parts=re.split(r'[,;/|]+',value.lower())
    vals=[LANGUAGE_CODES.get(p.strip(),p.strip().title()) for p in parts if p.strip()]
    return ', '.join(dict.fromkeys(vals))

def norm_country(value):
    if not value: return ''
    v=value.strip(); low=v.lower()
    return COUNTRY_CODES.get(low, COUNTRY_CODES.get(low[:2], v.title()))

def infer_country(name,group,source):
    text=f'{name} {group} {source}'.lower()
    patterns=[(r'\busa\b|\bunited states\b|\bus\b','United States'),(r'\buk\b|\bunited kingdom\b|\bgreat britain\b','United Kingdom'),(r'\bcanada\b|\bcan\b','Canada'),(r'\bfrance\b|\bfr\b','France'),(r'\bspain\b|\bes\b','Spain'),(r'\bgermany\b|\bde\b','Germany'),(r'\bitaly\b|\bit\b','Italy'),(r'\baustralia\b|\bau\b','Australia'),(r'\bjapan\b|\bjp\b','Japan'),(r'\bbrazil\b|\bbr\b','Brazil'),(r'\bmexico\b|\bmx\b','Mexico'),(r'\bdominica\b|\bdm\b','Dominica'),(r'\bgrenada\b|\bgr\b','Grenada'),(r'\bbarbados\b|\bbb\b','Barbados'),(r'\bjamaica\b|\bjm\b','Jamaica'),(r'\btrinidad\b|\btt\b','Trinidad and Tobago')]
    for p,c in patterns:
        if re.search(p,text): return c
    return ''

def infer_language(country,name,group):
    if country in {'United States','United Kingdom','Canada','Australia','Jamaica','Barbados','Dominica','Grenada','Trinidad and Tobago'}: return 'English'
    if country in {'France'}: return 'French'
    if country in {'Spain','Mexico','Argentina','Chile','Colombia','Dominican Republic','Puerto Rico'}: return 'Spanish'
    if country in {'Brazil','Portugal'}: return 'Portuguese'
    if country=='Germany': return 'German'
    if country=='Italy': return 'Italian'
    if country=='Japan': return 'Japanese'
    if country=='South Korea': return 'Korean'
    if country in {'China','Hong Kong','Taiwan'}: return 'Chinese'
    return ''

def normalize_metadata(raw):
    name=clean_name(raw.get('name')); group=raw.get('group','') or ''; country=norm_country(raw.get('country','')); language=norm_language(raw.get('language',''))
    if not country: country=infer_country(name,group,raw.get('source',''))
    if not language: language=infer_language(country,name,group)
    gt=group.lower()
    category=''
    for k,v in CATEGORY_MAP.items():
        if re.search(rf'(?<![a-z]){re.escape(k)}(?![a-z])',gt): category=v; break
    if not category:
        for k,v in CATEGORY_MAP.items():
            if re.search(rf'(?<![a-z]){re.escape(k)}(?![a-z])',name.lower()): category=v; break
    if not category: category='General'
    return name,country,language,category

def parse(text,source):
    rows=[]; meta=None
    for line in text.splitlines():
        t=line.strip()
        if t.startswith('#EXTINF:'):
            p=t.find(','); h=t if p<0 else t[:p]; name='' if p<0 else t[p+1:].strip()
            def a(k):
                m=re.search(rf'{re.escape(k)}="([^"]*)"',h,re.I); return m.group(1).strip() if m else ''
            meta={'id':a('tvg-id'),'name':name,'logo':a('tvg-logo'),'group':a('group-title'),'country':a('tvg-country'),'language':a('tvg-language'),'source':source}
        elif meta and re.match(r'^https?://',t,re.I): rows.append({**meta,'url':t}); meta=None
    return rows

def load(url):
    try:
        r=requests.get(url,headers={'User-Agent':UA},timeout=30); r.raise_for_status()
        return parse(r.text,url) if len(r.content)<=8_000_000 else []
    except Exception as e: print('playlist failed:',url,e); return []

def check(r):
    start=time.monotonic()
    try:
        x=requests.get(r['url'],headers={'User-Agent':UA,'Accept':'*/*','Range':'bytes=0-65535'},timeout=(3,6),allow_redirects=True,stream=True); latency=round((time.monotonic()-start)*1000); status=x.status_code; final=x.url; ct=(x.headers.get('content-type') or '').lower()
        if status>=400: x.close(); return None
        sample=b''
        for part in x.iter_content(16384): sample+=part; 
        x.close(); sample=sample[:65536]
        if not sample: return None
        hls='mpegurl' in ct or '.m3u8' in final.lower() or '.m3u8' in r['url'].lower() or b'#EXTM3U' in sample[:4096]
        if hls and b'#EXTM3U' not in sample[:8192]: return None
        return {**r,'latency':latency,'status':status,'hls':hls,'finalUrl':final}
    except Exception: return None

def main():
    playlist_urls=[]
    for repo,ref,prefix in [('CurwinB/iptv','master','streams'),('CurwinB/IPTV-Scraper-Zilla','main','')]: playlist_urls += playlist_urls_for(repo,ref,prefix)
    playlist_urls=list(dict.fromkeys(playlist_urls)); print('TOTAL PLAYLISTS:',len(playlist_urls))
    if not playlist_urls: raise SystemExit('ERROR: no playlists discovered')
    rows=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        for batch in pool.map(load,playlist_urls): rows += batch
    unique={r['url']:r for r in rows if r.get('url')}; print('RAW STREAMS:',len(rows),'UNIQUE URLS:',len(unique))
    if not unique: raise SystemExit('ERROR: zero stream URLs')
    healthy=[]
    with ThreadPoolExecutor(max_workers=48) as pool:
        fs=[pool.submit(check,r) for r in unique.values()]
        for f in as_completed(fs):
            v=f.result()
            if v: healthy.append(v)
    print('HEALTHY URLS:',len(healthy))
    channels={}
    for r in healthy:
        name,country,language,category=normalize_metadata(r); key=(re.sub(r'[^a-z0-9]+','',name.lower()),country.lower(),language.lower())
        c=channels.setdefault(key,{'id':r.get('id') or key[0],'name':name,'logo':r.get('logo',''),'country':country,'language':language,'category':category,'group':r.get('group',''),'sources':[]})
        if not c['logo'] and r.get('logo'): c['logo']=r['logo']
        c['sources'].append({'url':r['url'],'source':r['source'],'latency':r['latency'],'status':r['status'],'hls':r['hls']})
    output=[]
    for c in channels.values(): c['sources'].sort(key=lambda x:x['latency']); c['sourceCount']=len(c['sources']); c['url']=c['sources'][0]['url']; output.append(c)
    output.sort(key=lambda x:x['name'].lower())
    if not output: raise SystemExit('ERROR: zero playable channels')
    payload={'version':4,'updatedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'count':len(output),'checkedUrls':len(unique),'healthyUrls':len(healthy),'metadataVersion':1,'channels':output}
    (DATA/'catalog.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); print(f'PLAYABLE CHANNELS: {len(output)}')

if __name__=='__main__': main()

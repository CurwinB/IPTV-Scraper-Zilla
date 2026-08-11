import json, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data' / 'catalog.json'

COUNTRY_CODES = {
    'us':'United States','usa':'United States','uk':'United Kingdom','gb':'United Kingdom','fr':'France','ca':'Canada','au':'Australia','de':'Germany','es':'Spain','it':'Italy','br':'Brazil','mx':'Mexico','ar':'Argentina','cl':'Chile','co':'Colombia','pt':'Portugal','nl':'Netherlands','be':'Belgium','ch':'Switzerland','at':'Austria','ie':'Ireland','in':'India','jp':'Japan','kr':'South Korea','cn':'China','hk':'Hong Kong','tw':'Taiwan','ph':'Philippines','id':'Indonesia','th':'Thailand','vn':'Vietnam','za':'South Africa','ng':'Nigeria','gh':'Ghana','ke':'Kenya','tz':'Tanzania','ug':'Uganda','jm':'Jamaica','tt':'Trinidad and Tobago','bb':'Barbados','dm':'Dominica','gd':'Grenada','lc':'Saint Lucia','vc':'Saint Vincent and the Grenadines','kn':'Saint Kitts and Nevis','ag':'Antigua and Barbuda','do':'Dominican Republic','pr':'Puerto Rico','ae':'United Arab Emirates','sa':'Saudi Arabia','qa':'Qatar','il':'Israel','tr':'Turkey','ru':'Russia','ua':'Ukraine'
}
LANGUAGES = {
    'en':'English','eng':'English','english':'English','fr':'French','fra':'French','fre':'French','french':'French','es':'Spanish','spa':'Spanish','spanish':'Spanish','pt':'Portuguese','por':'Portuguese','portuguese':'Portuguese','de':'German','deu':'German','ger':'German','it':'Italian','ita':'Italian','nl':'Dutch','nld':'Dutch','ar':'Arabic','ara':'Arabic','zh':'Chinese','zho':'Chinese','chi':'Chinese','ja':'Japanese','jpn':'Japanese','ko':'Korean','kor':'Korean','hi':'Hindi','hin':'Hindi','ru':'Russian','rus':'Russian','tr':'Turkish','tur':'Turkish','pl':'Polish','pol':'Polish','ukr':'Ukrainian','sv':'Swedish','swe':'Swedish','no':'Norwegian','nor':'Norwegian','da':'Danish','dan':'Danish','fi':'Finnish','fin':'Finnish','cs':'Czech','ces':'Czech','el':'Greek','ell':'Greek','he':'Hebrew','heb':'Hebrew','ms':'Malay','msa':'Malay','th':'Thai','tha':'Thai','vi':'Vietnamese','vie':'Vietnamese','idn':'Indonesian'
}
CATEGORY_MAP = {
    'news':'News','news & information':'News','sports':'Sports','sport':'Sports','movie':'Movies','movies':'Movies','film':'Movies','films':'Movies','entertainment':'Entertainment','kids':'Kids','children':'Kids','cartoon':'Kids','music':'Music','documentary':'Documentary','documentaries':'Documentary','lifestyle':'Lifestyle','religious':'Religious','religion':'Religious','faith':'Religious','business':'Business','finance':'Business','shopping':'Shopping','general':'General','generalist':'General','anime':'Anime','comedy':'Entertainment','series':'Entertainment','drama':'Entertainment'
}
COUNTRY_PATTERNS = [
    (r'\busa\b|\bunited states\b|\bunited states of america\b','United States'),
    (r'\buk\b|\bunited kingdom\b|\bgreat britain\b|\bengland\b','United Kingdom'),
    (r'\bcanada\b','Canada'),(r'\bfrance\b','France'),(r'\bspain\b','Spain'),(r'\bgermany\b','Germany'),(r'\bitaly\b','Italy'),(r'\baustralia\b','Australia'),(r'\bjapan\b','Japan'),(r'\bbrazil\b','Brazil'),(r'\bmexico\b','Mexico'),(r'\bdominica\b','Dominica'),(r'\bgrenada\b','Grenada'),(r'\bbarbados\b','Barbados'),(r'\bjamaica\b','Jamaica'),(r'\btrinidad(?: and)? tobago\b','Trinidad and Tobago'),(r'\bportugal\b','Portugal'),(r'\bindia\b','India'),(r'\bchina\b','China'),(r'\bkorea\b|\bsouth korea\b','South Korea')
]

def clean(v):
    return re.sub(r'\s+',' ',str(v or '')).strip()

def norm_country(v):
    v=clean(v); return COUNTRY_CODES.get(v.lower(), v.title() if v else '')

def norm_language(v):
    if not v: return ''
    vals=[]
    for p in re.split(r'[,;/|]+', str(v).lower()):
        p=p.strip()
        if p: vals.append(LANGUAGES.get(p,p.title()))
    return ', '.join(dict.fromkeys(vals))

def infer_country(ch):
    text=' '.join(clean(ch.get(k)) for k in ('name','group','id','url','logo')).lower()
    for pattern,country in COUNTRY_PATTERNS:
        if re.search(pattern,text): return country
    return ''

def infer_language(country, name, group):
    if country in {'United States','United Kingdom','Canada','Australia','Jamaica','Barbados','Dominica','Grenada','Trinidad and Tobago'}: return 'English'
    if country == 'France': return 'French'
    if country in {'Spain','Mexico','Argentina','Chile','Colombia','Dominican Republic','Puerto Rico'}: return 'Spanish'
    if country in {'Brazil','Portugal'}: return 'Portuguese'
    if country == 'Germany': return 'German'
    if country == 'Italy': return 'Italian'
    if country == 'Japan': return 'Japanese'
    if country == 'South Korea': return 'Korean'
    if country in {'China','Hong Kong','Taiwan'}: return 'Chinese'
    return ''

def category(ch):
    text=(clean(ch.get('group'))+' '+clean(ch.get('name'))).lower()
    for key,val in CATEGORY_MAP.items():
        if re.search(rf'(?<![a-z]){re.escape(key)}(?![a-z])',text): return val
    return 'General'

def main():
    if not CATALOG.exists() or CATALOG.stat().st_size == 0: raise SystemExit('ERROR: no existing verified catalogue found')
    data=json.loads(CATALOG.read_text(encoding='utf-8'))
    channels=data.get('channels')
    if not isinstance(channels,list) or not channels: raise SystemExit('ERROR: existing catalogue has zero channels')
    counts={'country':0,'language':0,'category':0}
    for ch in channels:
        old_country=norm_country(ch.get('country'))
        country=old_country or infer_country(ch)
        old_language=norm_language(ch.get('language'))
        language=old_language or infer_language(country,clean(ch.get('name')),clean(ch.get('group')))
        cat=category(ch)
        if country: counts['country']+=1
        if language: counts['language']+=1
        if cat: counts['category']+=1
        ch['country']=country
        ch['language']=language
        ch['category']=cat
    data['version']=4
    data['metadataVersion']=2
    data['metadataUpdatedAt']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    data['metadataCoverage']=counts
    CATALOG.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'METADATA ENRICHED: {len(channels)} channels')
    print(f'Country: {counts["country"]}/{len(channels)}')
    print(f'Language: {counts["language"]}/{len(channels)}')
    print(f'Category: {counts["category"]}/{len(channels)}')

if __name__ == '__main__': main()

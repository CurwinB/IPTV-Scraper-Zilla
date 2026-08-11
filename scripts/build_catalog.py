import json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

UA = 'BouyonTV/1.0 (+https://github.com/CurwinB/IPTV-Scraper-Zilla)'
TIMEOUT = (5, 8)
MAX_WORKERS = 32


def attr(head, key):
    m = re.search(rf'{re.escape(key)}="([^"]*)"', head, re.I)
    return m.group(1).strip() if m else ''


def parse_playlist(path):
    rows, meta = [], None
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return rows
    for line in text.splitlines():
        t = line.strip()
        if t.startswith('#EXTINF:'):
            comma = t.find(',')
            head = t if comma < 0 else t[:comma]
            name = '' if comma < 0 else t[comma + 1:].strip()
            meta = {
                'id': attr(head, 'tvg-id'), 'name': name,
                'logo': attr(head, 'tvg-logo'), 'group': attr(head, 'group-title'),
                'country': attr(head, 'tvg-country'), 'language': attr(head, 'tvg-language'),
                'source': path.name,
            }
        elif meta and re.match(r'^https?://', t, re.I):
            rows.append({**meta, 'url': t})
            meta = None
    return rows


def check(url):
    started = time.monotonic()
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Range': 'bytes=0-65535'}, timeout=TIMEOUT, allow_redirects=True, stream=True)
        latency = round((time.monotonic() - started) * 1000)
        ct = (r.headers.get('content-type') or '').lower()
        final = r.url
        ok = r.status_code < 400
        looks_hls = 'mpegurl' in ct or '.m3u8' in url.lower() or '.m3u8' in final.lower()
        if looks_hls and ok:
            chunk = b''
            for part in r.iter_content(8192):
                chunk += part
                if len(chunk) >= 65536: break
            ok = b'#EXTM3U' in chunk
        return {'ok': ok, 'latency': latency, 'status': r.status_code, 'final': final, 'hls': looks_hls}
    except Exception as e:
        return {'ok': False, 'latency': 999999, 'status': 0, 'error': type(e).__name__}


def main():
    playlists = [p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in {'.m3u', '.m3u8'} and '.git' not in p.parts and 'data' not in p.parts]
    rows = []
    for p in playlists:
        rows.extend(parse_playlist(p))

    # Deduplicate exact URLs first.
    unique = {}
    for r in rows:
        if r.get('url'):
            unique.setdefault(r['url'], r)

    checks = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(check, url): url for url in unique}
        for f in as_completed(futures):
            checks[futures[f]] = f.result()

    channels = {}
    for url, raw in unique.items():
        result = checks.get(url, {})
        if not result.get('ok'):
            continue
        name = re.sub(r'\s+', ' ', raw.get('name') or raw.get('id') or 'Unknown').strip()
        key = (raw.get('id') or re.sub(r'[^a-z0-9]+', '', name.lower()), raw.get('country',''), raw.get('language',''))
        channel = channels.setdefault(key, {
            'id': raw.get('id') or key[0], 'name': name, 'logo': raw.get('logo',''),
            'country': raw.get('country',''), 'language': raw.get('language',''),
            'group': raw.get('group',''), 'sources': []
        })
        if not channel['logo'] and raw.get('logo'): channel['logo'] = raw['logo']
        channel['sources'].append({
            'url': url, 'source': raw.get('source',''),
            'latency': result.get('latency', 999999), 'status': result.get('status', 0)
        })

    output = []
    for c in channels.values():
        c['sources'].sort(key=lambda x: x['latency'])
        c['sourceCount'] = len(c['sources'])
        c['url'] = c['sources'][0]['url']
        output.append(c)
    output.sort(key=lambda x: x['name'].lower())

    payload = {'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'count': len(output), 'channels': output}
    (DATA / 'catalog.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'BouyonTV: {len(unique)} unique URLs checked, {len(output)} healthy channels retained')

if __name__ == '__main__': main()

import json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

UA = 'BouyonTV/1.0'
TIMEOUT = (5, 8)
MAX_WORKERS = 32
GITHUB_HEADERS = {'User-Agent': UA, 'Accept': 'application/vnd.github+json'}
REMOTE_PLAYLIST_DIRS = [
    'https://api.github.com/repos/CurwinB/iptv/contents/streams?ref=master',
]


def attr(head, key):
    m = re.search(rf'{re.escape(key)}="([^"]*)"', head, re.I)
    return m.group(1).strip() if m else ''


def parse_text(text, source):
    rows, meta = [], None
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
                'source': source,
            }
        elif meta and re.match(r'^https?://', t, re.I):
            rows.append({**meta, 'url': t})
            meta = None
    return rows


def parse_file(path):
    try:
        return parse_text(path.read_text(encoding='utf-8', errors='ignore'), path.name)
    except Exception:
        return []


def github_dir(url):
    files = []
    page = 1
    while True:
        r = requests.get(url + f'&per_page=100&page={page}', headers=GITHUB_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json()
        if not items:
            break
        files.extend(x for x in items if x.get('type') == 'file' and re.search(r'\.(m3u8?|txt)$', x.get('name',''), re.I))
        if len(items) < 100:
            break
        page += 1
    return files


def download_remote(item):
    try:
        r = requests.get(item['download_url'], headers={'User-Agent': UA}, timeout=TIMEOUT)
        r.raise_for_status()
        if len(r.content) > 2_000_000:
            return []
        return parse_text(r.text, 'iptv/' + item['name'])
    except Exception:
        return []


def check(url):
    started = time.monotonic()
    try:
        headers = {'User-Agent': UA, 'Accept': '*/*', 'Range': 'bytes=0-131071'}
        r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, stream=True)
        latency = round((time.monotonic() - started) * 1000)
        ct = (r.headers.get('content-type') or '').lower()
        final = r.url
        status = r.status_code
        if status >= 400:
            r.close(); return None
        sample = b''
        for part in r.iter_content(16384):
            sample += part
            if len(sample) >= 131072: break
        r.close()
        is_hls = 'mpegurl' in ct or '.m3u8' in url.lower() or '.m3u8' in final.lower() or b'#EXTM3U' in sample[:4096]
        if not is_hls:
            if not sample: return None
            return {'url': url, 'latency': latency, 'status': status, 'hls': False}

        manifest = sample.decode('utf-8', errors='ignore')
        if '#EXTM3U' not in manifest:
            return None

        # Confirm that an HLS manifest contains an actual variant/media reference.
        refs = []
        lines = [x.strip() for x in manifest.splitlines() if x.strip() and not x.startswith('#')]
        refs.extend(lines[:3])
        if not refs:
            return None
        # Probe one referenced playlist/segment. This rejects many "HTTP 200 but dead" URLs.
        probe = urljoin(final, refs[0])
        try:
            p = requests.get(probe, headers={'User-Agent': UA, 'Range': 'bytes=0-32767'}, timeout=TIMEOUT, allow_redirects=True, stream=True)
            ok = p.status_code < 400
            chunk = next(p.iter_content(32768), b'') if ok else b''
            p.close()
            if not ok or not chunk:
                return None
            if b'#EXTM3U' in chunk and b'#EXTINF' not in chunk and b'#EXT-X-STREAM-INF' not in chunk:
                return None
        except Exception:
            return None
        return {'url': url, 'latency': latency, 'status': status, 'hls': True}
    except Exception:
        return None


def main():
    rows = []
    local_playlists = [p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in {'.m3u', '.m3u8'} and '.git' not in p.parts and 'data' not in p.parts]
    for p in local_playlists:
        rows.extend(parse_file(p))

    # Add the user's IPTV fork as a second source without cloning its ~1GB repository.
    for directory in REMOTE_PLAYLIST_DIRS:
        try:
            files = github_dir(directory)
            print(f'Found {len(files)} IPTV playlist files')
            with ThreadPoolExecutor(max_workers=8) as pool:
                for batch in pool.map(download_remote, files):
                    rows.extend(batch)
        except Exception as e:
            print('Remote IPTV source unavailable:', e)

    unique = {}
    for r in rows:
        if r.get('url'):
            unique.setdefault(r['url'], r)
    print(f'Collected {len(unique)} unique stream URLs')

    checks = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(check, url): url for url in unique}
        for f in as_completed(futures):
            checks[futures[f]] = f.result()

    channels = {}
    for url, raw in unique.items():
        result = checks.get(url)
        if not result:
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
            'latency': result['latency'], 'status': result['status'], 'hls': result['hls']
        })

    output = []
    for c in channels.values():
        c['sources'].sort(key=lambda x: x['latency'])
        c['sourceCount'] = len(c['sources'])
        c['url'] = c['sources'][0]['url']
        output.append(c)
    output.sort(key=lambda x: x['name'].lower())

    payload = {
        'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'count': len(output),
        'checkedUrls': len(unique),
        'healthyUrls': sum(x['sourceCount'] for x in output),
        'channels': output,
    }
    (DATA / 'catalog.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'BouyonTV: {len(unique)} URLs checked, {payload["healthyUrls"]} healthy sources, {len(output)} playable channels retained')


if __name__ == '__main__':
    main()

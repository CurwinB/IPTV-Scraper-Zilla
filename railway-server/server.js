import express from 'express';
import { Readable } from 'node:stream';

const OWNER = 'CurwinB';
const REPO = 'IPTV-Scraper-Zilla';
const REF = 'main';
const CATALOG_URL = `https://raw.githubusercontent.com/${OWNER}/${REPO}/${REF}/data/catalog.json`;
const CATALOG_TTL = 5 * 60 * 1000;

const PORT = process.env.PORT || 8080;

const app = express();
app.disable('x-powered-by');

app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,HEAD,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');
  if (req.method === 'OPTIONS') return res.status(204).end();
  next();
});

app.get('/', (req, res) => res.json({ ok: true, service: 'bouyontv-edge' }));
app.get('/health', (req, res) => res.status(200).send('ok'));

// --- /api/catalog: verified live channel list, cached in-process so repeat
// requests don't re-pull the 8MB+ catalogue from GitHub every time. ---
let catalogCache = { at: 0, data: null };

app.get('/api/catalog', async (req, res) => {
  if (catalogCache.data && Date.now() - catalogCache.at < CATALOG_TTL) {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=3600');
    return res.status(200).json(catalogCache.data);
  }

  try {
    const upstream = await fetch(CATALOG_URL, {
      headers: { 'User-Agent': 'BouyonTV/1.0', Accept: 'application/json' },
    });

    if (!upstream.ok) {
      if (catalogCache.data) return res.status(200).json(catalogCache.data);
      return res.status(503).json({ error: 'Verified BouyonTV catalogue is unavailable' });
    }

    const data = await upstream.json();
    const channels = Array.isArray(data.channels) ? data.channels : [];

    // Never expose an unvalidated/fallback playlist. If the generated catalogue
    // is empty or malformed, fail closed rather than showing unverified streams
    // (unless we have a previous good copy cached, in which case serve that).
    if (!channels.length || Number(data.count) !== channels.length || Number(data.healthyUrls) <= 0) {
      if (catalogCache.data) return res.status(200).json(catalogCache.data);
      return res.status(503).json({ error: 'Verified BouyonTV catalogue is not ready' });
    }

    const normalized = channels
      .filter(c => c && typeof c === 'object' && c.url)
      .map(c => ({
        id: c.id || c.name || c.url,
        name: String(c.name || c.id || 'Unknown').trim(),
        logo: c.logo || '',
        country: c.country || '',
        language: c.language || '',
        group: c.group || '',
        category: c.category || '',
        url: c.url,
        sourceCount: Number(c.sourceCount) || (Array.isArray(c.sources) ? c.sources.length : 1),
        sources: Array.isArray(c.sources)
          ? c.sources.filter(s => s && s.url).map(s => ({
              url: s.url,
              source: s.source || '',
              latency: Number(s.latency) || 0,
              hls: Boolean(s.hls),
            }))
          : [{ url: c.url, source: '', latency: 0, hls: true }],
      }));

    const payload = {
      version: data.version,
      updatedAt: data.updatedAt,
      count: normalized.length,
      checkedUrls: data.checkedUrls,
      healthyUrls: data.healthyUrls,
      channels: normalized,
    };
    catalogCache = { at: Date.now(), data: payload };

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=3600');
    return res.status(200).json(payload);
  } catch (error) {
    console.error('BouyonTV catalogue error:', error);
    if (catalogCache.data) return res.status(200).json(catalogCache.data);
    return res.status(502).json({ error: 'Unable to load verified BouyonTV catalogue' });
  }
});

// --- /api/stream: HLS proxy. Rewrites manifest URIs back through this same
// route so segments/keys are fetched through us too (CORS + mixed-content safe).
// Binary segments are piped straight through rather than buffered in memory. ---
app.get('/api/stream', async (req, res) => {
  const target = typeof req.query?.url === 'string' ? req.query.url : '';
  let url;
  try { url = new URL(target); } catch { return res.status(400).json({ error: 'Invalid URL' }); }
  if (!['http:', 'https:'].includes(url.protocol)) return res.status(400).json({ error: 'Unsupported protocol' });

  try {
    const upstream = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 IPTV Zilla Player' }, redirect: 'follow' });
    if (!upstream.ok) return res.status(upstream.status).send(`Upstream returned ${upstream.status}`);

    const type = upstream.headers.get('content-type') || '';
    const manifest = type.includes('mpegurl') || /\.m3u8(?:$|\?)/i.test(url.pathname + url.search);
    res.setHeader('Cache-Control', 'no-store');

    if (!manifest) {
      res.setHeader('Content-Type', type || 'application/octet-stream');
      const len = upstream.headers.get('content-length');
      if (len) res.setHeader('Content-Length', len);
      if (upstream.body) {
        Readable.fromWeb(upstream.body).pipe(res);
      } else {
        res.end(Buffer.from(await upstream.arrayBuffer()));
      }
      return;
    }

    const text = await upstream.text();
    const rewritten = text.split(/\r?\n/).map(line => {
      const t = line.trim();
      if (!t) return line;
      if (t.startsWith('#EXT-X-KEY:') || t.startsWith('#EXT-X-MAP:') || t.startsWith('#EXT-X-MEDIA:')) {
        return line.replace(/URI="([^"]+)"/g, (_, value) => `URI="/api/stream?url=${encodeURIComponent(new URL(value, url).href)}"`);
      }
      if (t.startsWith('#')) return line;
      try { return `/api/stream?url=${encodeURIComponent(new URL(t, url).href)}`; } catch { return line; }
    }).join('\n');
    res.setHeader('Content-Type', 'application/vnd.apple.mpegurl');
    return res.status(200).send(rewritten);
  } catch (e) {
    console.error(e);
    return res.status(502).json({ error: 'Unable to reach stream' });
  }
});

app.listen(PORT, () => console.log(`bouyontv-edge listening on :${PORT}`));

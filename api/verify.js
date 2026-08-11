const cache = globalThis.__bouyonVerifyCache || (globalThis.__bouyonVerifyCache = new Map());
const TTL = 10 * 60 * 1000;
const UA = 'BouyonTV/1.0';

function validUrl(value) { try { const u = new URL(value); return ['http:','https:'].includes(u.protocol) ? u : null; } catch { return null; } }

export default async function handler(req, res) {
  const target = typeof req.query?.url === 'string' ? req.query.url : '';
  const url = validUrl(target);
  if (!url) return res.status(400).json({ ok:false, error:'Invalid URL' });
  const key = url.href;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < TTL) return res.status(200).json(hit.value);

  const started = Date.now();
  try {
    const upstream = await fetch(url, { headers: { 'User-Agent': UA, Accept: '*/*' }, redirect:'follow' });
    const type = (upstream.headers.get('content-type') || '').toLowerCase();
    const finalUrl = upstream.url || url.href;
    const looksHls = type.includes('mpegurl') || /\.m3u8(?:$|\?)/i.test(finalUrl);
    let ok = upstream.ok;
    let bytes = 0;
    let sample = '';
    if (looksHls && upstream.ok) {
      const text = await upstream.text();
      bytes = text.length;
      sample = text.slice(0, 8192);
      ok = sample.includes('#EXTM3U');
    } else if (upstream.body) {
      const reader = upstream.body.getReader();
      const first = await reader.read();
      bytes = first.value?.byteLength || 0;
      try { await reader.cancel(); } catch {}
    }
    const value = { ok, status:upstream.status, latency:Date.now()-started, hls:looksHls, bytes, finalUrl };
    cache.set(key,{at:Date.now(),value});
    res.setHeader('Cache-Control','s-maxage=600, stale-while-revalidate=3600');
    return res.status(200).json(value);
  } catch (e) {
    const value={ok:false,status:0,latency:Date.now()-started,error:e.name||'NetworkError'};
    cache.set(key,{at:Date.now(),value});
    return res.status(200).json(value);
  }
}

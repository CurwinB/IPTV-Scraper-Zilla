export default async function handler(req, res) {
  const target = typeof req.query?.url === 'string' ? req.query.url : '';
  let url;
  try { url = new URL(target); } catch { return res.status(400).json({ error: 'Invalid URL' }); }
  if (!['http:','https:'].includes(url.protocol)) return res.status(400).json({ error: 'Unsupported protocol' });

  try {
    const upstream = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 IPTV Zilla Player' }, redirect: 'follow' });
    if (!upstream.ok) return res.status(upstream.status).send(`Upstream returned ${upstream.status}`);
    const type = upstream.headers.get('content-type') || '';
    const manifest = type.includes('mpegurl') || /\.m3u8(?:$|\?)/i.test(url.pathname + url.search);
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store');
    if (!manifest) {
      res.setHeader('Content-Type', type || 'application/octet-stream');
      return res.status(200).send(Buffer.from(await upstream.arrayBuffer()));
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
}
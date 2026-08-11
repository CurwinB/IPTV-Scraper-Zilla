const OWNER = 'CurwinB';
const REPO = 'IPTV-Scraper-Zilla';
const REF = 'main';
const CATALOG_URL = `https://raw.githubusercontent.com/${OWNER}/${REPO}/${REF}/data/catalog.json`;

export default async function handler(req, res) {
  try {
    const upstream = await fetch(CATALOG_URL, {
      headers: { 'User-Agent': 'BouyonTV/1.0', Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!upstream.ok) {
      return res.status(503).json({ error: 'Verified BouyonTV catalogue is unavailable' });
    }

    const data = await upstream.json();
    const channels = Array.isArray(data.channels) ? data.channels : [];

    // Never expose an unvalidated/fallback playlist. If the generated catalogue
    // is empty or malformed, fail closed rather than showing unverified streams.
    if (!channels.length || Number(data.count) !== channels.length || Number(data.healthyUrls) <= 0) {
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

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=3600');
    return res.status(200).json({
      version: data.version,
      updatedAt: data.updatedAt,
      count: normalized.length,
      checkedUrls: data.checkedUrls,
      healthyUrls: data.healthyUrls,
      channels: normalized,
    });
  } catch (error) {
    console.error('BouyonTV catalogue error:', error);
    return res.status(502).json({ error: 'Unable to load verified BouyonTV catalogue' });
  }
}

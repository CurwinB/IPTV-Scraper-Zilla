const API = 'https://api.themoviedb.org/3';
function endpoint(type, id, season, page) {
  if (type === 'search') return `/search/multi?query=${encodeURIComponent(id)}&include_adult=false&page=${page}`;
  if (type === 'search-movie') return `/search/movie?query=${encodeURIComponent(id)}&include_adult=false&page=${page}`;
  if (type === 'search-tv') return `/search/tv?query=${encodeURIComponent(id)}&include_adult=false&page=${page}`;
  if (type === 'movie') return `/movie/${encodeURIComponent(id)}?append_to_response=credits`;
  if (type === 'tv' || type === 'tv-details') return `/tv/${encodeURIComponent(id)}?append_to_response=credits`;
  if (type === 'season') return `/tv/${encodeURIComponent(id)}/season/${encodeURIComponent(season)}`;
  if (type === 'trending') return '/trending/all/week';
  if (type === 'popular-movies') return `/movie/popular?page=${page}`;
  if (type === 'popular-tv') return `/tv/popular?page=${page}`;
  return null;
}
export default async function handler(req, res) {
  const token = process.env.TMDB_READ_TOKEN || process.env.TMDB_API_TOKEN;
  if (!token) return res.status(503).json({ error: 'TMDB is not configured. Add TMDB_READ_TOKEN to Vercel.' });
  const type = String(req.query?.type || 'trending'), id = req.query?.id, season = req.query?.season;
  const page = Math.min(Math.max(parseInt(req.query?.page, 10) || 1, 1), 500);
  const path = endpoint(type, id, season, page);
  const needsId = ['search', 'search-movie', 'search-tv', 'movie', 'tv', 'tv-details', 'season'];
  if (!path || (needsId.includes(type) && !id)) return res.status(400).json({ error: 'Invalid TMDB request' });
  try {
    const r = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' } });
    const data = await r.json();
    if (!r.ok) return res.status(r.status).json({ error: data.status_message || 'TMDB request failed' });
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=3600');
    return res.status(200).json(data);
  } catch (e) { console.error('TMDB proxy error', e); return res.status(502).json({ error: 'Unable to reach TMDB' }); }
}

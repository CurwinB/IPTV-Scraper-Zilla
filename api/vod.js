const TMDB_BASE = 'https://api.themoviedb.org/3';
const IMAGE_BASE = 'https://image.tmdb.org/t/p/w500';

function token() {
  return process.env.TMDB_API_TOKEN || process.env.TMDB_API_KEY || '';
}

function cleanItem(item, type) {
  const id = item.id;
  const title = type === 'tv' ? item.name : item.title;
  const date = type === 'tv' ? item.first_air_date : item.release_date;
  return {
    id,
    tmdbId: id,
    type: type === 'tv' ? 'series' : 'movie',
    title: title || 'Untitled',
    year: date ? String(date).slice(0, 4) : '',
    overview: item.overview || '',
    poster: item.poster_path ? IMAGE_BASE + item.poster_path : '',
    backdrop: item.backdrop_path ? `https://image.tmdb.org/t/p/w1280${item.backdrop_path}` : '',
    rating: typeof item.vote_average === 'number' ? item.vote_average : null,
    genres: item.genre_ids || []
  };
}

async function tmdb(path, params = {}) {
  const t = token();
  if (!t) throw new Error('TMDB_API_TOKEN is not configured');
  const url = new URL(TMDB_BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') url.searchParams.set(k, v);
  });
  const r = await fetch(url, {
    headers: { Authorization: `Bearer ${t}`, accept: 'application/json' },
    cache: 'no-store'
  });
  if (!r.ok) throw new Error(`TMDB returned ${r.status}`);
  return r.json();
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
  try {
    const type = req.query.type === 'tv' ? 'tv' : 'movie';
    const action = req.query.action || 'popular';
    const page = Math.min(Math.max(Number(req.query.page) || 1, 1), 20);
    let data;

    if (action === 'search') {
      const q = String(req.query.q || '').trim();
      if (!q) return res.status(400).json({ error: 'Missing q' });
      data = await tmdb(`/search/${type}`, { query: q, page, include_adult: false, language: 'en-US' });
    } else if (action === 'trending') {
      data = await tmdb(`/trending/${type}/week`, { language: 'en-US' });
    } else if (action === 'details') {
      const id = String(req.query.id || '').replace(/[^0-9]/g, '');
      if (!id) return res.status(400).json({ error: 'Missing id' });
      data = await tmdb(`/${type}/${id}`, { language: 'en-US', append_to_response: 'credits' });
      if (type === 'tv') {
        return res.json({
          ...cleanItem(data, type),
          numberOfSeasons: data.number_of_seasons || 0,
          seasons: (data.seasons || []).filter(s => s.season_number > 0).map(s => ({ season: s.season_number, name: s.name, episodes: s.episode_count, poster: s.poster_path ? IMAGE_BASE + s.poster_path : '' }))
        });
      }
      return res.json(cleanItem(data, type));
    } else {
      data = await tmdb(`/discover/${type}`, {
        page,
        sort_by: 'popularity.desc',
        include_adult: false,
        language: 'en-US',
        include_video: false
      });
    }

    return res.json({
      page: data.page || page,
      totalPages: data.total_pages || 1,
      totalResults: data.total_results || 0,
      type,
      results: (data.results || []).map(item => cleanItem(item, type))
    });
  } catch (e) {
    return res.status(500).json({ error: e.message || 'VOD service unavailable' });
  }
};

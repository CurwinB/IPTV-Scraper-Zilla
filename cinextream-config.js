// Single source of truth for CineXtream playback.
// Anime language is part of the path: /api/embed/anime/sub|dub/[ANILIST_ID]/[EPISODE]
window.BOUYONTV_CINEXTREAM_BASE = 'https://cinextream.cc';

window.BouyonTVCineXtream = {
  movie: (tmdbId) => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/movie/${encodeURIComponent(tmdbId)}`,
  tv: (tmdbId, season = 1, episode = 1) => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/tv/${encodeURIComponent(tmdbId)}/${encodeURIComponent(season)}/${encodeURIComponent(episode)}`,
  anime: (anilistId, episode = 1, language = 'sub') => {
    const lang = String(language).toLowerCase() === 'dub' ? 'dub' : 'sub';
    return `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/anime/${lang}/${encodeURIComponent(anilistId)}/${encodeURIComponent(episode)}`;
  }
};

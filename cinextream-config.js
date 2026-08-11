// Single source of truth for CineXtream playback.
// Anime language is part of the path: /api/embed/anime/sub|dub/[ANILIST_ID]/[EPISODE]
window.BOUYONTV_CINEXTREAM_BASE = 'https://cinextream.cc';
window.BouyonTVCineXtream = {
  movie: id => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/movie/${encodeURIComponent(id)}`,
  tv: (id,s=1,e=1) => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/tv/${encodeURIComponent(id)}/${encodeURIComponent(s)}/${encodeURIComponent(e)}`,
  anime: (id,e=1,lang='sub') => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/anime/${String(lang).toLowerCase()==='dub'?'dub':'sub'}/${encodeURIComponent(id)}/${encodeURIComponent(e)}`
};

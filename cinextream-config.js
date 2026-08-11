// Single source of truth for CineXtream playback.
// Anime language is part of the path: /api/embed/anime/sub|dub/[ANILIST_ID]/[EPISODE]
window.BOUYONTV_CINEXTREAM_BASE = 'https://cinextream.cc';
window.BouyonTVCineXtream = {
  movie: id => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/movie/${encodeURIComponent(id)}`,
  tv: (id,s=1,e=1) => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/tv/${encodeURIComponent(id)}/${encodeURIComponent(s)}/${encodeURIComponent(e)}`,
  anime: (id,e=1,lang='sub') => `${window.BOUYONTV_CINEXTREAM_BASE}/api/embed/anime/${String(lang).toLowerCase()==='dub'?'dub':'sub'}/${encodeURIComponent(id)}/${encodeURIComponent(e)}`
};

// Mobile navigation already provides the Movies / TV Shows / Anime switcher.
// Hide the duplicate VOD tabs injected into the browse page on small screens only.
(() => {
  const css = document.createElement('style');
  css.id = 'bouyon-mobile-vod-nav-fix';
  css.textContent = '@media (max-width: 700px){.vod-tabs{display:none!important}}';
  document.head.appendChild(css);
})();

// BouyonTV VOD player: mounts CineXtream into the existing #frame container only.
(() => {
  const frame = document.getElementById('frame');
  const vod = document.getElementById('vod');
  const video = document.getElementById('video');
  const player = document.getElementById('player');
  const title = document.getElementById('title');
  const status = document.getElementById('status');
  if (!frame || !vod || !player) return;

  const CINE = 'https://cinextream.net';
  let active = false;

  const setStatus = (text, error = false) => {
    if (!status) return;
    status.textContent = text;
    status.className = 'status' + (error ? ' error' : '');
  };

  const showVOD = (url, name) => {
    active = true;
    // Do not touch the Live TV video element or its HLS instance.
    if (video) video.style.display = 'none';
    frame.src = 'about:blank';
    frame.style.display = 'block';
    frame.style.width = '100%';
    frame.style.height = '100%';
    frame.style.minHeight = '0';
    frame.style.border = '0';
    frame.style.position = 'absolute';
    frame.style.inset = '0';
    frame.setAttribute('allowfullscreen', '');
    frame.setAttribute('allow', 'autoplay; encrypted-media; fullscreen; picture-in-picture');
    frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    vod.style.display = 'block';
    vod.style.position = 'absolute';
    vod.style.inset = '0';
    vod.style.width = '100%';
    vod.style.height = '100%';
    player.classList.add('active');
    if (title) title.textContent = name || 'BouyonTV';
    setStatus('Loading player…');

    const fallback = () => {
      frame.src = 'about:blank';
      setStatus('CineXtream is currently unreachable. Please try again shortly.', true);
    };
    const timer = setTimeout(() => {
      if (active) setStatus('CineXtream is taking too long to respond. Please try again.', true);
    }, 15000);

    const onMessage = e => {
      if (e.source !== frame.contentWindow) return;
      let data = e.data;
      try { if (typeof data === 'string') data = JSON.parse(data); } catch { return; }
      if (!data || typeof data !== 'object') return;
      if (data.event === 'player_ready') {
        clearTimeout(timer);
        setStatus('Player ready');
      } else if (data.event === 'player_error') {
        clearTimeout(timer);
        setStatus(`CineXtream error: ${data.reason || 'Unable to play this title.'}`, true);
      } else if (data.event === 'complete' || data.event === 'VIDEO_ENDED') {
        setStatus('Playback complete');
      }
    };
    window.addEventListener('message', onMessage);
    frame.addEventListener('error', fallback, { once: true });
    frame.src = url;
  };

  const movie = (tmdbId, name) => showVOD(`${CINE}/api/embed/movie/${encodeURIComponent(tmdbId)}`, name);
  const tv = (tmdbId, season, episode, name) => showVOD(`${CINE}/api/embed/tv/${encodeURIComponent(tmdbId)}/${encodeURIComponent(season)}/${encodeURIComponent(episode)}`, name);
  const anime = (anilistId, episode, name) => showVOD(`${CINE}/api/anime/embed/lang/${encodeURIComponent(anilistId)}/${encodeURIComponent(episode)}`, name);

  window.__bouyonPlayMovie = movie;
  window.__bouyonPlayTV = tv;
  window.__bouyonPlayAnime = anime;
})();

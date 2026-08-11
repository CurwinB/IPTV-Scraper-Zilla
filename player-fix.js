// BouyonTV player hardening. Keeps Live TV playback on the native HLS player and
// keeps CineXtream isolated from the Live TV path.
(() => {
  const video = document.getElementById('video');
  const player = document.getElementById('player');
  const vod = document.getElementById('vod');
  const frame = document.getElementById('frame');
  const title = document.getElementById('title');
  const status = document.getElementById('status');
  if (!video || !player || !vod || !frame) return;

  let hls = null;
  let sources = [];
  let sourceIndex = 0;
  let current = null;

  const setStatus = (text, error = false) => {
    if (!status) return;
    status.textContent = text;
    status.className = 'status' + (error ? ' error' : '');
  };
  const showPlayer = () => {
    document.getElementById('home')?.style && (document.getElementById('home').style.display = 'none');
    document.getElementById('browse')?.style && (document.getElementById('browse').style.display = 'none');
    player.classList.add('active');
  };
  const destroy = () => {
    if (hls) { try { hls.destroy(); } catch {} hls = null; }
    video.pause();
    video.removeAttribute('src');
    video.load();
    frame.src = '';
    vod.style.display = 'none';
    video.style.display = 'block';
  };
  const proxy = url => `/api/stream?url=${encodeURIComponent(url)}`;

  async function playSource() {
    if (sourceIndex >= sources.length) {
      setStatus('This channel has no playable source right now.', true);
      return;
    }
    const original = sources[sourceIndex++];
    setStatus(`Connecting to source ${sourceIndex}/${sources.length}…`);
    const src = proxy(original);

    if (window.Hls && Hls.isSupported()) {
      hls = new Hls({ enableWorker: true, lowLatencyMode: true, backBufferLength: 15, maxBufferLength: 30 });
      hls.attachMedia(video);
      hls.once(Hls.Events.MEDIA_ATTACHED, () => hls.loadSource(src));
      hls.once(Hls.Events.MANIFEST_PARSED, () => {
        video.play().then(() => setStatus('Playing')).catch(() => setStatus('Ready — tap play'));
      });
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        try { hls.destroy(); } catch {}
        hls = null;
        setStatus(`Source ${sourceIndex} failed, trying next…`);
        setTimeout(playSource, 100);
      });
      return;
    }

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src;
      video.load();
      try { await video.play(); setStatus('Playing'); } catch { setStatus('Ready — tap play'); }
      video.onerror = () => playSource();
      return;
    }
    setStatus('HLS is not supported by this browser.', true);
  }

  async function playLive(channel) {
    showPlayer();
    destroy();
    current = channel;
    sources = [
      ...(Array.isArray(channel.sources) ? channel.sources.map(s => typeof s === 'string' ? s : s?.url) : []),
      channel.url
    ].filter(Boolean).filter((u, i, a) => a.indexOf(u) === i);
    sourceIndex = 0;
    title.textContent = channel.name || 'Live TV';
    if (!sources.length) return setStatus('No stream URL is available for this channel.', true);
    await playSource();
  }

  // Capture Live TV clicks before the older inline player handler. This prevents
  // VOD UI code from taking over the Live TV player.
  document.addEventListener('click', e => {
    const card = e.target.closest('.live-card');
    if (!card) return;
    const id = card.dataset.id;
    const source = window.__bouyonChannels?.find(c => String(c.id) === String(id) || String(c.name) === String(id));
    if (!source) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    playLive(source);
  }, true);

  window.__bouyonPlayLive = playLive;
  window.addEventListener('bouyon:channels', e => {
    if (Array.isArray(e.detail)) window.__bouyonChannels = e.detail;
  });
})();

(function(){
  function findLiveChannel(channels,id){return channels.find(c=>String(c.id||c.name)===String(id))}
  async function dispatch(route){
    const R=window.bouyonRouter;
    if(!R)return;
    if(!route||route.mode==='home'){R.showHome();return}
    if(route.mode==='browse'){R.showBrowse(route.browse);return}
    if(route.mode==='movie'){
      try{const d=await R.fetchMovie(route.id);d.media_type='movie';await R.playMovieOrTVAt(d,1,1)}
      catch(e){R.showHome()}
      return;
    }
    if(route.mode==='tv'){
      try{const d=await R.fetchTV(route.id);d.media_type='tv';await R.playMovieOrTVAt(d,Number(route.season)||1,Number(route.episode)||1)}
      catch(e){R.showHome()}
      return;
    }
    if(route.mode==='anime'){
      try{const x=await R.fetchAnimeById(route.id);R.playAnime(x,Number(route.episode)||1,'sub')}
      catch(e){R.showHome()}
      return;
    }
    if(route.mode==='live'){
      try{
        const channels=await R.ensureLiveChannels();
        const c=findLiveChannel(channels,route.id);
        if(c&&typeof window.playLive==='function')window.playLive(c);
        else R.showBrowse('live');
      }catch(e){R.showHome()}
      return;
    }
    R.showHome();
  }
  dispatch(window.BouyonRoute);
  window.addEventListener('popstate',function(){
    dispatch(window.bouyonParseRoute(location.pathname));
  });
})();

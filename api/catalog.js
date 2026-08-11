const owner = 'CurwinB';
const repo = 'IPTV-Scraper-Zilla';
const ref = 'main';

async function github(path = '') {
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${ref}`;
  const r = await fetch(url, { headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'BouyonTV' } });
  if (!r.ok) throw new Error(`GitHub API ${r.status}`);
  return r.json();
}

function attr(text, key) { const m = text.match(new RegExp(`${key}=\"([^\"]*)\"`, 'i')); return m ? m[1].trim() : ''; }
function parse(text, source) {
  const out=[]; let meta=null;
  for (const line of text.split(/\r?\n/)) {
    const t=line.trim();
    if(t.startsWith('#EXTINF:')){const comma=t.indexOf(',');const head=comma>=0?t.slice(0,comma):t;const name=comma>=0?t.slice(comma+1).trim():'';meta={id:attr(head,'tvg-id'),name,logo:attr(head,'tvg-logo'),group:attr(head,'group-title'),country:attr(head,'tvg-country'),language:attr(head,'tvg-language'),source};}
    else if(meta && /^https?:\/\//i.test(t)){out.push({...meta,url:t});meta=null;}
  } return out;
}

export default async function handler(req,res){
  try {
    // Prefer the GitHub Actions-produced, health-checked catalogue. This keeps Vercel fast.
    const cached=await fetch(`https://raw.githubusercontent.com/${owner}/${repo}/${ref}/data/catalog.json`,{headers:{'User-Agent':'BouyonTV'}});
    if(cached.ok){const data=await cached.json();res.setHeader('Cache-Control','s-maxage=300, stale-while-revalidate=3600');return res.status(200).json(data);}

    // Fallback for the first deployment before the scheduled workflow has produced data.
    const files=await github(); const playlists=files.filter(x=>x.type==='file'&&/\.(m3u8?|txt)$/i.test(x.name)); const rows=[];
    for(const file of playlists){try{const r=await fetch(file.download_url,{headers:{'User-Agent':'BouyonTV'}});if(r.ok)rows.push(...parse(await r.text(),file.name));}catch(e){console.warn(file.name,e.message);}}
    const map=new Map();
    for(const c of rows){const name=(c.name||c.id||'Unknown').replace(/\s+/g,' ').trim();const key=`${(c.id||name).toLowerCase()}|${c.country}|${c.language}`;if(!map.has(key))map.set(key,{id:c.id||name,name,logo:c.logo,country:c.country,language:c.language,group:c.group,sources:[]});const x=map.get(key);if(!x.logo&&c.logo)x.logo=c.logo;if(!x.group&&c.group)x.group=c.group;if(!x.sources.some(s=>s.url===c.url))x.sources.push({url:c.url,source:c.source});}
    const channels=[...map.values()].map(c=>({...c,sourceCount:c.sources.length,url:c.sources[0]?.url||''}));res.setHeader('Cache-Control','s-maxage=300, stale-while-revalidate=3600');res.status(200).json({updatedAt:new Date().toISOString(),count:channels.length,channels});
  }catch(e){console.error(e);res.status(502).json({error:'Unable to load BouyonTV catalogue'});}
}
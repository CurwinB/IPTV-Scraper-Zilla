const owner = 'CurwinB';
const repo = 'IPTV-Scraper-Zilla';
const ref = 'main';

const skip = new Set(['.gitignore','README.md','LICENSE','vercel.json']);

async function github(path = '') {
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${ref}`;
  const r = await fetch(url, { headers: { 'Accept': 'application/vnd.github+json', 'User-Agent': 'IPTV-Zilla-Vercel' } });
  if (!r.ok) throw new Error(`GitHub API ${r.status}`);
  return r.json();
}

function parse(text, source) {
  const out=[]; let meta=null;
  for (const line of text.split(/\r?\n/)) {
    const t=line.trim();
    if (t.startsWith('#EXTINF:')) {
      const comma=t.indexOf(',');
      const attrs=comma>=0?t.slice(0,comma):t;
      const name=comma>=0?t.slice(comma+1).trim():'';
      const get=k=>{const m=attrs.match(new RegExp(`${k}="([^"]*)"`,'i'));return m?m[1]:''};
      meta={id:get('tvg-id'),name,logo:get('tvg-logo'),group:get('group-title'),country:get('tvg-country'),language:get('tvg-language'),source};
    } else if (meta && /^https?:\/\//i.test(t)) { out.push({...meta,url:t}); meta=null; }
  }
  return out;
}

export default async function handler(req,res) {
  try {
    const files=await github();
    const playlists=files.filter(x=>x.type==='file' && /\.(m3u8?|txt)$/i.test(x.name) && !skip.has(x.name));
    const results=[];
    for (const file of playlists) {
      const r=await fetch(file.download_url,{headers:{'User-Agent':'IPTV-Zilla-Vercel'}});
      if (!r.ok) continue;
      const text=await r.text();
      results.push(...parse(text,file.name));
    }
    const seen=new Set(), channels=results.filter(c=>{const k=`${c.name}|${c.url}`;if(seen.has(k))return false;seen.add(k);return true;});
    res.setHeader('Access-Control-Allow-Origin','*');
    res.setHeader('Cache-Control','s-maxage=300, stale-while-revalidate=3600');
    res.status(200).json({updatedAt:new Date().toISOString(),count:channels.length,channels});
  } catch(e) { console.error(e); res.status(502).json({error:'Unable to build IPTV catalogue'}); }
}
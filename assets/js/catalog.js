const cache = new Map();
async function json(path, version) {
  const url = new URL(path, document.baseURI);
  if (version) url.searchParams.set('v', version);
  const key = url.href;
  if (!cache.has(key)) cache.set(key, fetch(key, {cache: version ? 'default' : 'no-cache'}).then(async response => {
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }).catch(error => { cache.delete(key); throw error; }));
  return cache.get(key);
}
export async function manifest() {
  const data = await json('data/manifest.json');
  if (data.schema_version !== 1) throw new Error('Unsupported catalog schema');
  return data;
}
export async function dataset(name) {
  const data = await manifest();
  if (!data.files[name]) throw new Error(`Missing dataset: ${name}`);
  return json(data.files[name], data.dataset_version);
}
export async function record(id) {
  const data = await manifest();
  const chunk = Object.values(data.chunks).flat().find(item => item.ids ? item.ids.includes(id) : typeof id === 'string' && item.first_id <= id && id <= item.last_id);
  if (!chunk) return null;
  const rows = await json(chunk.path, data.dataset_version);
  const item = rows.find(row => row.id === id);
  return item || null;
}

export async function queryCatalog(criteria, limit, {onProgress = () => {}, cancelled = () => false} = {}) {
  const [data, index] = await Promise.all([manifest(), dataset('search_index')]);
  const {normalize} = await import('./utils.js');
  const query = normalize(criteria.q);
  const queryX = query.replace(/[×✕✖]/g, 'x');
  const querySpace = query.replace(/[×✕✖]/g, ' ');
  const queryCompact = query.replace(/[^a-z0-9]+/g, '');
  const queryXCompact = queryX.replace(/[^a-z0-9]+/g, '');
  const tokens = querySpace.split(/\s+/).filter(Boolean);

  const matchTitle = row => {
    if (!query) return true;
    const target = normalize([row.title, row.original_title, ...(row.aliases || [])].join(' '));
    if (target.includes(query)) return true;

    const targetX = target.replace(/[×✕✖]/g, 'x');
    if (targetX.includes(queryX)) return true;

    const targetSpace = target.replace(/[×✕✖]/g, ' ');
    if (targetSpace.includes(querySpace)) return true;

    const targetCompact = target.replace(/[^a-z0-9]+/g, '');
    if (queryCompact && targetCompact.includes(queryCompact)) return true;

    const targetXCompact = targetX.replace(/[^a-z0-9]+/g, '');
    if (queryXCompact && targetXCompact.includes(queryXCompact)) return true;

    if (tokens.length > 1 && tokens.every(token => targetSpace.includes(token))) return true;

    return false;
  };

  const matches = row => matchTitle(row)
    && (!criteria.type || row.type === criteria.type)
    && (!criteria.genre || (row.genres || []).includes(criteria.genre))
    && (!criteria.year || String(row.year) === criteria.year)
    && (!criteria.language || (row.languages || []).includes(criteria.language))
    && (!criteria.country || [...(row.countries || []),...(row.broadcast_countries || [])].includes(criteria.country));
  const compare = (a,b) => {
    if (criteria.sort === 'title') return a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
    if (criteria.sort === 'release_date') return (b.release_date || '').localeCompare(a.release_date || '') || a.id.localeCompare(b.id);
    return (b.rating ?? -1) - (a.rating ?? -1) || a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
  };
  if (Array.isArray(index)) return {rows:index.filter(matches).sort(compare),complete:true};
  const shards = index.shards.filter(shard => (!criteria.type || shard.type === criteria.type)
    && (!criteria.genre || shard.facets.genres.includes(criteria.genre))
    && (!criteria.year || shard.facets.years.includes(Number(criteria.year)))
    && (!criteria.language || shard.facets.languages.includes(criteria.language))
    && (!criteria.country || [...shard.facets.countries,...shard.facets.broadcast_countries].includes(criteria.country)))
    .sort((a,b) => b.max_rating-a.max_rating || a.path.localeCompare(b.path));
  const found=[];
  for (let offset=0;offset<shards.length;offset+=4) {
    if (cancelled()) return null;
    const batch=shards.slice(offset,offset+4);
    const results=await Promise.all(batch.map(shard=>json(shard.path,data.dataset_version)));
    for (const rows of results) found.push(...rows.filter(matches));
    if (cancelled()) return null;
    onProgress(Math.min(offset+4,shards.length),shards.length);
    // Rating bounds allow a globally correct first page without fetching every shard.
    // All equal-rated candidates are still read to resolve title ordering correctly.
    const next=shards[offset+4];
    if (criteria.sort === 'rating' && found.length>limit && next) {
      found.sort(compare);
      if ((found[limit-1].rating ?? -1) > next.max_rating) return {rows:found,complete:false};
    }
  }
  return {rows:found.sort(compare),complete:true};
}

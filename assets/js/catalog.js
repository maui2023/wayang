const cache = new Map();
async function json(path, version) {
  const url = new URL(path, document.baseURI);
  if (version) url.searchParams.set('v', version);
  const key = url.href;
  if (!cache.has(key)) cache.set(key, fetch(key).then(async response => {
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
  const chunk = Object.values(data.chunks).flat().find(item => item.ids.includes(id));
  if (!chunk) return null;
  const rows = await json(chunk.path, data.dataset_version);
  const item = rows.find(row => row.id === id);
  if (!item) throw new Error('Catalog index/chunk mismatch');
  return item;
}

import {dataset, manifest} from './catalog.js';
import {grid} from './components.js';
import {escapeHTML as e, normalize, labels} from './utils.js';
export async function init(container) {
  const [rows, catalog] = await Promise.all([dataset('search_index'), manifest()]);
  const params = new URLSearchParams(location.search);
  const unique = key => [...new Set(rows.flatMap(row => row[key] ?? []))].sort();
  const select = (name, label, values) => `<div class="col-6 col-lg"><label for="${name}">${label}</label><select class="form-select" id="${name}" name="${name}"><option value="">Semua</option>${values.map(value => `<option value="${e(value)}">${e(labels[value] || value)}</option>`).join('')}</select></div>`;
  container.innerHTML = `<form class="filter-panel" id="filters"><div class="row g-3"><div class="col-12"><label for="q">Cari tajuk atau nama asal</label><input class="form-control" type="search" id="q" name="q" placeholder="Cari tajuk pilihan anda" autocomplete="off"></div>${select('type','Jenis',['movie','tv','anime'])}${select('genre','Genre',unique('genres'))}${select('year','Tahun',unique('year').reverse())}${select('language','Bahasa',unique('languages'))}<div class="col-6 col-lg"><label for="sort">Susun mengikut</label><select class="form-select" id="sort" name="sort"><option value="rating">Rating tertinggi</option><option value="title">Tajuk A–Z</option><option value="release_date">Terbaharu</option></select></div></div><div class="d-flex gap-2 mt-3"><button type="submit" class="btn btn-primary">Terapkan</button><button type="reset" class="btn btn-outline-light">Set semula</button></div></form><p id="result-count" role="status" class="muted small"></p><div id="results"></div><div class="text-center mt-4"><button id="more" class="btn btn-outline-light" type="button">Muatkan lagi</button></div>`;
  const form = container.querySelector('form');
  for (const name of ['q','type','genre','year','language','sort']) if (params.has(name)) form.elements[name].value = params.get(name);
  if (!form.elements.sort.value) form.elements.sort.value = 'rating';
  let limit = 12, filtered = [];
  const render = () => {
    const target = container.querySelector('#results');
    target.replaceChildren();
    if (filtered.length) target.append(grid(filtered.slice(0,limit)));
    else if (form.elements.type.value === 'movie' && !catalog.counts.movie) target.innerHTML = '<section class="empty"><h2>Katalog filem belum tersedia.</h2><p class="muted">Koleksi semasa merangkumi siri TV dan anime. Pilih jenis lain untuk terus meneroka.</p></section>';
    else target.innerHTML = '<section class="empty"><h2>Belum ada cerita yang sepadan.</h2><p class="muted">Cuba tajuk lain atau kurangkan penapis anda.</p></section>';
    container.querySelector('#result-count').textContent = `${filtered.length} cerita ditemui · ${Math.min(filtered.length,limit)} dipaparkan${catalog.is_demo ? ' · Data demo' : ''}`;
    container.querySelector('#more').hidden = filtered.length <= limit;
  };
  const apply = (writeURL = true) => {
    limit = 12;
    const values = Object.fromEntries(new FormData(form));
    const query = normalize(values.q);
    filtered = rows.filter(row => (!query || normalize([row.title,row.original_title,...(row.aliases || [])].join(' ')).includes(query)) && (!values.type || row.type === values.type) && (!values.genre || row.genres.includes(values.genre)) && (!values.year || String(row.year) === values.year) && (!values.language || row.languages.includes(values.language)));
    filtered.sort((a,b) => {
      if (values.sort === 'title') return a.title.localeCompare(b.title);
      if (values.sort === 'release_date') return (b.release_date || '').localeCompare(a.release_date || '') || a.id.localeCompare(b.id);
      return (b[values.sort] ?? -1) - (a[values.sort] ?? -1) || a.title.localeCompare(b.title);
    });
    if (writeURL) { const next = new URLSearchParams(); Object.entries(values).forEach(([key,value]) => {if (value) next.set(key,value);}); history.replaceState(null,'',`${location.pathname}?${next}`); }
    document.title = `${query ? `Carian: ${values.q}` : 'Katalog'} · MovieHub`;
    render();
  };
  form.addEventListener('submit', event => {event.preventDefault();apply();});
  form.addEventListener('change', () => apply());
  let timer; form.elements.q.addEventListener('input', () => {clearTimeout(timer);timer=setTimeout(apply,200);});
  form.addEventListener('reset', () => {clearTimeout(timer);setTimeout(() => apply(),0);});
  container.querySelector('#more').addEventListener('click', () => {limit+=12;render();});
  apply(false);
}

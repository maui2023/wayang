import {dataset, manifest, queryCatalog} from './catalog.js';
import {grid} from './components.js';
import {escapeHTML as e, labels, showError} from './utils.js';
const countryNames = new Intl.DisplayNames(['ms'], {type:'region'});
const countryName = value => { try { return countryNames.of(value); } catch { return value; } };
export async function init(container) {
  const [index, catalog] = await Promise.all([dataset('search_index'), manifest()]);
  const params = new URLSearchParams(location.search);
  const facets = Array.isArray(index) ? Object.fromEntries(['genres','languages','countries','broadcast_countries'].map(key=>[key,[...new Set(index.flatMap(row=>row[key] || []))].sort()])) : index.facets;
  const years = Array.isArray(index) ? [...new Set(index.map(row=>row.year).filter(Boolean))].sort((a,b)=>b-a) : [...facets.years].sort((a,b)=>b-a);
  const countries = [...new Set([...(facets.countries || []),...(facets.broadcast_countries || [])])].sort();
  const select = (name,label,values,display = value => labels[value] || value) => `<div class="col-6 col-lg"><label for="${name}">${label}</label><select class="form-select" id="${name}" name="${name}"><option value="">Semua</option>${values.map(value=>`<option value="${e(value)}">${e(display(value))}</option>`).join('')}</select></div>`;
  container.innerHTML = `<form class="filter-panel" id="filters"><div class="row g-3"><div class="col-12"><label for="q">Cari tajuk atau nama asal</label><input class="form-control" type="search" id="q" name="q" placeholder="Cari tajuk pilihan anda" autocomplete="off"></div>${select('type','Jenis',['movie','tv','anime'])}${select('country','Negara / wilayah',countries,countryName)}${select('genre','Genre',facets.genres)}${select('year','Tahun',years)}${select('language','Bahasa',facets.languages)}<div class="col-6 col-lg"><label for="sort">Susun mengikut</label><select class="form-select" id="sort" name="sort"><option value="rating">Rating tertinggi</option><option value="title">Tajuk A–Z</option><option value="release_date">Terbaharu</option></select></div></div><p class="small muted mt-3 mb-0">Negara filem mengikut asal produksi; wilayah siri TV mengikut rangkaian penyiar yang direkodkan. Rekod tanpa maklumat wilayah masih tersedia dalam “Semua”.</p><div class="d-flex gap-2 mt-3"><button type="submit" class="btn btn-primary">Terapkan</button><button type="reset" class="btn btn-outline-light">Set semula</button></div></form><p id="result-count" role="status" class="muted small"></p><div id="results"></div><div class="text-center mt-4"><button id="more" class="btn btn-outline-light" type="button" hidden>Muatkan lagi</button></div>`;
  const form=container.querySelector('form'), results=container.querySelector('#results'), status=container.querySelector('#result-count'), more=container.querySelector('#more');
  for (const name of ['q','type','country','genre','year','language','sort']) if (params.has(name)) form.elements[name].value=params.get(name);
  if (!form.elements.sort.value) form.elements.sort.value='rating';
  let limit=12, revision=0, timer;
  async function apply(writeURL=true, reset=true) {
    const current=++revision;
    if (reset) limit=12;
    const values=Object.fromEntries(new FormData(form));
    if (writeURL) {const next=new URLSearchParams();Object.entries(values).forEach(([key,value])=>{if(value)next.set(key,value);});history.replaceState(null,'',`${location.pathname}?${next}`);}
    document.title=`${values.q ? `Carian: ${values.q}` : 'Katalog'} · MovieHub`;
    more.hidden=true;results.setAttribute('aria-busy','true');status.textContent='Mencari dalam katalog…';
    if(reset)results.innerHTML='<p class="loading">Memuatkan cerita…</p>';
    try {
      const answer=await queryCatalog(values,limit,{cancelled:()=>current!==revision,onProgress:(done,total)=>{if(current===revision)status.textContent=`Menyemak katalog… ${Math.round(done/total*100)}%`;}});
      if(current!==revision || !answer)return;
      results.replaceChildren();results.removeAttribute('aria-busy');
      if(answer.rows.length)results.append(grid(answer.rows.slice(0,limit)));
      else results.innerHTML='<section class="empty"><h2>Belum ada cerita yang sepadan.</h2><p class="muted">Cuba tajuk lain atau kurangkan penapis anda.</p></section>';
      const count=Math.min(answer.rows.length,limit);
      status.textContent=answer.complete ? `${answer.rows.length.toLocaleString('ms')} cerita ditemui · ${count} dipaparkan` : `${count} cerita dipaparkan · Muatkan lagi untuk terus meneroka`;
      if(catalog.is_demo)status.textContent+=' · Data demo';
      more.hidden=answer.complete && answer.rows.length<=limit;
    } catch(error) {if(current!==revision)return;results.removeAttribute('aria-busy');status.textContent='Carian belum selesai.';showError(results,error);}
  }
  form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);apply();});
  form.addEventListener('change',()=>{clearTimeout(timer);apply();});
  form.elements.q.addEventListener('input',()=>{clearTimeout(timer);revision++;timer=setTimeout(()=>apply(),300);});
  form.addEventListener('reset',()=>{clearTimeout(timer);revision++;setTimeout(()=>apply(),0);});
  more.addEventListener('click',()=>{limit+=12;apply(false,false);});
  await apply(false);
}

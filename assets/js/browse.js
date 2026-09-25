import {dataset, manifest, queryCatalog} from './catalog.js';
import {grid} from './components.js';
import {escapeHTML as e, labels, showError} from './utils.js';
import {getLang, t, countryDisplayName} from './i18n.js';

export async function init(container) {
  const [index, catalog] = await Promise.all([dataset('search_index'), manifest()]);
  const lang = getLang();
  const params = new URLSearchParams(location.search);
  const facets = Array.isArray(index) ? Object.fromEntries(['genres','languages','countries','broadcast_countries'].map(key=>[key,[...new Set(index.flatMap(row=>row[key] || []))].sort()])) : index.facets;
  const years = Array.isArray(index) ? [...new Set(index.map(row=>row.year).filter(Boolean))].sort((a,b)=>b-a) : [...facets.years].sort((a,b)=>b-a);
  const countries = [...new Set([...(facets.countries || []),...(facets.broadcast_countries || [])])].sort();
  const select = (name,label,values,display = value => labels[value] || value) => `<div class="col-6 col-lg"><label for="${name}">${label}</label><select class="form-select" id="${name}" name="${name}"><option value="">${e(t('browse.all'))}</option>${values.map(value=>`<option value="${e(value)}">${e(display(value))}</option>`).join('')}</select></div>`;
  container.innerHTML = `<form class="filter-panel" id="filters"><div class="row g-3"><div class="col-12"><label for="q">${e(t('browse.search_label'))}</label><input class="form-control" type="search" id="q" name="q" placeholder="${e(t('browse.search_placeholder'))}" autocomplete="off"></div>${select('type',t('browse.type'),['movie','tv','anime'])}${select('country',t('browse.country'),countries,countryDisplayName)}${select('genre',t('browse.genre'),facets.genres)}${select('year',t('browse.year'),years)}${select('language',t('browse.language'),facets.languages)}<div class="col-6 col-lg"><label for="sort">${e(t('browse.sort'))}</label><select class="form-select" id="sort" name="sort"><option value="rating">${e(t('browse.sort_rating'))}</option><option value="title">${e(t('browse.sort_title'))}</option><option value="release_date">${e(t('browse.sort_release'))}</option></select></div></div><p class="small muted mt-3 mb-0">${e(t('browse.region_note'))}</p><div class="d-flex gap-2 mt-3"><button type="submit" class="btn btn-primary">${e(t('browse.apply'))}</button><button type="reset" class="btn btn-outline-light">${e(t('browse.reset'))}</button></div></form><p id="result-count" role="status" class="muted small"></p><div id="results"></div><div class="text-center mt-4"><button id="more" class="btn btn-outline-light" type="button" hidden>${e(t('browse.load_more'))}</button></div>`;
  const form=container.querySelector('form'), results=container.querySelector('#results'), status=container.querySelector('#result-count'), more=container.querySelector('#more');
  for (const name of ['q','type','country','genre','year','language','sort']) if (params.has(name)) form.elements[name].value=params.get(name);
  if (!form.elements.sort.value) form.elements.sort.value='rating';
  let limit=12, revision=0, timer;
  async function apply(writeURL=true, reset=true) {
    const current=++revision;
    if (reset) limit=12;
    const values=Object.fromEntries(new FormData(form));
    if (writeURL) {const next=new URLSearchParams();Object.entries(values).forEach(([key,value])=>{if(value)next.set(key,value);});if (params.has('lang')) next.set('lang', params.get('lang'));history.replaceState(null,'',`${location.pathname}?${next}`);}
    document.title=`${values.q ? t('browse.search_title', {q: values.q}) : t('browse.title')} · MovieHub`;
    more.hidden=true;results.setAttribute('aria-busy','true');status.textContent=t('browse.searching');
    if(reset)results.innerHTML=`<p class="loading">${e(t('browse.loading'))}</p>`;
    try {
      const answer=await queryCatalog(values,limit,{cancelled:()=>current!==revision,onProgress:(done,total)=>{if(current===revision)status.textContent=t('browse.checking', {percent: Math.round(done/total*100)});}});
      if(current!==revision || !answer)return;
      results.replaceChildren();results.removeAttribute('aria-busy');
      if(answer.rows.length)results.append(grid(answer.rows.slice(0,limit)));
      else results.innerHTML=`<section class="empty"><h2>${e(t('browse.empty_heading'))}</h2><p class="muted">${e(t('browse.empty_sub'))}</p></section>`;
      const count=Math.min(answer.rows.length,limit);
      const numLocale = lang === 'ms' ? 'ms' : 'en';
      status.textContent=answer.complete ? t('browse.results_complete', {total: answer.rows.length.toLocaleString(numLocale), count: count.toLocaleString(numLocale)}) : t('browse.results_partial', {count: count.toLocaleString(numLocale)});
      if(catalog.is_demo)status.textContent+=t('browse.demo_data');
      more.hidden=answer.complete && answer.rows.length<=limit;
    } catch(error) {if(current!==revision)return;results.removeAttribute('aria-busy');status.textContent=t('browse.error');showError(results,error);}
  }
  form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);apply();});
  form.addEventListener('change',()=>{clearTimeout(timer);apply();});
  form.elements.q.addEventListener('input',()=>{clearTimeout(timer);revision++;timer=setTimeout(()=>apply(),300);});
  form.addEventListener('reset',()=>{clearTimeout(timer);revision++;setTimeout(()=>apply(),0);});
  more.addEventListener('click',()=>{limit+=12;apply(false,false);});
  await apply(false);
}

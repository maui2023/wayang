import {showError, escapeHTML as e, safeURL} from './utils.js';
import {manifest} from './catalog.js';
import {getLang, setLang, t} from './i18n.js';

const lang = getLang();
document.documentElement.lang = (lang === 'ms' ? 'ms' : 'en');
const skipLink = document.querySelector('.skip-link');
if (skipLink) skipLink.textContent = t('skip_link');

document.querySelectorAll('[data-i18n]').forEach(el => {
  const key = el.dataset.i18n;
  if (key) el.textContent = t(key);
});
document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
  const key = el.dataset.i18nPlaceholder;
  if (key) el.placeholder = t(key);
});

const page = document.body.dataset.page;
if (page === 'index') {
  document.title = `${t('nav.explore')} · MovieHub`;
} else if (page === 'browse' && !location.search) {
  document.title = `${t('browse.title')} · MovieHub`;
} else if (page === '404') {
  document.title = `${t('404.title')} · MovieHub`;
}
document.querySelector('#header').innerHTML = `<nav class="navbar navbar-expand-lg"><div class="container"><a class="navbar-brand" href="index.html"><span class="brand-icon" aria-hidden="true">◧</span>MovieHub<span class="small" style="color:var(--accent)">.</span></a><button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navigation" aria-controls="navigation" aria-expanded="false" aria-label="${e(t('nav.toggle'))}"><span class="navbar-toggler-icon"></span></button><div class="collapse navbar-collapse" id="navigation"><ul class="navbar-nav mx-auto gap-lg-3"><li class="nav-item"><a class="nav-link ${page==='index'?'active':''}" href="index.html" ${page==='index'?'aria-current="page"':''}>${e(t('nav.explore'))}</a></li><li class="nav-item"><a class="nav-link" href="browse.html?type=movie">${e(t('nav.movies'))}</a></li><li class="nav-item"><a class="nav-link" href="browse.html?type=tv">${e(t('nav.tv'))}</a></li><li class="nav-item"><a class="nav-link" href="browse.html?type=anime">${e(t('nav.anime'))}</a></li></ul><div class="d-flex align-items-center gap-2 mt-3 mt-lg-0"><form action="search.html" role="search" class="d-flex gap-2 mb-0"><label class="visually-hidden" for="global-search">${e(t('nav.search_label'))}</label><input id="global-search" class="form-control form-control-sm" name="q" type="search" placeholder="${e(t('nav.search_placeholder'))}"><button class="btn btn-outline-light btn-sm" type="submit">${e(t('nav.search_btn'))}</button></form><div class="btn-group btn-group-sm lang-toggle ms-1" role="group" aria-label="${e(t('nav.lang'))}"><button type="button" class="btn btn-sm ${lang==='en'?'btn-primary':'btn-outline-light'} px-2 fw-bold" data-lang="en">EN</button><button type="button" class="btn btn-sm ${lang==='ms'?'btn-primary':'btn-outline-light'} px-2 fw-bold" data-lang="ms">BM</button></div></div></div></div></nav>`;

document.querySelectorAll('.lang-toggle button').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.dataset.lang !== lang) {
      setLang(btn.dataset.lang);
    }
  });
});

document.querySelector('#footer').innerHTML = `<div class="d-flex flex-wrap justify-content-between gap-3"><div><strong class="text-light">MovieHub.</strong><p class="mt-2 mb-0">${e(t('footer.tagline'))}</p></div><div>${e(t('footer.desc'))}<br><span id="attribution"></span><br>${e(t('footer.no_video'))}</div><a href="browse.html">${e(t('footer.explore_link'))}</a></div>`;
const modules = {index:'home',browse:'browse',search:'browse',details:'details'};
if (modules[page]) { const content=document.querySelector('#content'); try { const module=await import(`./${modules[page]}.js`); await module.init(content); } catch(error) {showError(content,error);} }

try {
  const catalog = await manifest();
  document.querySelector('#attribution').innerHTML = catalog.is_demo ? e(t('footer.demo_attr')) : (catalog.attributions || []).map(source => {
    const url = safeURL(source.url), license = safeURL(source.license_url);
    return `${e(t('footer.adapted_from'))} ${url ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(source.name)}</a>` : e(source.name)} · ${license ? `<a href="${e(license)}" target="_blank" rel="noopener noreferrer">${e(source.license)}</a>` : e(source.license)}<br>${e(t('footer.reorganized_by'))}`;
  }).join('<br>');
} catch { /* Page loader already reports catalog failures. */ }

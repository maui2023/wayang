import {showError, escapeHTML as e, safeURL} from './utils.js';
import {manifest} from './catalog.js';
const page = document.body.dataset.page;
document.querySelector('#header').innerHTML = `<nav class="navbar navbar-expand-lg"><div class="container"><a class="navbar-brand" href="index.html"><span class="brand-icon" aria-hidden="true">◧</span>MovieHub<span class="small" style="color:var(--accent)">.</span></a><button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navigation" aria-controls="navigation" aria-expanded="false" aria-label="Buka navigasi"><span class="navbar-toggler-icon"></span></button><div class="collapse navbar-collapse" id="navigation"><ul class="navbar-nav mx-auto gap-lg-3"><li class="nav-item"><a class="nav-link ${page==='index'?'active':''}" href="index.html" ${page==='index'?'aria-current="page"':''}>Terokai</a></li><li class="nav-item"><a class="nav-link" href="browse.html?type=movie">Filem</a></li><li class="nav-item"><a class="nav-link" href="browse.html?type=tv">Siri TV</a></li><li class="nav-item"><a class="nav-link" href="browse.html?type=anime">Anime</a></li></ul><form action="search.html" role="search" class="d-flex gap-2"><label class="visually-hidden" for="global-search">Cari cerita</label><input id="global-search" class="form-control form-control-sm" name="q" type="search" placeholder="Cari cerita…"><button class="btn btn-outline-light btn-sm" type="submit">Cari</button></form></div></div></nav>`;
document.querySelector('#footer').innerHTML = '<div class="d-flex flex-wrap justify-content-between gap-3"><div><strong class="text-light">MovieHub.</strong><p class="mt-2 mb-0">Cerita baharu. Perspektif baharu.</p></div><div>Katalog penemuan filem, TV & anime.<br><span id="attribution"></span><br>Tiada video penuh dihoskan di sini.</div><a href="browse.html">Terokai katalog ↗</a></div>';
const modules = {index:'home',browse:'browse',search:'browse',details:'details'};
if (modules[page]) { const content=document.querySelector('#content'); try { const module=await import(`./${modules[page]}.js`); await module.init(content); } catch(error) {showError(content,error);} }

try {
  const catalog = await manifest();
  document.querySelector('#attribution').innerHTML = catalog.is_demo ? 'Demo menggunakan metadata rekaan dan artwork asal.' : (catalog.attributions || []).map(source => {
    const url = safeURL(source.url), license = safeURL(source.license_url);
    return `Metadata diadaptasi daripada ${url ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(source.name)}</a>` : e(source.name)} · ${license ? `<a href="${e(license)}" target="_blank" rel="noopener noreferrer">${e(source.license)}</a>` : e(source.license)}<br>Disusun semula oleh MovieHub. Artwork daripada sumber asal.`;
  }).join('<br>');
} catch { /* Page loader already reports catalog failures. */ }

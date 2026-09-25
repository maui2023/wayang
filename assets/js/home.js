import {dataset, record, manifest} from './catalog.js';
import {section} from './components.js';
import {escapeHTML as e, image, showError, labels} from './utils.js';
export async function init(container) {
  const [featured, catalog] = await Promise.all([dataset('featured'), manifest()]);
  const title = await record(featured.hero);
  container.replaceChildren();
  if (title) {
    const hero = document.createElement('section'); hero.className = 'hero';
    hero.append(image(title.backdrop?.url || title.poster?.original_url || title.poster?.url, '', 'hero-art', true));
    const copy = document.createElement('div'); copy.className = 'hero-copy';
    const summary = title.overview || 'Temui cerita pilihan anda.';
    copy.innerHTML = `<p class="eyebrow">PILIHAN KATALOG${catalog.is_demo ? ' / EDISI DEMO' : ''}</p><h1>${e(title.title)}</h1><div class="meta"><span class="rating">★ ${e(title.rating?.value ?? '—')}</span><span>${e(title.year ?? '—')}</span><span>${e(labels[title.type])}</span><span>${e((title.genres || []).join(' / '))}</span>${title.runtime_minutes ? `<span>${e(title.runtime_minutes)} min</span>` : ''}</div><p class="overview">${e(summary.length > 220 ? summary.slice(0,217) + '…' : summary)}</p><a class="btn btn-primary" href="details.html?id=${encodeURIComponent(title.id)}">Terokai cerita <span aria-hidden="true">↗</span></a>`;
    hero.append(copy); container.append(hero);
  }
  const intro = document.createElement('div');
  const count = Object.values(catalog.counts).reduce((sum,n) => sum+n,0);
  intro.innerHTML = `<p class="notice">${catalog.is_demo ? 'Katalog demo · Semua tajuk, sinopsis dan rating ialah data rekaan untuk pembangunan.' : `${count.toLocaleString("ms")} cerita sebenar · Filem, siri TV dan anime · Metadata mengikut sumber asal.`}</p><nav class="category-links" aria-label="Kategori"><a href="browse.html">Semua cerita ↗</a>${Object.entries(catalog.counts).filter(([,n]) => n > 0).map(([type]) => `<a href="browse.html?type=${type}">${e(labels[type])}</a>`).join('')}${['MY','ID','TH'].map((country,i)=>`<a href="browse.html?country=${country}">${['Malaysia','Indonesia','Thailand'][i]}</a>`).join('')}</nav>`;
  container.append(intro);
  for (const collection of featured.collections) {
    if (!collection.items.length) continue;
    const slot = document.createElement('div'); container.append(slot);
    try { slot.append(section(collection.title, collection.items, `browse.html?type=${collection.type}${collection.country ? `&country=${collection.country}` : ""}`)); }
    catch (error) { showError(slot, error); }
  }
}

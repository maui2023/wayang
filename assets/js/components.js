import {escapeHTML as e, image, labels} from './utils.js';
export function card(row) {
  const article = document.createElement('article'); article.className = 'media-card';
  article.innerHTML = `<a href="details.html?id=${encodeURIComponent(row.id)}"><div class="poster-wrap"><span class="poster-type">${e(labels[row.type])}</span></div><h3>${e(row.title)}</h3><div class="card-meta"><span>${e(row.year || 'Tahun —')} · ${e(labels[row.type])}</span><span class="rating">${row.rating == null ? '—' : `★ ${e(row.rating)}`}</span></div></a>`;
  article.querySelector('.poster-wrap').prepend(image(row.poster, `Poster ${row.title}`));
  return article;
}
export function grid(rows) { const element = document.createElement('div'); element.className = 'media-grid'; rows.forEach(row => element.append(card(row))); return element; }
export function section(title, rows, href) {
  const section = document.createElement('section');
  section.innerHTML = `<div class="section-head"><h2>${e(title)}</h2><a href="${e(href)}">Lihat semua ↗</a></div>`;
  section.append(grid(rows)); return section;
}

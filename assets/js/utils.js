import {getLang, t, translations} from './i18n.js';

export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export const normalize = value => String(value ?? '').normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
export const labels = new Proxy({}, {
  get(target, prop) {
    const lang = getLang();
    return translations[lang]?.[`type.${prop}`] ?? translations['en']?.[`type.${prop}`] ?? prop;
  }
});
export function safeURL(value) {
  if (!value) return null;
  try { const url = new URL(value, document.baseURI); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
}
export function image(url, alt, className = '', eager = false) {
  const img = document.createElement('img');
  img.src = safeURL(url) || 'assets/img/fallback.svg'; img.alt = alt; img.className = className;
  img.loading = eager ? 'eager' : 'lazy'; img.decoding = 'async';
  img.addEventListener('error', () => { img.src = 'assets/img/fallback.svg'; }, {once:true});
  return img;
}
export function showError(container, error) {
  console.error('MovieHub:', error);
  container.innerHTML = `<section class="empty" role="alert"><h2>${escapeHTML(t('error.heading'))}</h2><p>${escapeHTML(t('error.sub'))}</p><button class="btn btn-outline-light" type="button">${escapeHTML(t('error.retry'))}</button></section>`;
  container.querySelector('button').addEventListener('click', () => location.reload());
}

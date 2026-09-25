export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export const normalize = value => String(value ?? '').normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
export const labels = {movie:'Filem',tv:'Siri TV',anime:'Anime'};
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
  container.innerHTML = '<section class="empty" role="alert"><h2>Katalog belum dapat dimuatkan.</h2><p>Sila cuba semula sebentar lagi.</p><button class="btn btn-outline-light" type="button">Cuba semula</button></section>';
  container.querySelector('button').addEventListener('click', () => location.reload());
}

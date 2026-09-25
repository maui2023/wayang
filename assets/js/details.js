import {record} from './catalog.js';
import {escapeHTML as e, image, labels, safeURL} from './utils.js';
import {trailerButton} from './trailer.js';
import {getLang, t, countryDisplayName} from './i18n.js';

export async function init(container) {
  const lang = getLang();
  const title = await record(new URLSearchParams(location.search).get('id'));
  if (!title) {
    container.innerHTML = `<section class="empty"><h1>${e(t('details.not_found_heading'))}</h1><p>${e(t('details.not_found_desc'))}</p><a class="btn btn-primary" href="browse.html">${e(t('details.not_found_btn'))}</a></section>`;
    document.title = t('details.not_found_title');
    return;
  }
  document.title = `${title.title} · MovieHub`;
  const countries = title.countries?.map(c => countryDisplayName(c)).join(', ');
  const broadcastCountries = title.broadcast_countries?.map(c => countryDisplayName(c)).join(', ');
  const facts = [
    [t('details.release_date'), title.release_date],
    [t('details.genres'), title.genres?.join(', ')],
    [t('details.languages'), title.languages?.join(', ')],
    [t('details.country_origin'), countries],
    [t('details.broadcast_country'), broadcastCountries],
    [t('details.episode_runtime'), title.series?.episode_runtime_minutes ? t('details.minutes', {n: title.series.episode_runtime_minutes}) : null],
    [t('details.runtime'), title.runtime_minutes ? t('details.minutes', {n: title.runtime_minutes}) : null],
    [t('details.series'), title.series ? [title.series.seasons && t('details.seasons', {n: title.series.seasons}), title.series.episodes && `${t('details.episodes', {n: title.series.episodes})}${title.sources.some(source => source.provider === "tvmaze") ? t('details.ordered') : ""}`].filter(Boolean).join(' · ') : null],
    [t('details.status'), title.status],
    [t('details.rating'), title.rating ? `${title.rating.value}/${title.rating.scale} · ${title.rating.votes != null ? `${t('details.votes', {n: title.rating.votes})} · ` : ''}${title.rating.source}` : null],
    ...Object.entries(title.external_ids || {}).map(([key,value]) => [key.toUpperCase(),value])
  ].filter(([,value]) => value);
  container.innerHTML = `<a class="d-inline-block muted mb-4" href="browse.html">${e(t('details.back'))}</a><div class="row g-4 g-lg-5"><div class="col-md-4" id="poster"></div><div class="col-md-8 detail-copy"><p class="eyebrow">${e(labels[title.type])} / ${e(title.year ?? '—')}</p><h1>${e(title.title)}</h1>${title.original_title && title.original_title !== title.title ? `<p class="muted">${e(title.original_title)}</p>` : ''}<p class="notice">${title.sources.some(s => s.provider === 'original-fixture') ? e(t('details.demo_badge')) : e(t('details.info_source'))}</p><p class="mt-4">${e(title.overview || t('details.no_overview'))}</p><div id="trailer-action" class="my-4"></div><dl class="detail-facts">${facts.map(([label,value]) => `<div><dt>${e(label)}</dt><dd>${e(value)}</dd></div>`).join('')}</dl><p class="small muted mt-4">${e(t('details.sources'))} ${title.sources.map(source => safeURL(source.url) ? `<a href="${e(safeURL(source.url))}" target="_blank" rel="noopener noreferrer">${e(source.provider)}</a>${safeURL(source.license_url) ? ` · <a href="${e(safeURL(source.license_url))}" target="_blank" rel="noopener noreferrer">${e(source.license)}</a>` : ''}` : e(source.provider)).join(', ')}</p></div></div>`;
  container.querySelector('#poster').append(image(title.poster?.original_url || title.poster?.url, `Poster ${title.title}`, 'detail-poster', true));
  container.querySelector('#trailer-action').append(trailerButton(title.trailer));
}

import {dataset, record, manifest} from './catalog.js';
import {section} from './components.js';
import {escapeHTML as e, image, showError, labels} from './utils.js';
export async function init(container) {
  const [featured, catalog] = await Promise.all([dataset('featured'), manifest()]);
  let heroList = featured.hero_items;
  if (!heroList || !heroList.length) {
    if (featured.heroes && featured.heroes.length) {
      heroList = (await Promise.all(featured.heroes.slice(0, 10).map(hid => record(hid)))).filter(Boolean);
    } else if (featured.hero) {
      const single = await record(featured.hero);
      if (single) heroList = [single];
    }
  }

  container.replaceChildren();

  if (heroList && heroList.length) {
    const heroSection = document.createElement('section');
    heroSection.className = 'hero hero-slider';
    heroSection.setAttribute('aria-roledescription', 'carousel');
    heroSection.setAttribute('aria-label', 'Pilihan Katalog Terkini');

    const track = document.createElement('div');
    track.className = 'hero-track';

    heroList.forEach((title, idx) => {
      const slide = document.createElement('div');
      slide.className = `hero-slide ${idx === 0 ? 'active' : ''}`;
      slide.setAttribute('role', 'group');
      slide.setAttribute('aria-roledescription', 'slide');
      slide.setAttribute('aria-label', `${idx + 1} daripada ${heroList.length}`);
      slide.setAttribute('aria-hidden', idx !== 0);

      const art = image(
        title.backdrop?.url || title.poster?.original_url || title.poster?.url,
        '',
        'hero-art',
        idx === 0
      );
      slide.append(art);

      const copy = document.createElement('div');
      copy.className = 'hero-copy';
      const summary = title.overview || 'Temui cerita pilihan anda.';
      const typeLabel = labels[title.type] || title.type;
      copy.innerHTML = `<p class="eyebrow">PILIHAN KATALOG · ${e(typeLabel.toUpperCase())}${catalog.is_demo ? ' / EDISI DEMO' : ''}</p><h1>${e(title.title)}</h1><div class="meta"><span class="rating">★ ${e(title.rating?.value ?? '—')}</span><span>${e(title.year ?? '—')}</span><span class="badge-type">${e(typeLabel)}</span><span>${e((title.genres || []).join(' / '))}</span>${title.runtime_minutes ? `<span>${e(title.runtime_minutes)} min</span>` : ''}</div><p class="overview">${e(summary.length > 220 ? summary.slice(0, 217) + '…' : summary)}</p><a class="btn btn-primary" href="details.html?id=${encodeURIComponent(title.id)}" ${idx !== 0 ? 'tabindex="-1"' : ''}>Terokai cerita <span aria-hidden="true">↗</span></a>`;
      slide.append(copy);
      track.append(slide);
    });

    heroSection.append(track);

    if (heroList.length > 1) {
      const prevBtn = document.createElement('button');
      prevBtn.type = 'button';
      prevBtn.className = 'hero-arrow hero-prev';
      prevBtn.setAttribute('aria-label', 'Slaid sebelumnya');
      prevBtn.innerHTML = '<span aria-hidden="true">❮</span>';

      const nextBtn = document.createElement('button');
      nextBtn.type = 'button';
      nextBtn.className = 'hero-arrow hero-next';
      nextBtn.setAttribute('aria-label', 'Slaid seterusnya');
      nextBtn.innerHTML = '<span aria-hidden="true">❯</span>';

      heroSection.append(prevBtn, nextBtn);

      const indicators = document.createElement('div');
      indicators.className = 'hero-indicators';
      indicators.setAttribute('role', 'tablist');
      indicators.setAttribute('aria-label', 'Navigasi slaid');

      const dots = heroList.map((item, i) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.role = 'tab';
        dot.className = `hero-dot ${i === 0 ? 'active' : ''}`;
        dot.setAttribute('aria-selected', i === 0);
        dot.setAttribute('aria-label', `Slaid ${i + 1}: ${item.title}`);
        dot.setAttribute('tabindex', i === 0 ? '0' : '-1');
        dot.addEventListener('click', () => {
          goToSlide(i);
          startTimer();
        });
        indicators.append(dot);
        return dot;
      });

      heroSection.append(indicators);

      let currentIndex = 0;
      let timer = null;
      const total = heroList.length;

      function goToSlide(index) {
        currentIndex = (index + total) % total;
        track.style.transform = `translateX(-${currentIndex * 100}%)`;

        const slides = track.querySelectorAll('.hero-slide');
        slides.forEach((s, i) => {
          const active = i === currentIndex;
          s.classList.toggle('active', active);
          s.setAttribute('aria-hidden', !active);
          s.querySelectorAll('a, button').forEach(el => {
            el.setAttribute('tabindex', active ? '0' : '-1');
          });
        });

        dots.forEach((dot, i) => {
          const active = i === currentIndex;
          dot.classList.toggle('active', active);
          dot.setAttribute('aria-selected', active);
          dot.setAttribute('tabindex', active ? '0' : '-1');
        });
      }

      function startTimer() {
        stopTimer();
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
          timer = setInterval(() => {
            goToSlide(currentIndex + 1);
          }, 5000);
        }
      }

      function stopTimer() {
        if (timer) {
          clearInterval(timer);
          timer = null;
        }
      }

      prevBtn.addEventListener('click', () => {
        goToSlide(currentIndex - 1);
        startTimer();
      });

      nextBtn.addEventListener('click', () => {
        goToSlide(currentIndex + 1);
        startTimer();
      });

      heroSection.addEventListener('mouseenter', stopTimer);
      heroSection.addEventListener('mouseleave', startTimer);
      heroSection.addEventListener('focusin', stopTimer);
      heroSection.addEventListener('focusout', startTimer);

      heroSection.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') {
          e.preventDefault();
          goToSlide(currentIndex - 1);
          startTimer();
        } else if (e.key === 'ArrowRight') {
          e.preventDefault();
          goToSlide(currentIndex + 1);
          startTimer();
        }
      });

      let touchStartX = 0;
      heroSection.addEventListener('touchstart', (e) => {
        if (e.changedTouches && e.changedTouches.length) {
          touchStartX = e.changedTouches[0].screenX;
        }
        stopTimer();
      }, {passive: true});

      heroSection.addEventListener('touchend', (e) => {
        if (e.changedTouches && e.changedTouches.length) {
          const touchEndX = e.changedTouches[0].screenX;
          const diff = touchEndX - touchStartX;
          if (Math.abs(diff) > 40) {
            goToSlide(diff < 0 ? currentIndex + 1 : currentIndex - 1);
          }
        }
        startTimer();
      }, {passive: true});

      startTimer();
    }

    container.append(heroSection);
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

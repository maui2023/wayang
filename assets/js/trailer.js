export function validTrailer(trailer) {
  return trailer?.provider === 'youtube' && trailer.official === true && /^[A-Za-z0-9_-]{11}$/.test(trailer.video_id);
}
export function trailerButton(trailer) {
  const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-primary';
  button.textContent = validTrailer(trailer) ? '▷ Tonton trailer' : 'Trailer belum tersedia'; button.disabled = !validTrailer(trailer);
  button.addEventListener('click', () => {
    let modal = document.getElementById('trailer-modal');
    if (!modal) {
      modal = document.createElement('div'); modal.id = 'trailer-modal'; modal.className = 'modal fade'; modal.tabIndex = -1;
      modal.setAttribute('aria-labelledby', 'trailer-heading');
      modal.innerHTML = '<div class="modal-dialog modal-dialog-centered modal-xl"><div class="modal-content"><div class="modal-header"><h2 id="trailer-heading" class="modal-title fs-5">Trailer rasmi</h2><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Tutup trailer"></button></div><div class="modal-body"><div class="ratio ratio-16x9"></div><p class="small text-secondary mt-3 mb-0">Dimainkan melalui YouTube. Video mungkin terhad mengikut wilayah atau tetapan pemilik.</p></div></div></div>';
      document.body.append(modal);
      modal.addEventListener('hide.bs.modal', () => modal.querySelector('.ratio').replaceChildren());
      modal.addEventListener('hidden.bs.modal', () => button.focus());
    }
    const frame = document.createElement('iframe'); frame.title = trailer.title || 'Trailer rasmi';
    frame.src = `https://www.youtube-nocookie.com/embed/${trailer.video_id}?autoplay=1`;
    frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen'; frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    modal.querySelector('.ratio').replaceChildren(frame);
    bootstrap.Modal.getOrCreateInstance(modal).show();
  });
  return button;
}

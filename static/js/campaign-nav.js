(function () {
  'use strict';

  var header = document.querySelector('.gh-campaign-header');
  if (!header) {
    return;
  }

  var SCROLL_THRESHOLD = 32;
  var ticking = false;

  function setHeaderOffset() {
    if (!document.querySelector('.gh-campaign-hero-nav-only')) {
      return;
    }
    document.body.style.setProperty('--gh-campaign-header-offset', header.offsetHeight + 'px');
  }

  function applyScrolledState() {
    header.classList.toggle('gh-campaign-nav-scrolled', window.scrollY > SCROLL_THRESHOLD);
    ticking = false;
  }

  function onScroll() {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(applyScrolledState);
    }
  }

  setHeaderOffset();
  applyScrolledState();
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', setHeaderOffset, { passive: true });
})();

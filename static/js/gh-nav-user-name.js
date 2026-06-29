/**
 * Shorten navbar user display name when it would push the brand onto its own row.
 * 1) Drop words from the end (last space first): "Daveed Benjamin" → "Daveed"
 * 2) If still wrapping on one token, mid-word ellipsis: "DaveedBenjamin" → "DaveedBenj..."
 */
(function () {
  'use strict';

  var DESKTOP_MQ = window.matchMedia('(min-width: 992px)');
  var resizeTimer;

  function navbarLayoutWraps(navbar) {
    var brand = navbar.querySelector('.navbar-brand');
    var collapse = navbar.querySelector('.navbar-collapse');
    if (!brand) return false;
    var br = brand.getBoundingClientRect();
    if (collapse) {
      var cr = collapse.getBoundingClientRect();
      return cr.top > br.top + 8;
    }
    var msAuto = navbar.querySelector('.navbar-nav.ms-auto');
    if (!msAuto) return false;
    var mr = msAuto.getBoundingClientRect();
    return mr.top > br.top + 8;
  }

  function fitUserNavName(link) {
    if (link.querySelector('.gh-profile-nav-icon')) return;
    var fullName = (link.getAttribute('data-gh-full-name') || link.textContent || '').trim();
    if (!fullName) return;

    var navbar = link.closest('.navbar');
    if (!navbar || !DESKTOP_MQ.matches) {
      link.textContent = fullName;
      link.setAttribute('title', fullName);
      return;
    }

    link.setAttribute('title', fullName);

    function setText(text) {
      link.textContent = text;
    }

    var candidate = fullName;
    setText(candidate);
    if (!navbarLayoutWraps(navbar)) return;

    while (candidate.indexOf(' ') !== -1 && navbarLayoutWraps(navbar)) {
      candidate = candidate.slice(0, candidate.lastIndexOf(' ')).trim();
      setText(candidate);
    }
    if (!navbarLayoutWraps(navbar)) return;

    candidate = candidate.replace(/\s+/g, '');
    if (!candidate) {
      setText(fullName);
      return;
    }
    setText(candidate);
    if (!navbarLayoutWraps(navbar)) return;

    var ellipsis = '...';
    for (var len = candidate.length - 1; len >= 4; len--) {
      setText(candidate.slice(0, len) + ellipsis);
      if (!navbarLayoutWraps(navbar)) return;
    }
  }

  function fitAll() {
    document.querySelectorAll('.gh-user-nav-name').forEach(fitUserNavName);
  }

  function scheduleFit() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(fitAll, 80);
  }

  function init() {
    fitAll();
    window.addEventListener('load', scheduleFit);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(scheduleFit);
    }
    requestAnimationFrame(function () {
      requestAnimationFrame(fitAll);
    });
    window.addEventListener('resize', scheduleFit);
    if (DESKTOP_MQ.addEventListener) {
      DESKTOP_MQ.addEventListener('change', scheduleFit);
    } else if (DESKTOP_MQ.addListener) {
      DESKTOP_MQ.addListener(scheduleFit);
    }
    var collapse = document.getElementById('navbarNav');
    if (collapse) {
      collapse.addEventListener('shown.bs.collapse', scheduleFit);
      collapse.addEventListener('hidden.bs.collapse', scheduleFit);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

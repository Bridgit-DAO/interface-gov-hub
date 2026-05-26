/**
 * Return navigation for draft read pages:
 * - Annotate same-origin /read/ links with ?return_to=<current page>
 * - Expose ghReadUrl() for programmatic navigation
 * - On read pages, set Back from return_to or same-origin referrer
 */
(function (global) {
  'use strict';

  function safeReturnPath(raw) {
    if (!raw || typeof raw !== 'string') return null;
    var path = raw.trim();
    if (!path.startsWith('/') || path.startsWith('//')) return null;
    return path;
  }

  function currentReturnTo() {
    return global.location.pathname + global.location.search;
  }

  function isDraftReadPath(pathname) {
    return /\/doc\/draft\/[^/]+\/read\/?$/.test(pathname || '');
  }

  function ghReadUrl(draftRef, returnTo) {
    var ref = String(draftRef || '').trim();
    if (!ref) return '/doc/all/';
    var url = '/doc/draft/' + encodeURIComponent(ref) + '/read/';
    var back = safeReturnPath(returnTo) || currentReturnTo();
    if (back) {
      url += '?return_to=' + encodeURIComponent(back);
    }
    return url;
  }

  function annotateReadLink(anchor) {
    if (!anchor || anchor.getAttribute('data-gh-no-return') != null) return;
    var href = anchor.getAttribute('href');
    if (!href || href.indexOf('/read/') === -1) return;
    try {
      var url = new URL(href, global.location.href);
      if (url.origin !== global.location.origin) return;
      if (!isDraftReadPath(url.pathname)) return;
      if (url.searchParams.has('return_to')) return;
      var back = currentReturnTo();
      if (isDraftReadPath(back.split('?')[0])) return;
      url.searchParams.set('return_to', back);
      anchor.setAttribute('href', url.pathname + url.search + url.hash);
    } catch (_e) {
      /* ignore malformed href */
    }
  }

  function bindReadLinkCapture() {
    document.addEventListener('click', function (ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest('a[href*="/read/"]') : null;
      if (!a) return;
      annotateReadLink(a);
    });
  }

  function applyDraftReaderBack() {
    var back = document.querySelector('.draft-reader-nav a.btn');
    if (!back) return;
    var params = new URLSearchParams(global.location.search);
    var ret = safeReturnPath(params.get('return_to'));
    if (ret) {
      back.setAttribute('href', ret);
      return;
    }
    var ref = document.referrer;
    if (!ref) return;
    try {
      var refUrl = new URL(ref);
      if (refUrl.origin !== global.location.origin) return;
      if (isDraftReadPath(refUrl.pathname)) return;
      back.setAttribute('href', refUrl.pathname + refUrl.search);
    } catch (_e2) {
      /* ignore */
    }
  }

  global.ghReadUrl = ghReadUrl;
  bindReadLinkCapture();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyDraftReaderBack);
  } else {
    applyDraftReaderBack();
  }
})(window);

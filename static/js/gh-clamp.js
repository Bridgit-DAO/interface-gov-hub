/**
 * GovHub card description clamp helper.
 *
 * Targets every `[data-gh-clamp-10]` description element. If its
 * `scrollHeight` exceeds `clientHeight` (i.e. it overflows the line-clamp),
 * the corresponding `[data-gh-more]` link is revealed so users can read the
 * full description on the workgroup detail page. When the content fits in
 * 10 lines, the clamp class is removed so the description is never
 * visually clipped and the "More" link stays hidden.
 */
(function () {
  'use strict';

  function apply() {
    var nodes = document.querySelectorAll('[data-gh-clamp-10]');
    if (!nodes.length) return;
    nodes.forEach(function (el) {
      // Reset to measure intrinsic height with no clamp applied.
      el.classList.remove('gh-clamp-10');
      // Force a synchronous layout reflow so clientHeight reflects the
      // un-clamped content height.
      var natural = el.scrollHeight;
      var visible = el.clientHeight;
      var overflows = natural > visible + 1;
      if (overflows) {
        el.classList.add('gh-clamp-10');
      }
      var more = el.parentElement && el.parentElement.querySelector('[data-gh-more]');
      if (more) {
        if (overflows) {
          more.removeAttribute('hidden');
        } else {
          more.setAttribute('hidden', '');
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }

  // Re-run when workgroup cards are injected dynamically (layer detail
  // page renders its grid client-side after a fetch).
  window.addEventListener('load', apply);
})();
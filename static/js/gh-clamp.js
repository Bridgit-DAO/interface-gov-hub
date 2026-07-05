/**
 * GovHub card description clamp helper.
 *
 * Targets every `[data-gh-clamp-6]` description element. Measures the
 * natural (un-clamped) height, applies the `.gh-clamp-6` class (which
 * uses `-webkit-line-clamp: 6`), and only keeps the clamp when the
 * natural height exceeds the clamped height — i.e. when the description
 * would overflow 6 lines. When the content fits naturally in 6 lines,
 * the clamp class is removed so the description is never visually
 * clipped and the "More" link stays hidden.
 *
 * The previous implementation measured `scrollHeight` while the clamp
 * class was already applied (or absent on first run), which always
 * reported "fits, no clamp needed" and so the clamp never engaged.
 */
(function () {
  'use strict';

  function apply() {
    var nodes = document.querySelectorAll('[data-gh-clamp-6]');
    if (!nodes.length) return;
    nodes.forEach(function (el) {
      // Ensure no clamp while we measure the un-clamped height.
      el.classList.remove('gh-clamp-6');
      // Force a synchronous layout reflow.
      var naturalHeight = el.scrollHeight;

      // Now apply the clamp and re-measure.
      el.classList.add('gh-clamp-6');
      var clampedHeight = el.clientHeight;

      var overflows = naturalHeight > clampedHeight + 1;
      if (!overflows) {
        el.classList.remove('gh-clamp-6');
      }

      var parent = el.parentElement;
      var more = parent && parent.querySelector('[data-gh-more]');
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

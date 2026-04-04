/**
 * Legacy shim: Civic Mason and the shell use `static/js/govhub-i18n.js`.
 * `CMI18n` is assigned there as an alias for `GovHubI18n`.
 * Load govhub-i18n.js before any script that references CMI18n.
 */
(function (g) {
    'use strict';
    if (g.GovHubI18n && !g.CMI18n) {
        g.CMI18n = g.GovHubI18n;
    }
})(typeof window !== 'undefined' ? window : this);

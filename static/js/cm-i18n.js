/**
 * Client-side i18n for Civic Mason (and similar pages).
 * Loads JSON from /static/i18n/civic-mason/{locale}.json
 */
(function (global) {
    'use strict';

    var RTL_LANGS = ['ar', 'he', 'fa', 'ur', 'yi', 'ku', 'dv'];

    function getByPath(obj, path) {
        if (!obj || !path) return undefined;
        var parts = path.split('.');
        var cur = obj;
        for (var i = 0; i < parts.length; i++) {
            if (cur == null || typeof cur !== 'object') return undefined;
            cur = cur[parts[i]];
        }
        return cur;
    }

    function interpolate(str, vars) {
        if (!vars || typeof str !== 'string') return str;
        return str.replace(/\{\{(\w+)\}\}/g, function (_, k) {
            return vars[k] != null ? String(vars[k]) : '';
        });
    }

    var CMI18n = {
        locale: 'en',
        messages: {},

        t: function (key, vars) {
            var v = getByPath(this.messages, key);
            if (typeof v !== 'string') return key;
            return interpolate(v, vars);
        },

        isRtl: function () {
            var base = (this.locale || 'en').split('-')[0].toLowerCase();
            return RTL_LANGS.indexOf(base) !== -1;
        },

        formatNumber: function (n) {
            try {
                return new Intl.NumberFormat(this.locale).format(n);
            } catch (e) {
                return String(n);
            }
        },

        /** Format a calendar year in UTC (for policy copy). */
        formatYearUtc: function (year) {
            try {
                return new Intl.DateTimeFormat(this.locale, {
                    year: 'numeric',
                    timeZone: 'UTC',
                }).format(new Date(Date.UTC(Number(year), 5, 15)));
            } catch (e) {
                return String(year);
            }
        },

        nextUtcCalendarYear: function () {
            return new Date().getUTCFullYear() + 1;
        },

        applyDom: function (root) {
            if (!root || !root.querySelectorAll) return;
            root.querySelectorAll('[data-cm-i18n]').forEach(function (el) {
                var key = el.getAttribute('data-cm-i18n');
                if (key) el.textContent = CMI18n.t(key);
            });
            root.querySelectorAll('[data-cm-i18n-placeholder]').forEach(function (el) {
                var key = el.getAttribute('data-cm-i18n-placeholder');
                if (key) el.setAttribute('placeholder', CMI18n.t(key));
            });
            root.querySelectorAll('[data-cm-i18n-aria]').forEach(function (el) {
                var key = el.getAttribute('data-cm-i18n-aria');
                if (key) el.setAttribute('aria-label', CMI18n.t(key));
            });
            root.querySelectorAll('[data-cm-i18n-title]').forEach(function (el) {
                var key = el.getAttribute('data-cm-i18n-title');
                if (key) el.setAttribute('title', CMI18n.t(key));
            });
        },

        setRtlOnRoot: function () {
            var root = document.getElementById('civic-mason-page');
            if (!root) return;
            var rtl = this.isRtl();
            root.setAttribute('dir', rtl ? 'rtl' : 'ltr');
            root.classList.toggle('cm-rtl', rtl);
        },

        /**
         * @param {string} locale - BCP 47 tag, e.g. en, ar
         * @param {string} jsonBaseUrl - URL prefix ending before locale.json (e.g. /static/i18n/civic-mason/)
         */
        init: async function (locale, jsonBaseUrl) {
            this.locale = locale || 'en';
            var base = jsonBaseUrl || '/static/i18n/civic-mason/';

            async function load(loc) {
                var url = base + (loc || 'en') + '.json';
                var r = await fetch(url, { credentials: 'same-origin' });
                if (r.ok) return r.json();
                return null;
            }

            var data = await load(this.locale);
            if (!data) data = await load('en');
            this.messages = data || {};
            this.setRtlOnRoot();
            this.applyDom(document.getElementById('civic-mason-page') || document.body);
            return this;
        },

        /** Map API error_code to translated toast; fallback to error string. */
        apiErrorMessage: function (data) {
            var code = (data && data.error_code) || 'UNKNOWN';
            var msg = this.t('api.errors.' + code);
            if (msg === 'api.errors.' + code) {
                return (data && data.error) || this.t('api.errors.UNKNOWN');
            }
            return msg;
        },
    };

    global.CMI18n = CMI18n;
})(typeof window !== 'undefined' ? window : this);

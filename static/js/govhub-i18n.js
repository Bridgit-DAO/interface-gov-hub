/**
 * Gov-Hub client i18n: loads /static/i18n/shell/{locale}.json (+ optional second bundle).
 * Merges with Civic Mason keys when second base URL is passed.
 * Exposes GovHubI18n and CMI18n (alias for Civic Mason scripts).
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

    function deepMerge(a, b) {
        if (!b || typeof b !== 'object') return a || {};
        var out = {};
        var ak = a && typeof a === 'object' ? a : {};
        Object.keys(ak).forEach(function (k) {
            out[k] = ak[k];
        });
        Object.keys(b).forEach(function (k) {
            var bv = b[k];
            var av = out[k];
            if (
                bv &&
                typeof bv === 'object' &&
                !Array.isArray(bv) &&
                av &&
                typeof av === 'object' &&
                !Array.isArray(av)
            ) {
                out[k] = deepMerge(av, bv);
            } else {
                out[k] = bv;
            }
        });
        return out;
    }

    async function loadJson(base, loc) {
        var b = (base || '').replace(/\/?$/, '/');
        var url = b + (loc || 'en') + '.json';
        var r = await fetch(url, { credentials: 'same-origin' });
        if (r.ok) return r.json();
        return null;
    }

    /** Soft-launch copy: softLaunch.{locale}.json merged over softLaunch.en.json */
    async function loadSoftLaunchMessages(locale) {
        var enData = null;
        var rEn = await fetch('/static/i18n/shell/softLaunch.en.json', { credentials: 'same-origin' });
        if (rEn.ok) {
            enData = await rEn.json();
        }
        var base = (enData && enData.softLaunch) || {};
        if (!locale || locale === 'en') {
            return base;
        }
        var rLoc = await fetch('/static/i18n/shell/softLaunch.' + locale + '.json', {
            credentials: 'same-origin',
        });
        if (rLoc.ok) {
            var locData = await rLoc.json();
            var over = (locData && locData.softLaunch) || {};
            return deepMerge(base, over);
        }
        return base;
    }

    var GovHubI18n = {
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
            var self = this;

            function applyAttr(selector, attr, fn) {
                root.querySelectorAll(selector).forEach(function (el) {
                    var key = el.getAttribute(attr);
                    if (key) fn(el, self.t(key));
                });
            }

            root.querySelectorAll('[data-gh-i18n-interp]').forEach(function (el) {
                var key = el.getAttribute('data-gh-i18n-interp');
                if (!key) return;
                var vars = {};
                if (el.hasAttribute('data-i18n-supports')) {
                    vars.supports = el.getAttribute('data-i18n-supports');
                }
                if (el.hasAttribute('data-i18n-opposes')) {
                    vars.opposes = el.getAttribute('data-i18n-opposes');
                }
                if (el.hasAttribute('data-i18n-abstains')) {
                    vars.abstains = el.getAttribute('data-i18n-abstains');
                }
                if (el.hasAttribute('data-i18n-count')) {
                    vars.count = el.getAttribute('data-i18n-count');
                }
                el.textContent = self.t(key, vars);
            });

            applyAttr('[data-gh-i18n-value]', 'data-gh-i18n-value', function (el, text) {
                if (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && el.type !== 'file')) {
                    el.value = text;
                }
            });

            applyAttr('[data-gh-i18n]', 'data-gh-i18n', function (el, text) {
                el.textContent = text;
            });
            applyAttr('[data-gh-i18n-placeholder]', 'data-gh-i18n-placeholder', function (el, text) {
                el.setAttribute('placeholder', text);
            });
            applyAttr('[data-gh-i18n-aria]', 'data-gh-i18n-aria', function (el, text) {
                el.setAttribute('aria-label', text);
            });
            applyAttr('[data-gh-i18n-title]', 'data-gh-i18n-title', function (el, text) {
                el.setAttribute('title', text);
            });

            applyAttr('[data-cm-i18n]', 'data-cm-i18n', function (el, text) {
                el.textContent = text;
            });
            applyAttr('[data-cm-i18n-placeholder]', 'data-cm-i18n-placeholder', function (el, text) {
                el.setAttribute('placeholder', text);
            });
            applyAttr('[data-cm-i18n-aria]', 'data-cm-i18n-aria', function (el, text) {
                el.setAttribute('aria-label', text);
            });
            applyAttr('[data-cm-i18n-title]', 'data-cm-i18n-title', function (el, text) {
                el.setAttribute('title', text);
            });
        },

        applyFooter: function () {
            var el = document.getElementById('gh-site-footer');
            if (!el) return;
            var build = document.body.getAttribute('data-build-number') || '';
            var mode = el.getAttribute('data-footer-mode') || 'global';
            if (mode === 'layer') {
                var layer = el.getAttribute('data-layer-name') || '';
                el.textContent = this.t('footer.layerLine', { build: build, layer: layer });
            } else {
                el.textContent = this.t('footer.line', { build: build });
            }
        },

        setDocumentDir: function () {
            var rtl = this.isRtl();
            document.documentElement.setAttribute('dir', rtl ? 'rtl' : 'ltr');
            document.documentElement.setAttribute('lang', this.locale || 'en');
            var cm = document.getElementById('civic-mason-page');
            if (cm) {
                cm.setAttribute('dir', rtl ? 'rtl' : 'ltr');
                cm.classList.toggle('cm-rtl', rtl);
            }
        },

        /** Theme toggle button titles (call after init and on theme change). */
        refreshThemeChrome: function () {
            if (!this.messages || !Object.keys(this.messages).length) return;
            var btn = document.getElementById('theme-toggle');
            if (!btn) return;
            var html = document.documentElement;
            var preference = html.getAttribute('data-theme-preference') || 'dark';
            var effective = html.getAttribute('data-theme') || 'dark';
            if (preference === 'auto') {
                btn.setAttribute('title', this.t('theme.systemAuto'));
            } else if (effective === 'dark') {
                btn.setAttribute('title', this.t('theme.switchToLight'));
            } else {
                btn.setAttribute('title', this.t('theme.switchToDark'));
            }
        },

        /**
         * @param {string} locale
         * @param {string|null|undefined} secondBase - e.g. /static/i18n/civic-mason/ (loads after shell)
         */
        init: async function (locale, secondBase) {
            this.locale = locale || 'en';
            var bases = ['/static/i18n/shell/'];
            if (typeof secondBase === 'string' && secondBase) {
                bases.push(secondBase.replace(/\/?$/, '/'));
            }

            var merged = {};
            for (var i = 0; i < bases.length; i++) {
                var data = await loadJson(bases[i], this.locale);
                if (!data) data = await loadJson(bases[i], 'en');
                merged = deepMerge(merged, data || {});
            }
            var sl = await loadSoftLaunchMessages(this.locale);
            if (sl && typeof sl === 'object') {
                merged.softLaunch = sl;
            }
            this.messages = merged;
            this.setDocumentDir();
            this.applyDom(document.body);
            this.applyFooter();
            this.refreshThemeChrome();
            return this;
        },

        afterShellInit: function () {
            this.applyDom(document.body);
            this.applyFooter();
            this.refreshThemeChrome();
        },

        apiErrorMessage: function (data) {
            var code = (data && data.error_code) || 'UNKNOWN';
            var msg = this.t('api.errors.' + code);
            if (msg === 'api.errors.' + code) {
                return (data && data.error) || this.t('api.errors.UNKNOWN');
            }
            return msg;
        },
    };

    global.GovHubI18n = GovHubI18n;
    global.CMI18n = GovHubI18n;
})(typeof window !== 'undefined' ? window : this);

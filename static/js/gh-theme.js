/**
 * Theme preference: light / dark / auto (system).
 * Sets data-theme (effective) + data-theme-preference on <html>.
 */
(function () {
  'use strict';

  var PREFERENCES = ['dark', 'light', 'auto'];
  var mediaQuery = window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null;

  function isLoggedIn() {
    return !!document.querySelector('a[href="/logout/"]');
  }

  function readUserThemeMeta() {
    var meta = document.querySelector('meta[name="user-theme-preference"]');
    var value = meta ? meta.getAttribute('content') : '';
    return PREFERENCES.indexOf(value) >= 0 ? value : null;
  }

  function readStoredPreference() {
    try {
      var stored = localStorage.getItem('theme');
      return PREFERENCES.indexOf(stored) >= 0 ? stored : null;
    } catch (_e) {
      return null;
    }
  }

  function readHtmlPreference() {
    var pref = document.documentElement.getAttribute('data-theme-preference');
    return PREFERENCES.indexOf(pref) >= 0 ? pref : null;
  }

  function effectiveFromPreference(preference) {
    if (preference === 'auto') {
      return mediaQuery && mediaQuery.matches ? 'dark' : 'light';
    }
    return preference === 'light' ? 'light' : 'dark';
  }

  function resolveInitialPreference() {
    var userPref = readUserThemeMeta();
    if (isLoggedIn() && userPref) {
      return userPref;
    }
    var stored = readStoredPreference();
    if (stored) {
      return stored;
    }
    var htmlPref = readHtmlPreference();
    if (htmlPref) {
      return htmlPref;
    }
    return 'dark';
  }

  function updateThemeIcon(themeToggle, icon, preference, effective) {
    if (!themeToggle || !icon) return;
    if (preference === 'auto') {
      icon.className = 'fas fa-circle-half-stroke';
      themeToggle.title = 'System theme (auto) – click to switch';
    } else if (effective === 'dark') {
      icon.className = 'fas fa-sun';
      themeToggle.title = 'Switch to light mode';
    } else {
      icon.className = 'fas fa-moon';
      themeToggle.title = 'Switch to dark mode';
    }
    if (window.GovHubI18n && window.GovHubI18n.refreshThemeChrome) {
      window.GovHubI18n.refreshThemeChrome();
    }
  }

  function persistThemeForLoggedInUser(preference) {
    if (!isLoggedIn()) return;
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute('content') : '';
    if (!token) return;
    var body = new URLSearchParams({
      action: 'update_theme',
      theme: preference,
      csrf_token: token,
    });
    fetch('/profile/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
      credentials: 'same-origin',
    }).catch(function () { /* non-blocking */ });
  }

  function applyPreference(preference, options) {
    options = options || {};
    var html = document.documentElement;
    var themeToggle = document.getElementById('theme-toggle');
    var icon = themeToggle ? themeToggle.querySelector('i') : null;
    var pref = PREFERENCES.indexOf(preference) >= 0 ? preference : 'dark';
    var effective = effectiveFromPreference(pref);

    html.setAttribute('data-theme-preference', pref);
    html.setAttribute('data-theme', effective);
    try {
      localStorage.setItem('theme', pref);
    } catch (_e) { /* ignore */ }

    var userMeta = document.querySelector('meta[name="user-theme-preference"]');
    if (userMeta && isLoggedIn()) {
      userMeta.setAttribute('content', pref);
    }

    updateThemeIcon(themeToggle, icon, pref, effective);

    if (options.persist !== false) {
      persistThemeForLoggedInUser(pref);
    }
  }

  function nextPreference(current) {
    var idx = PREFERENCES.indexOf(current);
    if (idx < 0) return 'light';
    return PREFERENCES[(idx + 1) % PREFERENCES.length];
  }

  function onSystemThemeChange() {
    var pref = document.documentElement.getAttribute('data-theme-preference');
    if (pref !== 'auto') return;
    applyPreference('auto', { persist: false });
  }

  function init() {
    var html = document.documentElement;
    var themeToggle = document.getElementById('theme-toggle');
    var icon = themeToggle ? themeToggle.querySelector('i') : null;
    var saved = resolveInitialPreference();
    applyPreference(saved, { persist: false });

    if (mediaQuery) {
      if (typeof mediaQuery.addEventListener === 'function') {
        mediaQuery.addEventListener('change', onSystemThemeChange);
      } else if (typeof mediaQuery.addListener === 'function') {
        mediaQuery.addListener(onSystemThemeChange);
      }
    }

    if (!themeToggle) return;
    themeToggle.addEventListener('click', function () {
      var current = html.getAttribute('data-theme-preference') || 'dark';
      applyPreference(nextPreference(current));
    });
  }

  window.GovHubTheme = {
    setPreference: function (preference, options) {
      applyPreference(preference, options || {});
    },
    getPreference: function () {
      return document.documentElement.getAttribute('data-theme-preference') || 'dark';
    },
    getEffective: function () {
      return document.documentElement.getAttribute('data-theme') || 'dark';
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

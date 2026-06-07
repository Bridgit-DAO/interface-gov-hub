/**
 * Light/dark theme toggle — applies data-theme on <html>, persists to localStorage,
 * and syncs logged-in users' preference to /profile/.
 */
(function () {
  'use strict';

  function resolveInitialTheme() {
    var html = document.documentElement;
    var serverTheme = html.getAttribute('data-theme') || 'dark';
    var stored = localStorage.getItem('theme');
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
    if (serverTheme === 'light' || serverTheme === 'dark') {
      return serverTheme;
    }
    return 'dark';
  }

  function updateThemeIcon(themeToggle, icon, theme) {
    if (!themeToggle || !icon) return;
    icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    themeToggle.title = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
    if (window.GovHubI18n && window.GovHubI18n.refreshThemeChrome) {
      window.GovHubI18n.refreshThemeChrome();
    }
  }

  function persistThemeForLoggedInUser(theme) {
    if (!document.querySelector('a[href="/logout/"]')) return;
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute('content') : '';
    if (!token) return;
    var body = new URLSearchParams({
      action: 'update_theme',
      theme: theme,
      csrf_token: token,
    });
    fetch('/profile/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
      credentials: 'same-origin',
    }).catch(function () { /* non-blocking */ });
  }

  function applyTheme(theme) {
    var html = document.documentElement;
    var themeToggle = document.getElementById('theme-toggle');
    var icon = themeToggle ? themeToggle.querySelector('i') : null;
    html.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    updateThemeIcon(themeToggle, icon, theme);
  }

  function init() {
    var html = document.documentElement;
    var themeToggle = document.getElementById('theme-toggle');
    var icon = themeToggle ? themeToggle.querySelector('i') : null;
    var saved = resolveInitialTheme();
    html.setAttribute('data-theme', saved);
    updateThemeIcon(themeToggle, icon, saved);

    if (!themeToggle) return;
    themeToggle.addEventListener('click', function () {
      var current = html.getAttribute('data-theme') || 'dark';
      var next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      persistThemeForLoggedInUser(next);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

"""HTML template strings: BASE_TEMPLATE, SUBMIT_TEMPLATE, PROFILE_TEMPLATE."""

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="{html_lang}" data-theme="{theme_effective}" data-theme-preference="{theme_preference}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="user-theme-preference" content="{user_theme_preference_meta}">
    <meta name="csrf-token" content="{csrf_token}">
    <title>{title}</title>
    <script>
    (function () {{
        var el = document.documentElement;
        var pref = el.getAttribute('data-theme-preference') || 'dark';
        var userMeta = document.querySelector('meta[name="user-theme-preference"]');
        var userPref = userMeta ? userMeta.getAttribute('content') : '';
        if (userPref === 'light' || userPref === 'dark' || userPref === 'auto') {{
            pref = userPref;
        }} else {{
            try {{
                var stored = localStorage.getItem('theme');
                if (stored === 'light' || stored === 'dark' || stored === 'auto') {{
                    pref = stored;
                }}
            }} catch (_e) {{}}
        }}
        var effective = pref;
        if (pref === 'auto') {{
            effective = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
                ? 'dark' : 'light';
        }}
        el.setAttribute('data-theme', effective);
        el.setAttribute('data-theme-preference', pref);
    }})();
    </script>
    <script>
    (function() {{
        var meta = document.querySelector('meta[name="csrf-token"]');
        var token = meta ? meta.getAttribute('content') : '';
        if (!token) return;
        var origFetch = window.fetch;
        window.fetch = function(input, init) {{
            init = init || {{}};
            if (init.credentials === 'omit') {{
                return origFetch.call(this, input, init);
            }}
            var url = typeof input === 'string'
                ? input
                : (input && input.url ? input.url : String(input));
            var sameOrigin = false;
            try {{
                sameOrigin = new URL(url, window.location.href).origin === window.location.origin;
            }} catch (_e) {{}}
            if (sameOrigin) {{
                var headers = new Headers(init.headers || {{}});
                if (!headers.has('X-CSRFToken')) {{
                    headers.set('X-CSRFToken', token);
                }}
                init.headers = headers;
            }}
            return origFetch.call(this, input, init);
        }};
    }})();
    </script>
    <link rel="icon" type="image/png" sizes="32x32" href="/static/favicon.png">
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
    <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    {font_awesome_link}
    <script src="{govhub_i18n_js}"></script>
    
    <style>
        :root {{
            /* Light theme (default) */
            --bg-color: #f4f7fc;
            --bg-secondary: #ffffff;
            --bg-tertiary: #e8eef8;
            --text-primary: #0a1628;
            --text-secondary: #4a5d7a;
            --text-muted: #7a8ba8;
            --border-color: rgba(77, 159, 255, 0.18);
            --border-hover: rgba(77, 159, 255, 0.32);
            --accent-color: #2563eb;
            --accent-hover: #1d4ed8;
            --success-color: #059669;
            --warning-color: #d97706;
            --error-color: #dc2626;
            --navbar-bg: rgba(244, 247, 252, 0.92);
            --navbar-text: #0a1628;
            --navbar-border: rgba(77, 159, 255, 0.14);
            --card-bg: rgba(255, 255, 255, 0.92);
            --card-border: rgba(102, 126, 234, 0.18);
            --input-bg: #ffffff;
            --input-border: rgba(77, 159, 255, 0.25);
            --shadow: 0 4px 20px rgba(10, 22, 40, 0.08);
            --shadow-hover: 0 8px 28px rgba(77, 159, 255, 0.12);
            --gh-brand-gov: #0a1628;
            --gh-brand-hub-start: #2563eb;
            --gh-brand-hub-end: #764ba2;
            --gh-brand-gradient: linear-gradient(135deg, #2563eb 0%, #667eea 48%, #764ba2 100%);
            --gh-glass-blur: blur(12px);
        }}

        [data-theme="dark"] {{
            /* Gov Hub brand — deep navy civic-tech palette */
            --bg-color: #050b1a;
            --bg-secondary: #0a1224;
            --bg-tertiary: #101a30;
            --text-primary: #eef2ff;
            --text-secondary: #94a3c4;
            --text-muted: #6b7a99;
            --border-color: rgba(77, 159, 255, 0.14);
            --border-hover: rgba(77, 159, 255, 0.28);
            --accent-color: #4d9fff;
            --accent-hover: #6eb3ff;
            --success-color: #34d399;
            --warning-color: #fbbf24;
            --error-color: #f87171;
            --navbar-bg: rgba(5, 11, 26, 0.88);
            --navbar-text: #eef2ff;
            --navbar-border: rgba(77, 159, 255, 0.12);
            --card-bg: rgba(10, 18, 36, 0.78);
            --card-border: rgba(102, 126, 234, 0.22);
            --input-bg: rgba(10, 18, 36, 0.92);
            --input-border: rgba(77, 159, 255, 0.22);
            --shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
            --shadow-hover: 0 8px 32px rgba(77, 159, 255, 0.12);
            --gh-brand-gov: #ffffff;
            --gh-brand-hub-start: #4d9fff;
            --gh-brand-hub-end: #764ba2;
            --gh-brand-gradient: linear-gradient(135deg, #4d9fff 0%, #667eea 48%, #764ba2 100%);
            --gh-glass-blur: blur(14px);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            margin: 0;
            min-height: 100vh;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}

        [data-theme="dark"] body {{
            background:
                radial-gradient(ellipse 120% 70% at 50% -10%, rgba(77, 159, 255, 0.1), transparent 55%),
                radial-gradient(ellipse 70% 50% at 100% 20%, rgba(118, 75, 162, 0.08), transparent 50%),
                radial-gradient(ellipse 60% 40% at 0% 80%, rgba(45, 212, 191, 0.05), transparent 45%),
                var(--bg-color);
        }}

        [data-theme="light"] body {{
            background:
                radial-gradient(ellipse 100% 60% at 50% -5%, rgba(77, 159, 255, 0.06), transparent 50%),
                var(--bg-color);
        }}

        /* Modern navbar similar to X — min-height only; fixed height caused overlap with main content on small screens */
        .navbar {{
            background-color: var(--navbar-bg) !important;
            border-bottom: 1px solid var(--navbar-border);
            backdrop-filter: var(--gh-glass-blur);
            -webkit-backdrop-filter: var(--gh-glass-blur);
            box-shadow: var(--shadow);
            padding: 0;
            min-height: 52px;
            z-index: 1030 !important;
            position: relative !important;
            overflow: visible !important;
        }}

        /* Align nav items with main content column (see govhub-design.css .container) */
        .navbar > .container {{
            align-items: center;
            max-width: var(--gh-content-max, 960px);
            width: 100%;
            margin-left: auto;
            margin-right: auto;
            padding-left: var(--bs-gutter-x, 0.75rem);
            padding-right: var(--bs-gutter-x, 0.75rem);
        }}

        @media (min-width: 992px) {{
            .navbar.navbar-expand-lg > .container {{
                display: flex !important;
                flex-wrap: nowrap !important;
                flex-direction: row !important;
                align-items: center !important;
            }}
            .navbar.navbar-expand-lg .navbar-brand {{
                flex: 0 0 auto;
                margin-right: 0.25rem;
            }}
            .navbar.navbar-expand-lg .navbar-collapse {{
                display: flex !important;
                flex: 1 1 auto !important;
                flex-basis: auto !important;
                flex-wrap: nowrap !important;
                width: auto !important;
                min-width: 0;
                justify-content: flex-end;
                align-items: center;
            }}
            .navbar.navbar-expand-lg .navbar-collapse > .navbar-nav {{
                flex-wrap: nowrap !important;
                flex-shrink: 1;
                min-width: 0;
            }}
            .navbar.navbar-expand-lg .navbar-nav.ms-auto {{
                flex-shrink: 0;
            }}
            .navbar.navbar-expand-lg .navbar-nav .nav-link {{
                padding-left: 12px;
                padding-right: 12px;
                white-space: nowrap;
            }}
            .navbar-expand-lg .navbar-nav.ms-auto .gh-user-nav-name {{
                display: inline-flex;
                align-items: center;
                vertical-align: middle;
            }}
        }}

        @media (max-width: 991.98px) {{
            .navbar > .container {{
                flex-wrap: wrap;
            }}
            .navbar-expand-lg .navbar-collapse {{
                flex-basis: 100%;
                width: 100%;
            }}
            .navbar-expand-lg .navbar-nav {{
                width: 100%;
            }}
        }}

        .navbar-brand {{
            color: var(--navbar-text) !important;
            font-weight: 700;
            font-size: 18px;
            padding: 16px 20px;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .navbar-brand:hover {{
            color: var(--accent-color) !important;
        }}

        .gh-brand-word {{
            font-weight: 800;
            letter-spacing: -0.02em;
        }}

        .gh-brand-gov {{
            color: var(--gh-brand-gov, var(--navbar-text));
        }}

        .gh-brand-hub {{
            background: var(--gh-brand-gradient, linear-gradient(135deg, #4d9fff, #764ba2));
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }}

        .navbar-brand img {{
            height: 24px;
            width: auto;
            object-fit: contain;
        }}

        /* White logo for dark mode — only for default GovHub logo, not layer logos */
        [data-theme="dark"] .navbar-brand img.navbar-brand-logo-invert {{
            filter: brightness(0) invert(1);
        }}

        .navbar-nav {{
            align-items: center;
        }}

        .nav-link {{
            color: var(--text-secondary) !important;
            font-weight: 500;
            padding: 16px 20px;
            margin: 0;
            border-radius: 0;
            transition: all 0.2s ease;
        }}
        
        .waitlist-tab-flair {{
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            border-radius: 8px 8px 0 0 !important;
            font-weight: 600 !important;
            position: relative;
        }}
        
        .waitlist-tab-flair::after {{
            content: '✨';
            margin-left: 6px;
            font-size: 0.9em;
        }}
        
        .waitlist-tab-flair.active {{
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
        }}

        .nav-link:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color) !important;
        }}

        .nav-link.active {{
            color: var(--accent-color) !important;
            border-bottom: 3px solid var(--accent-color);
            background-color: transparent;
        }}

        [data-theme="dark"] .inscribe-content-tabs .nav-link.active {{
            color: #ffffff !important;
            background-color: transparent !important;
            border-bottom-color: #ffffff;
        }}

        .layer-card-text {{
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
            overflow: hidden;
            font-size: 0.85rem;
            line-height: 1.35;
        }}
        /* Responsive: layers grid, navbar, containers */
        @media (max-width: 575.98px) {{
            .container {{ padding-left: 12px; padding-right: 12px; }}
            .navbar-nav {{ padding: 8px 0; }}
            .navbar-brand {{ font-size: 16px; padding: 12px 16px; }}
        }}
        @media (min-width: 1400px) {{
            .layer-card-col {{ flex: 0 0 16.666667%; max-width: 16.666667%; }}
        }}

        /* Theme toggle button */
        .theme-toggle {{
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 18px;
            padding: 16px 20px;
            cursor: pointer;
            transition: color 0.2s ease;
        }}

        .theme-toggle:hover {{
            color: var(--accent-color);
        }}
        [data-theme="dark"] .navbar-toggler {{
            border-color: var(--border-color);
            color: var(--navbar-text);
        }}
        [data-theme="dark"] .navbar-toggler-icon {{
            background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'%3e%3cpath stroke='rgba%28255, 255, 255, 0.8%29' stroke-linecap='round' stroke-miterlimit='10' stroke-width='2' d='M4 7h22M4 15h22M4 23h22'/%3e%3c/svg%3e");
        }}

        /* Cards with modern styling */
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            box-shadow: var(--shadow);
            transition: all 0.2s ease;
            backdrop-filter: var(--gh-glass-blur);
            -webkit-backdrop-filter: var(--gh-glass-blur);
        }}

        .card:hover {{
            box-shadow: var(--shadow-hover);
            border-color: var(--border-hover);
        }}

        .card-header {{
            background-color: transparent;
            border-bottom: 1px solid var(--card-border);
            border-radius: 16px 16px 0 0 !important;
            padding: 16px 20px;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .card-body {{
            padding: 20px;
        }}

        /* Buttons styled like X */
        .btn {{
            border-radius: 20px;
            font-weight: 700;
            padding: 8px 16px;
            transition: all 0.2s ease;
        }}

        .btn-primary {{
            background: var(--gh-brand-gradient, var(--accent-color));
            border: 1px solid rgba(77, 159, 255, 0.35);
            color: white;
            box-shadow: 0 4px 16px rgba(77, 159, 255, 0.2);
        }}

        .btn-primary:hover {{
            background: var(--gh-brand-gradient, var(--accent-hover));
            border-color: rgba(77, 159, 255, 0.5);
            filter: brightness(1.06);
            transform: translateY(-1px);
        }}

        .btn-outline-primary {{
            border-color: var(--text-secondary);
            color: var(--text-primary);
        }}

        .btn-outline-primary:hover {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .btn-outline-secondary {{
            border-color: var(--border-color);
            color: var(--text-secondary);
        }}

        .btn-outline-secondary:hover {{
            background-color: var(--bg-secondary);
            border-color: var(--border-hover);
            color: var(--text-primary);
        }}

        /* Form inputs */
        .form-control {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px;
            color: var(--text-primary) !important;
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        input.form-control, textarea.form-control, select.form-control {{
            color: var(--text-primary) !important;
            background-color: var(--input-bg) !important;
            border-color: var(--input-border) !important;
        }}

        /* Text fields only — do not restyle .form-check-input (breaks switches/checkboxes). */
        [data-theme="dark"] input:not(.form-check-input),
        [data-theme="dark"] textarea,
        [data-theme="dark"] select,
        [data-theme="dark"] input.form-control,
        [data-theme="dark"] textarea.form-control,
        [data-theme="dark"] select.form-control {{
            color: #ffffff !important;
            background-color: #16181c !important;
            border-color: #3d4043 !important;
        }}

        [data-theme="dark"] .form-switch .form-check-input {{
            background-color: #3d4043 !important;
            border-color: #2f3336 !important;
        }}

        [data-theme="dark"] .form-switch .form-check-input:checked {{
            background-color: var(--accent-color) !important;
            border-color: var(--accent-color) !important;
        }}

        .form-control:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
            background-color: var(--input-bg);
        }}

        .form-control::placeholder {{
            color: var(--text-muted);
        }}

        .form-select {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px;
            color: var(--text-primary) !important;
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        [data-theme="dark"] .form-select {{
            color: #ffffff !important;
            background-color: #16181c !important;
            border-color: #3d4043 !important;
        }}

        /* Modals */
        [data-theme="dark"] .modal-content {{
            background-color: var(--bg-secondary) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color) !important;
        }}

        [data-theme="dark"] .modal-header {{
            border-bottom-color: var(--border-color) !important;
        }}

        [data-theme="dark"] .modal-footer {{
            border-top-color: var(--border-color) !important;
        }}

        /* App modals: same style for all (no default Bootstrap look) */
        .modal-content {{
            border-radius: 12px;
            border: 1px solid var(--border-color, #dee2e6);
            box-shadow: 0 0.5rem 2rem rgba(0,0,0,0.15);
        }}
        [data-theme="dark"] .modal-content {{
            box-shadow: 0 0.5rem 2rem rgba(0,0,0,0.4);
        }}
        .modal-header {{
            border-bottom: 1px solid var(--border-color, #dee2e6);
            padding: 1rem 1.25rem;
            border-radius: 12px 12px 0 0;
        }}
        .modal-body {{
            padding: 1.25rem;
        }}
        .modal-footer {{
            border-top: 1px solid var(--border-color, #dee2e6);
            padding: 1rem 1.25rem;
            border-radius: 0 0 12px 12px;
        }}
        .modal-title {{
            font-weight: 600;
        }}

        [data-theme="dark"] .btn-close {{
            filter: invert(1);
        }}

        [data-theme="dark"] .list-group-item {{
            background-color: var(--bg-secondary) !important;
            color: var(--text-primary) !important;
            border-color: var(--border-color) !important;
        }}

        /* Alerts */
        .alert {{
            border-radius: 12px;
            border: none;
            padding: 16px 20px;
        }}

        .alert-info {{
            background-color: rgba(29, 155, 240, 0.1);
            color: var(--accent-color);
        }}

        /* Badges */
        .badge {{
            border-radius: 12px;
            font-weight: 500;
            padding: 4px 8px;
        }}

        /* Tables */
        .table {{
            color: var(--text-primary);
            border-color: var(--border-color);
        }}

        .table thead th {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
            border-color: var(--border-color);
            font-weight: 600;
            padding: 12px;
        }}

        .table tbody td {{
            background-color: var(--card-bg);
            color: var(--text-primary);
            border-color: var(--border-color);
            padding: 12px;
        }}

        .table-hover tbody tr:hover td {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
        }}
        
        .table-hover tbody tr:hover td * {{
            color: var(--text-primary);
        }}

        .table-responsive {{
            border-radius: 8px;
            overflow: hidden;
        }}

        /* Pagination */
        .pagination .page-link {{
            background-color: var(--card-bg);
            color: var(--text-primary);
            border-color: var(--border-color);
        }}

        .pagination .page-link:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
            border-color: var(--border-hover);
        }}

        .pagination .page-item.active .page-link {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .pagination .page-item.disabled .page-link {{
            background-color: var(--bg-secondary);
            color: var(--text-muted);
            border-color: var(--border-color);
        }}

        /* Dropdown menus in tables */
        .table .dropdown {{
            position: relative;
        }}

        .table .dropdown-menu {{
            background-color: var(--card-bg);
            border-color: var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            min-width: 120px;
            z-index: 1050;
            margin-top: 4px;
        }}

        .table .dropdown-item {{
            color: var(--text-primary);
            padding: 8px 16px;
            cursor: pointer;
        }}

        .table .dropdown-item:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
        }}

        .table .dropdown-toggle {{
            background-color: transparent;
            border-color: var(--accent-color);
            color: var(--accent-color);
        }}

        .table .dropdown-toggle:hover {{
            background-color: var(--accent-color);
            color: white;
            border-color: var(--accent-color);
        }}

        /* Ensure table doesn't clip dropdowns */
        .table-responsive {{
            overflow: visible !important;
        }}

        .card-body {{
            overflow: visible !important;
        }}

        /* Breadcrumbs */
        .breadcrumb {{
            background-color: transparent;
            padding: 0;
            margin-bottom: 20px;
        }}

        .breadcrumb-item a {{
            color: var(--text-secondary);
        }}

        .breadcrumb-item.active {{
            color: var(--text-primary);
            font-weight: 500;
        }}

        /* Flash messages */
        #flash-messages {{
            position: fixed;
            top: 70px;
            right: 20px;
            z-index: 1000;
            max-width: 400px;
        }}

        .flash-message {{
            margin-bottom: 10px;
            padding: 12px 16px;
            border-radius: 12px;
            font-weight: 500;
            box-shadow: var(--shadow);
        }}

        .flash-success {{
            background-color: rgba(0, 186, 124, 0.1);
            color: var(--success-color);
            border: 1px solid rgba(0, 186, 124, 0.2);
        }}

        .flash-error {{
            background-color: rgba(244, 33, 46, 0.1);
            color: var(--error-color);
            border: 1px solid rgba(244, 33, 46, 0.2);
        }}

        .flash-info {{
            background-color: rgba(247, 181, 41, 0.1);
            color: var(--warning-color);
            border: 1px solid rgba(247, 181, 41, 0.2);
        }}

        /* Avatar styling */
        .avatar {{
            border-radius: 50%;
            object-fit: cover;
        }}

        /* Centered content — moderate width for readability */
        .container {{
            max-width: 960px;
            margin: 0 auto;
            padding-left: 20px;
            padding-right: 20px;
        }}

        /* Responsive adjustments */
        @media (max-width: 768px) {{
            .navbar-brand {{
                font-size: 16px;
                padding: 16px 15px;
            }}

            .nav-link {{
                padding: 16px 12px;
                font-size: 14px;
            }}

            .theme-toggle {{
                padding: 16px 15px;
            }}

            .card {{
                border-radius: 12px;
            }}

            .card-header {{
                border-radius: 12px 12px 0 0 !important;
            }}

            .container {{
                padding-left: 15px;
                padding-right: 15px;
            }}
        }}

        @media (min-width: 992px) {{
            .container {{
                padding-left: 24px;
                padding-right: 24px;
            }}
        }}

        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
        }}

        ::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: var(--border-hover);
        }}

        /* Dropdown menu stacking relative to navbar */
        .dropdown-menu {{
            z-index: 1050 !important;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            background-color: var(--card-bg);
            margin-top: 8px;
            overflow: visible !important;
            position: absolute !important;
            top: 100% !important;
            left: 0 !important;
            min-width: 200px;
        }}

        /* Ensure dropdown container doesn't clip */
        .dropdown {{
            position: relative !important;
            overflow: visible !important;
        }}

        /* Prevent any parent from clipping the dropdown */
        .navbar .dropdown {{
            overflow: visible !important;
        }}

        /* Dropdown above navbar */
        .navbar .dropdown-menu {{
            z-index: 1050 !important;
            position: absolute !important;
            top: 100% !important;
            left: 0 !important;
        }}

        .dropdown-item {{
            color: var(--text-primary);
            padding: 12px 16px;
            transition: background-color 0.2s ease;
        }}

        .dropdown-item:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
        }}

        .dropdown-toggle {{
            border: none;
            background: none;
            color: var(--text-secondary);
            font-weight: 500;
            padding: 16px 12px;
            border-radius: 8px;
            transition: all 0.2s ease;
        }}

        .dropdown-toggle:hover {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
        }}

        .dropdown-toggle:focus {{
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
        }}

        /* Desktop nav: open dropdown submenus on hover (mobile keeps click/tap) */
        @media (min-width: 992px) {{
            .navbar.navbar-expand-lg .nav-item.dropdown:hover > .dropdown-menu,
            .navbar.navbar-expand-lg .nav-item.dropdown:focus-within > .dropdown-menu {{
                display: block;
            }}
        }}
    </style>
    <link href="/static/css/govhub-design.css?v=20260607herotheme" rel="stylesheet">
    <link href="/static/css/gh-nav-pills.css?v=1" rel="stylesheet">
    <script src="/static/js/gh-nav-pills.js?v=1" defer></script>
    <script src="/static/js/gh-nav-user-name.js?v=3" defer></script>
    <script src="/static/js/gh-directory.js"></script>
</head>
<body data-build-number="{build_number}" {body_attrs}>
    <script>
        (function () {{
            var loc = {site_locale_json};
            var b = document.body;
            var extra = (b.getAttribute('data-i18n-extra-base') || '').trim();
            window.__GH_I18N_READY__ = window.GovHubI18n
                ? GovHubI18n.init(loc, extra || null)
                : Promise.resolve();
        }})();
    </script>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="/">
                <img class="navbar-brand-logo-invert" src="/static/images/overweb_logo.png" alt="Overweb" />
                <span class="gh-brand-word"><span class="gh-brand-gov">Gov</span> <span class="gh-brand-hub">Hub</span></span>
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" data-gh-i18n-aria="nav.toggleMenu">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav">
                {participate_nav_html}
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-i18n="nav.governance">Governance</a>
                    <ul class="dropdown-menu">
                        {governance_nav}
                    </ul>
                </li>
                {community_nav_html}
                {recognition_nav_html}
                {learn_nav_html}
            </ul>
            <ul class="navbar-nav ms-auto">
                {user_menu}
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle gh-lang-toggle d-flex align-items-center" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-i18n-aria="lang.menuLabel" data-gh-i18n-title="lang.menuLabel"><img src="/static/images/language-icon.png?v=20260601" alt="" class="gh-lang-icon" aria-hidden="true"></a>
                    <ul class="dropdown-menu dropdown-menu-end">
                        {lang_menu}
                    </ul>
                </li>
                <li class="nav-item"><button type="button" class="theme-toggle nav-link border-0 bg-transparent" id="theme-toggle" data-gh-i18n-title="theme.toggle">
                    <i class="fas fa-moon"></i>
                </button></li>
            </ul>
            </div>
        </div>
    </nav>

    <div id="flash-messages">{flash_messages}</div>
    {content}

    <div class="container-fluid mt-5 py-3" style="border-top: 1px solid var(--border-color); background-color: var(--bg-secondary);">
        <div class="text-center text-muted small">
            <span id="gh-site-footer" data-footer-mode="global" data-layer-name=""></span>
        </div>
    </div>

    <div id="gh-account-declaration-overlay" style="display:none;position:fixed;inset:0;z-index:10050;background:rgba(0,0,0,0.65);align-items:center;justify-content:center;padding:16px;">
        <div style="background:var(--bg-primary,#1a1a1a);color:var(--text-primary,#eee);max-width:480px;width:100%;max-height:90vh;border-radius:12px;padding:20px;border:1px solid var(--border-color,#333);display:flex;flex-direction:column;gap:10px;">
            <h2 style="font-size:15px;margin:0;line-height:1.35;">Important Notice: Account Declaration and Unique Humanity Transition</h2>
            <p id="gh-ada-moratorium" style="font-size:12px;color:var(--text-muted,#888);margin:0;"></p>
            <div id="gh-ada-body" style="overflow-y:auto;max-height:42vh;font-size:12px;line-height:1.55;"></div>
            <label style="display:flex;gap:8px;align-items:flex-start;font-size:12px;cursor:pointer;">
                <input type="checkbox" id="gh-ada-understand" style="margin-top:2px;">
                <span>I understand and wish to continue.</span>
            </label>
            <p id="gh-ada-error" style="color:#dc3545;font-size:12px;min-height:16px;margin:0;"></p>
            <div style="display:flex;gap:8px;">
                <button type="button" class="btn btn-secondary flex-fill" id="gh-ada-cancel">Cancel</button>
                <button type="button" class="btn btn-primary flex-fill" id="gh-ada-accept" disabled>Accept</button>
            </div>
        </div>
    </div>

    <div id="gh-mfa-login-overlay" style="display:none;position:fixed;inset:0;z-index:10060;background:rgba(0,0,0,0.65);align-items:center;justify-content:center;padding:16px;">
        <div style="background:var(--bg-primary,#1a1a1a);color:var(--text-primary,#eee);max-width:400px;width:100%;border-radius:12px;padding:20px;border:1px solid var(--border-color,#333);display:flex;flex-direction:column;gap:12px;">
            <h2 style="font-size:16px;margin:0;line-height:1.35;"><i class="fas fa-shield-halved me-2"></i>Two-factor authentication</h2>
            <p style="font-size:13px;color:var(--text-muted,#888);margin:0;">Enter the 6-digit code from your authenticator app, or a backup code.</p>
            <input type="text" id="gh-mfa-login-code" class="form-control" inputmode="numeric" autocomplete="one-time-code" maxlength="12" placeholder="000000 or backup code">
            <p id="gh-mfa-login-error" style="color:#dc3545;font-size:12px;min-height:16px;margin:0;"></p>
            <div style="display:flex;gap:8px;">
                <button type="button" class="btn btn-secondary flex-fill" id="gh-mfa-login-cancel">Cancel</button>
                <button type="button" class="btn btn-primary flex-fill" id="gh-mfa-login-submit">Verify</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/gh-return-nav.js"></script>
    <script src="/static/js/gh-dialog.js"></script>
    <script src="/static/js/gh-image-crop.js"></script>
    <script src="/static/js/gh-invite.js?v=18"></script>
    <script src="/static/js/gh-theme.js?v=2" defer></script>
    <script>
        (function () {{
            var HOVER_MQ = window.matchMedia('(min-width: 992px)');

            function bindNavbarHoverDropdowns() {{
                if (!HOVER_MQ.matches || typeof bootstrap === 'undefined') return;
                document.querySelectorAll('.navbar .nav-item.dropdown').forEach(function (el) {{
                    if (el.dataset.ghHoverNavBound) return;
                    var toggle = el.querySelector('[data-bs-toggle="dropdown"]');
                    if (!toggle) return;
                    el.dataset.ghHoverNavBound = '1';
                    var dd = bootstrap.Dropdown.getOrCreateInstance(toggle);
                    el.addEventListener('mouseenter', function () {{ dd.show(); }});
                    el.addEventListener('mouseleave', function () {{ dd.hide(); }});
                }});
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', bindNavbarHoverDropdowns);
            }} else {{
                bindNavbarHoverDropdowns();
            }}
            HOVER_MQ.addEventListener('change', bindNavbarHoverDropdowns);
        }})();
    </script>
    <script>
        // Flash message auto-hide
        setTimeout(() => {{
            const flashMessages = document.querySelectorAll('.flash-message');
            flashMessages.forEach(msg => {{
                msg.style.opacity = '0';
                setTimeout(() => msg.remove(), 300);
            }});
        }}, 5000);

        // Web3Auth Integration
        let web3auth = null;
        let web3authInitPromise = null;
        let web3authLoginInProgress = false;
        const CANOPI_API_URL = "{canopi_api_url}";

        function ghAccountDeclarationBodyHtml() {{
            return '<p>As Canopi evolves toward a more trustworthy and accountable civic environment, we are introducing a transition period for account declaration.</p>'
                + '<p>Today, many participants may have more than one account for legitimate reasons, including historical usage, testing, organizational participation, pseudonymous participation, or account recovery.</p>'
                + '<p>We recognize that these situations exist.</p>'
                + '<p>To support a healthy transition, all participants are required to declare and connect any duplicate or related accounts before the Declaration Moratorium Date.</p>'
                + '<h3 style="font-size:13px;margin:14px 0 6px;">What this means</h3>'
                + '<p>If you control more than one Canopi account, you must:</p><ul>'
                + '<li>Declare all accounts under your control.</li>'
                + '<li>Link those accounts through the account declaration process.</li>'
                + '<li>Identify which account should serve as your primary account where applicable.</li>'
                + '</ul><p>Multiple accounts are not prohibited when properly declared and linked.</p>'
                + '<p>Undeclared duplicate accounts are not permitted.</p>'
                + '<h3 style="font-size:13px;margin:14px 0 6px;">Looking Ahead</h3>'
                + '<p>The future Meta-Layer ecosystem will support community choice regarding Proof of Unique Humanity and identity requirements.</p>'
                + '<p>Different communities may choose different approaches to identity, pseudonymity, reputation, and verification.</p>'
                + '<p>This policy is not intended to eliminate pseudonymous participation.</p>'
                + '<p>It is intended to ensure transparency, fairness, and trust within the Canopi ecosystem.</p>'
                + '<h3 style="font-size:13px;margin:14px 0 6px;">After the Moratorium Date</h3>'
                + '<p>Participants found to have knowingly maintained undeclared duplicate accounts after the moratorium date may be considered in violation of community terms and Canopi participation requirements.</p>'
                + '<p>Such violations may result in:</p><ul>'
                + '<li>loss of accumulated benefits,</li><li>loss of reputation or standing,</li>'
                + '<li>removal from governance processes,</li><li>suspension of accounts,</li>'
                + '<li>or other remedies determined by community governance processes.</li></ul>'
                + '<h3 style="font-size:13px;margin:14px 0 6px;">Acknowledgement</h3>'
                + '<p>By continuing, you acknowledge that:</p><ul>'
                + '<li>you have read and understood this policy;</li>'
                + '<li>you will declare any duplicate accounts under your control before the moratorium date;</li>'
                + '<li>you understand that future enforcement may apply to undeclared accounts discovered after the moratorium.</li></ul>';
        }}

        function ghEnsureAccountDeclaration(opts) {{
            const verifierId = (opts && opts.verifierId) || '';
            const idToken = (opts && opts.idToken) || '';
            if (!verifierId) return Promise.resolve(true);
            return fetch(CANOPI_API_URL + '/api/account-declaration/status?verifierId=' + encodeURIComponent(verifierId))
                .then(function (r) {{ return r.ok ? r.json() : {{ needed: true }}; }})
                .then(function (status) {{
                    if (!status || status.needed === false) return true;
                    return new Promise(function (resolve) {{
                        const overlay = document.getElementById('gh-account-declaration-overlay');
                        const body = document.getElementById('gh-ada-body');
                        const mor = document.getElementById('gh-ada-moratorium');
                        const cb = document.getElementById('gh-ada-understand');
                        const acceptBtn = document.getElementById('gh-ada-accept');
                        const cancelBtn = document.getElementById('gh-ada-cancel');
                        const errEl = document.getElementById('gh-ada-error');
                        if (!overlay || !body || !cb || !acceptBtn || !cancelBtn) {{
                            resolve(true);
                            return;
                        }}
                        body.innerHTML = ghAccountDeclarationBodyHtml();
                        mor.textContent = status.moratoriumDate
                            ? ('Declaration Moratorium Date: ' + status.moratoriumDate)
                            : '';
                        cb.checked = false;
                        acceptBtn.disabled = true;
                        errEl.textContent = '';
                        overlay.style.display = 'flex';
                        cb.onchange = function () {{ acceptBtn.disabled = !cb.checked; }};
                        cancelBtn.onclick = function () {{
                            overlay.style.display = 'none';
                            resolve(false);
                        }};
                        acceptBtn.onclick = function () {{
                            if (!cb.checked) return;
                            acceptBtn.disabled = true;
                            errEl.textContent = '';
                            fetch(CANOPI_API_URL + '/api/account-declaration/acknowledge', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: JSON.stringify({{
                                    idToken: idToken,
                                    verifierId: verifierId,
                                    policyVersion: status.currentPolicyVersion || undefined,
                                }}),
                            }}).then(function (resp) {{
                                if (!resp.ok) {{
                                    errEl.textContent = 'Could not save acknowledgement. Please try again.';
                                    acceptBtn.disabled = !cb.checked;
                                    return;
                                }}
                                overlay.style.display = 'none';
                                resolve(true);
                            }}).catch(function () {{
                                errEl.textContent = 'Network error. Please try again.';
                                acceptBtn.disabled = !cb.checked;
                            }});
                        }};
                    }});
                }})
                .catch(function () {{ return true; }});
        }}

        // Function to load script dynamically
        function loadScript(src) {{
            return new Promise((resolve, reject) => {{
                const script = document.createElement('script');
                script.src = src;
                script.onload = () => resolve();
                script.onerror = (e) => reject(e);
                document.head.appendChild(script);
            }});
        }}

        function setWeb3AuthUiState(state) {{
            ['web3auth-signin-btn', 'web3auth-google-btn', 'web3auth-email-btn'].forEach(function(id) {{
                const btn = document.getElementById(id);
                if (!btn) return;
                if (state === 'loading') {{
                    btn.disabled = true;
                    btn.setAttribute('aria-busy', 'true');
                }} else {{
                    btn.disabled = false;
                    btn.removeAttribute('aria-busy');
                }}
            }});
        }}

        // Initialize Web3Auth after ensuring scripts are loaded (single shared promise)
        function startWeb3AuthInit() {{
            if (web3authInitPromise) {{
                return web3authInitPromise;
            }}

            web3authInitPromise = (async () => {{
                setWeb3AuthUiState('loading');
                await loadScript('https://cdn.jsdelivr.net/npm/web3@1.10.0/dist/web3.min.js');
                await loadScript('https://unpkg.com/@web3auth/modal@10.13.1/dist/modal.umd.min.js');

                await new Promise((resolve, reject) => {{
                    const start = Date.now();
                    const timeout = 10000;
                    const checkWeb3Auth = () => {{
                        if (window.Modal && window.Modal.Web3Auth) {{
                            resolve();
                        }} else if (Date.now() - start > timeout) {{
                            reject(new Error('Web3Auth load timeout'));
                        }} else {{
                            setTimeout(checkWeb3Auth, 100);
                        }}
                    }};
                    checkWeb3Auth();
                }});

                const Web3AuthConstructor = window.Modal.Web3Auth;
                const modalCfg = ghWeb3AuthModalConfig();
                const web3AuthConfig = {{
                    clientId: "{web3auth_client_id}",
                    web3AuthNetwork: '{web3auth_network}',
                    chainConfig: {{
                        chainNamespace: 'eip155',
                        chainId: '0x1',
                        rpcTarget: 'https://rpc.ankr.com/eth',
                        displayName: 'Ethereum Mainnet',
                        blockExplorerUrl: 'https://etherscan.io',
                        ticker: 'ETH',
                        tickerName: 'Ethereum',
                    }},
                    uiConfig: {{
                        mode: 'dark',
                        theme: {{
                            primary: '#1d9bf0'
                        }},
                        loginMethodsOrder: ghWeb3AuthLoginMethodsOrder(),
                        defaultLanguage: 'en',
                    }},
                    loginConfig: {{
                        google: {{
                            verifier: '{web3auth_google_verifier}',
                            typeOfLogin: 'google',
                            clientId: '{web3auth_client_id}',
                            extraLoginOptions: {{ prompt: 'login select_account', access_type: 'offline' }},
                            queryParameters: {{ prompt: 'login select_account', access_type: 'offline' }}
                        }}
                    }},
                }};
                if (modalCfg) {{
                    web3AuthConfig.modalConfig = modalCfg;
                }}

                refreshWeb3AuthLoginHint();
                const instance = new Web3AuthConstructor(web3AuthConfig);
                await instance.init();
                web3auth = instance;
                if (web3auth.connected && window.location.pathname === '/login/') {{
                    console.log('Web3Auth: clearing stale session on login page');
                    try {{ await web3auth.logout(); }} catch (_e) {{}}
                }}
                console.log('Web3Auth initialized successfully');
                setWeb3AuthUiState('ready');
                return web3auth;
            }})().catch((error) => {{
                web3authInitPromise = null;
                web3auth = null;
                setWeb3AuthUiState('ready');
                console.error('Web3Auth initialization failed:', error);
                throw error;
            }});

            return web3authInitPromise;
        }}

        function isSafeReturnPath(url) {{
            if (!url) return false;
            if (url.startsWith('/') && !url.startsWith('//')) return true;
            try {{
                const u = new URL(url, window.location.origin);
                return u.origin === window.location.origin;
            }} catch (_e) {{
                return false;
            }}
        }}

        function normalizeReturnPath(url) {{
            if (!url) return '/';
            if (url.startsWith(window.location.origin + '/')) {{
                return url.slice(window.location.origin.length) || '/';
            }}
            if (url.startsWith(window.location.origin)) {{
                return '/';
            }}
            return url;
        }}

        function getReturnPathFromQuery() {{
            const params = new URLSearchParams(window.location.search);
            const candidate = params.get('redirect') || params.get('next');
            if (candidate && isSafeReturnPath(candidate)) {{
                return normalizeReturnPath(candidate);
            }}
            return null;
        }}

        function storePostLoginReturnPath(path) {{
            try {{
                if (path && isSafeReturnPath(path)) {{
                    sessionStorage.setItem('ghPostLoginReturn', normalizeReturnPath(path));
                }}
            }} catch (_e) {{}}
        }}

        function consumePostLoginReturnPath() {{
            const fromQuery = getReturnPathFromQuery();
            if (fromQuery) return fromQuery;
            try {{
                const stored = sessionStorage.getItem('ghPostLoginReturn');
                if (stored && isSafeReturnPath(stored)) {{
                    sessionStorage.removeItem('ghPostLoginReturn');
                    return normalizeReturnPath(stored);
                }}
            }} catch (_e) {{}}
            return '/';
        }}

        function ghAuthContextHasInvite() {{
            try {{
                const params = new URLSearchParams(window.location.search);
                if (params.get('invite')) return true;
                const next = params.get('next') || params.get('redirect') || '';
                if (next.indexOf('invite=') >= 0) return true;
                const stored = sessionStorage.getItem('ghPostLoginReturn') || '';
                if (stored.indexOf('invite=') >= 0) return true;
            }} catch (_e) {{}}
            return false;
        }}

        function ghIsWalletInAppBrowser() {{
            try {{
                const ua = navigator.userAgent || '';
                return /MetaMask|MetaMaskMobile/i.test(ua);
            }} catch (_e) {{}}
            return false;
        }}

        function ghShouldUseSocialLoginOnly() {{
            if (ghAuthContextHasInvite()) return true;
            if (ghIsWalletInAppBrowser()) return true;
            const path = window.location.pathname || '';
            return path === '/login/' || path === '/login';
        }}

        function ghWeb3AuthLoginMethodsOrder() {{
            if (ghShouldUseSocialLoginOnly()) {{
                return ['google', 'twitter', 'email_passwordless'];
            }}
            return ['google', 'twitter', 'email_passwordless', 'wallet'];
        }}

        function ghWeb3AuthModalConfig() {{
            if (!ghShouldUseSocialLoginOnly()) return null;
            const M = window.Modal || {{}};
            const WC = M.WALLET_CONNECTORS;
            if (!WC) {{
                return {{ hideWalletDiscovery: true }};
            }}
            const authId = WC.AUTH || 'auth';
            const connectors = {{
                [authId]: {{
                    label: 'social',
                    showOnModal: true,
                    loginMethods: {{
                        google: {{ name: 'Google', showOnModal: true }},
                        twitter: {{ showOnModal: true }},
                        email_passwordless: {{ showOnModal: true }},
                    }},
                }},
            }};
            [WC.METAMASK, WC.WALLET_CONNECT, WC.WALLET_CONNECT_V2].forEach(function(key) {{
                if (key) connectors[key] = {{ showOnModal: false }};
            }});
            return {{ hideWalletDiscovery: true, connectors: connectors }};
        }}

        async function ghResolveInviteLoginHint() {{
            try {{
                const stored = sessionStorage.getItem('gh_invite_login_hint');
                if (stored && stored.indexOf('@') > 0) return stored.trim().toLowerCase();
            }} catch (_e) {{}}
            let token = null;
            try {{
                const params = new URLSearchParams(window.location.search);
                token = params.get('invite');
                if (!token) {{
                    const next = params.get('next') || params.get('redirect') || '';
                    const m = next.match(/[?&]invite=([^&]+)/);
                    if (m) token = decodeURIComponent(m[1]);
                }}
                if (!token) {{
                    const ret = sessionStorage.getItem('ghPostLoginReturn') || '';
                    const m2 = ret.match(/[?&]invite=([^&]+)/);
                    if (m2) token = decodeURIComponent(m2[1]);
                }}
            }} catch (_e) {{}}
            if (!token) return null;
            try {{
                const res = await fetch('/api/platform-invitations/preview/' + encodeURIComponent(token), {{
                    credentials: 'include',
                }});
                const data = await res.json();
                const email = (data.invitee_email || '').trim().toLowerCase();
                if (email && email.indexOf('@') > 0) {{
                    try {{ sessionStorage.setItem('gh_invite_login_hint', email); }} catch (_e) {{}}
                    return email;
                }}
            }} catch (_e) {{}}
            return null;
        }}

        async function connectWeb3AuthProvider(providerMode, loginHint) {{
            const M = window.Modal || {{}};
            const WC = M.WALLET_CONNECTORS;
            if (providerMode === 'google' && WC) {{
                return web3auth.connectTo(WC.AUTH, {{ authConnection: 'google' }});
            }}
            if (providerMode === 'email' && WC) {{
                const hint = (loginHint || '').trim().toLowerCase();
                if (!hint || hint.indexOf('@') < 1) {{
                    throw new Error('Missing login_hint for email sign-in. Use the email address from your invitation.');
                }}
                return web3auth.connectTo(WC.AUTH, {{
                    authConnection: 'email_passwordless',
                    extraLoginOptions: {{ login_hint: hint }},
                    loginHint: hint,
                }});
            }}
            return web3auth.connect();
        }}

        function refreshWeb3AuthLoginHint() {{
            const hint = document.getElementById('web3auth-login-hint');
            const socialOnly = ghShouldUseSocialLoginOnly();
            if (hint) {{
                if (socialOnly) {{
                    hint.textContent = 'Sign in with Google or email using the same address as your invitation.';
                }} else {{
                    hint.textContent = 'Web3Auth — Google, email, or wallet';
                }}
            }}
        }}

        async function ghFinishLoginAfterSession(userInfo, idToken, evmAddress) {{
            const verifierId = userInfo.verifierId || userInfo.email || evmAddress || '';
            const declarationOk = await ghEnsureAccountDeclaration({{
                verifierId: verifierId,
                idToken: idToken,
            }});
            if (!declarationOk) {{
                await fetch('/api/auth/logout', {{ method: 'POST', credentials: 'include' }});
                alert('Sign in cancelled — account declaration is required to participate.');
                return false;
            }}
            let dest = consumePostLoginReturnPath();
            if (window.GhInvite && window.GhInvite.finishLoginWithInviteAccept) {{
                dest = await window.GhInvite.finishLoginWithInviteAccept(dest);
            }}
            window.location.replace(dest);
            return true;
        }}

        function ghShowMfaLoginOverlay() {{
            var overlay = document.getElementById('gh-mfa-login-overlay');
            if (overlay) {{
                overlay.style.display = 'flex';
            }}
            var input = document.getElementById('gh-mfa-login-code');
            if (input) {{
                input.value = '';
                input.focus();
            }}
            var err = document.getElementById('gh-mfa-login-error');
            if (err) err.textContent = '';
        }}

        function ghHideMfaLoginOverlay() {{
            var overlay = document.getElementById('gh-mfa-login-overlay');
            if (overlay) overlay.style.display = 'none';
        }}

        async function ghCompleteMfaLogin(challengeToken, userInfo, idToken, evmAddress) {{
            return new Promise(function (resolve) {{
                ghShowMfaLoginOverlay();
                var input = document.getElementById('gh-mfa-login-code');
                var errEl = document.getElementById('gh-mfa-login-error');
                var submitBtn = document.getElementById('gh-mfa-login-submit');
                var cancelBtn = document.getElementById('gh-mfa-login-cancel');
                if (!input || !submitBtn || !cancelBtn) {{
                    resolve(false);
                    return;
                }}

                async function onSubmit() {{
                    var code = (input.value || '').trim();
                    if (!code) {{
                        if (errEl) errEl.textContent = 'Enter a verification code.';
                        return;
                    }}
                    submitBtn.disabled = true;
                    if (errEl) errEl.textContent = '';
                    try {{
                        var res = await fetch('/api/mfa/verify-login', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            credentials: 'include',
                            body: JSON.stringify({{ challengeToken: challengeToken, code: code }}),
                        }});
                        var data = await res.json();
                        if (!res.ok) {{
                            if (errEl) errEl.textContent = data.error || 'Verification failed';
                            submitBtn.disabled = false;
                            return;
                        }}
                        ghHideMfaLoginOverlay();
                        if (data.user && data.user.theme && window.GovHubTheme) {{
                            window.GovHubTheme.setPreference(data.user.theme, {{ persist: false }});
                        }}
                        await ghFinishLoginAfterSession(userInfo, idToken, evmAddress);
                        resolve(true);
                    }} catch (e) {{
                        if (errEl) errEl.textContent = 'Network error. Try again.';
                        submitBtn.disabled = false;
                    }}
                }}

                function onCancel() {{
                    ghHideMfaLoginOverlay();
                    submitBtn.removeEventListener('click', onSubmit);
                    cancelBtn.removeEventListener('click', onCancel);
                    if (web3auth) {{
                        web3auth.logout().catch(function () {{}});
                    }}
                    resolve(false);
                }}

                submitBtn.addEventListener('click', onSubmit);
                cancelBtn.addEventListener('click', onCancel);
                input.addEventListener('keydown', function (ev) {{
                    if (ev.key === 'Enter') onSubmit();
                }});
            }});
        }}

        async function performWeb3AuthLogin(providerMode, loginHint) {{
            if (web3authLoginInProgress) {{
                return;
            }}

            try {{
                await startWeb3AuthInit();
            }} catch (error) {{
                alert('Web3Auth failed to load. Please refresh the page and try again.');
                return;
            }}

            if (!web3auth) {{
                alert("Web3Auth not initialized. Please refresh the page.");
                return;
            }}

            web3authLoginInProgress = true;
            try {{
                // Preserve return path when signing in from a content page (navbar modal).
                if (window.location.pathname !== '/login/') {{
                    const here = window.location.pathname + window.location.search + window.location.hash;
                    storePostLoginReturnPath(here);
                }}

                const web3authProvider = await connectWeb3AuthProvider(providerMode, loginHint);
                const userInfo = await web3auth.getUserInfo();
                
                console.log('User info received:', userInfo);
                
                // Get wallet address - with retry and error handling
                let evmAddress = '';
                try {{
                    if (web3authProvider) {{
                        const web3 = new Web3(web3authProvider);
                        // Wait a bit for provider to be ready
                        await new Promise(resolve => setTimeout(resolve, 500));
                        const accounts = await web3.eth.getAccounts();
                        if (accounts && accounts.length > 0) {{
                            evmAddress = accounts[0];
                        }}
                    }}
                }} catch (addrError) {{
                    console.warn('Could not get EVM address:', addrError);
                    // Not critical for social logins
                }}

                // Identity token — required for server-side verification (after connect only).
                let idToken = '';
                for (let attempt = 0; attempt < 3 && !idToken; attempt++) {{
                    try {{
                        if (attempt > 0) {{
                            await new Promise(resolve => setTimeout(resolve, 400 * attempt));
                        }}
                        const identity = await web3auth.getIdentityToken();
                        idToken = (identity && identity.idToken) || '';
                    }} catch (tokenError) {{
                        console.warn('Could not get identity token (attempt ' + (attempt + 1) + '):', tokenError);
                    }}
                }}
                if (!idToken) {{
                    alert('Sign-in verification failed: no identity token. Please try again.');
                    return;
                }}

                const payload = {{
                    idToken: idToken,
                    evmAddress: evmAddress || '',
                }};

                console.log('Sending verified Web3Auth login');

                // Send to backend
                const response = await fetch('/api/auth/web3auth', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    credentials: 'include',
                    body: JSON.stringify(payload)
                }});

                const result = await response.json();
                if (response.ok && result.mfaRequired && result.challengeToken) {{
                    await ghCompleteMfaLogin(
                        result.challengeToken,
                        userInfo,
                        idToken,
                        evmAddress
                    );
                    return;
                }}
                if (response.ok && result.success !== false) {{
                    if (result.user && result.user.theme && window.GovHubTheme) {{
                        window.GovHubTheme.setPreference(result.user.theme, {{ persist: false }});
                    }}
                    const me = await fetch('/api/user/me', {{ credentials: 'include' }});
                    if (!me.ok) {{
                        console.error('Session not established after login', me.status);
                        alert('Sign-in succeeded but the session was not saved. Try again or use a private window.');
                        return;
                    }}
                    await ghFinishLoginAfterSession(userInfo, idToken, evmAddress);
                }} else {{
                    console.error('Backend error:', result);
                    try {{ await web3auth.logout(); }} catch (_e) {{}}
                    alert('Login failed: ' + (result.error || 'Unknown error'));
                }}
            }} catch (error) {{
                console.error('Login failed:', error);
                try {{ if (web3auth) await web3auth.logout(); }} catch (_e) {{}}
                if (error.message && !error.message.includes('user closed')) {{
                    var msg = error.message;
                    if (/could not verify identity/i.test(msg)) {{
                        msg += '\\n\\nUse Google or email sign-in (same address as your invitation). Wallet login often fails for invited editors.';
                    }}
                    alert('Login failed: ' + msg);
                }}
            }} finally {{
                web3authLoginInProgress = false;
            }}
        }}

        async function loginWithWeb3Auth() {{
            if (ghShouldUseSocialLoginOnly()) {{
                return loginWithWeb3AuthGoogle();
            }}
            return performWeb3AuthLogin(null);
        }}

        async function loginWithWeb3AuthGoogle() {{
            return performWeb3AuthLogin('google', null);
        }}

        async function loginWithWeb3AuthEmail() {{
            let hint = await ghResolveInviteLoginHint();
            if (!hint) {{
                hint = (window.prompt('Enter the email address from your invitation:') || '').trim().toLowerCase();
            }}
            if (!hint || hint.indexOf('@') < 1) {{
                return;
            }}
            return performWeb3AuthLogin('email', hint);
        }}

        // Initialize Web3Auth on page load
        function bootWeb3Auth() {{
            const returnPath = getReturnPathFromQuery();
            if (returnPath) {{
                storePostLoginReturnPath(returnPath);
            }}

            startWeb3AuthInit()
                .then(async () => {{
                    refreshWeb3AuthLoginHint();
                    const urlParams = new URLSearchParams(window.location.search);
                    if (urlParams.get('show_login') === '1') {{
                        window.history.replaceState({{}}, '', window.location.pathname + window.location.search);
                        if (ghAuthContextHasInvite()) {{
                            await loginWithWeb3AuthEmail();
                        }} else if (!ghShouldUseSocialLoginOnly()) {{
                            await loginWithWeb3Auth();
                        }}
                    }}
                }})
                .catch(() => {{}});
        }}

        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', bootWeb3Auth);
        }} else {{
            bootWeb3Auth();
        }}

        window.loginWithWeb3Auth = loginWithWeb3Auth;
        window.loginWithWeb3AuthGoogle = loginWithWeb3AuthGoogle;
        window.loginWithWeb3AuthEmail = loginWithWeb3AuthEmail;
    </script>
</body>
</html>
"""

# Standalone layer view: layer branding in navbar, View in GovHub button. Same structure as BASE_TEMPLATE.
LAYER_STANDALONE_BASE_TEMPLATE = BASE_TEMPLATE.replace(
    '''    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="/">
                <img class="navbar-brand-logo-invert" src="/static/images/overweb_logo.png" alt="Overweb" />
                <span class="gh-brand-word"><span class="gh-brand-gov">Gov</span> <span class="gh-brand-hub">Hub</span></span>
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" data-gh-i18n-aria="nav.toggleMenu">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav">
                {participate_nav_html}
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-i18n="nav.governance">Governance</a>
                    <ul class="dropdown-menu">
                        {governance_nav}
                    </ul>
                </li>
                {community_nav_html}
                {recognition_nav_html}
                {learn_nav_html}
            </ul>
            <ul class="navbar-nav ms-auto">
                {user_menu}
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle gh-lang-toggle d-flex align-items-center" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-i18n-aria="lang.menuLabel" data-gh-i18n-title="lang.menuLabel"><img src="/static/images/language-icon.png?v=20260601" alt="" class="gh-lang-icon" aria-hidden="true"></a>
                    <ul class="dropdown-menu dropdown-menu-end">
                        {lang_menu}
                    </ul>
                </li>
                <li class="nav-item"><button type="button" class="theme-toggle nav-link border-0 bg-transparent" id="theme-toggle" data-gh-i18n-title="theme.toggle">
                    <i class="fas fa-moon"></i>
                </button></li>
            </ul>
            </div>
        </div>
    </nav>''',
    '''    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="/layer/{layer_slug}/">
                {layer_image_html}
                {layer_name}
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" data-gh-i18n-aria="nav.toggleMenu">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav">
                {participate_nav_html}
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-i18n="nav.governance">Governance</a>
                    <ul class="dropdown-menu">
                        {governance_nav}
                    </ul>
                </li>
                {community_nav_html}
                {recognition_nav_html}
                {learn_nav_html}
            </ul>
            <ul class="navbar-nav ms-auto">
                {user_menu}
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle gh-lang-toggle d-flex align-items-center" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-i18n-aria="lang.menuLabel" data-gh-i18n-title="lang.menuLabel"><img src="/static/images/language-icon.png?v=20260601" alt="" class="gh-lang-icon" aria-hidden="true"></a>
                    <ul class="dropdown-menu dropdown-menu-end">
                        {lang_menu}
                    </ul>
                </li>
                <li class="nav-item"><button type="button" class="theme-toggle nav-link border-0 bg-transparent" id="theme-toggle" data-gh-i18n-title="theme.toggle">
                    <i class="fas fa-moon"></i>
                </button></li>
            </ul>
            </div>
        </div>
    </nav>'''
).replace(
    '<span id="gh-site-footer" data-footer-mode="global" data-layer-name=""></span>',
    '<span id="gh-site-footer" data-footer-mode="layer" data-layer-name="{layer_name_attr}"></span>',
)


SUBMIT_TEMPLATE = """
<div class="gh-page container mt-4" data-stripe-key="{{STRIPE_PK}}">
    <nav aria-label="breadcrumb" class="gh-detail-breadcrumb mb-3">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">Home</a></li>
            <li class="breadcrumb-item active">Submit Draft</li>
        </ol>
    </nav>

    {{PAGE_HERO}}

    <header class="gh-page-header">
        <div class="gh-page-header-main">
            <div class="gh-page-header-icon"><i class="fas fa-file-upload"></i></div>
            <div>
                <h1 class="gh-page-title">Submit a Meta-Layer Draft</h1>
                <p class="gh-page-lead">Submit a new Meta-Layer Draft to the Gov-Hub</p>
            </div>
        </div>
    </header>
    
    <div class="row">
        <div class="col-md-8">
            <div class="living-module">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-edit"></i></div>
                    <h5 class="living-module-title">Draft Submission Form</h5>
                </div>
                <div class="living-module-body">
                    <!-- Tabs for Upload File vs From Ordinal -->
                    <ul class="nav nav-tabs mb-3" id="submissionTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active" id="upload-tab" data-bs-toggle="tab" 
                                    data-bs-target="#upload" type="button" role="tab">
                                <i class="bi bi-upload"></i> Upload File
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="ordinal-tab" data-bs-toggle="tab" 
                                    data-bs-target="#ordinal" type="button" role="tab">
                                <i class="bi bi-coin"></i> From Ordinal
                            </button>
                        </li>
                        <!-- GH_IMMORTALIZE_NAV -->
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="immortalize-tab" data-bs-toggle="tab" 
                                    data-bs-target="#immortalize" type="button" role="tab">
                                <i class="bi bi-pencil-square"></i> Immortalize
                            </button>
                        </li>
                        <!-- /GH_IMMORTALIZE_NAV -->
                    </ul>

                    {{LAYER_SELECTOR_SHARED}}
                    
                    <div class="tab-content" id="submissionTabContent">
                        <!-- Upload File Tab -->
                        <div class="tab-pane fade show active" id="upload" role="tabpanel">
                            <form method="POST" enctype="multipart/form-data" id="uploadForm">
                                <input type="hidden" name="sourceType" value="file">
                                {{LAYER_HIDDEN_FIELD}}
                                
                                <div class="mb-3">
                                    <label for="title" class="form-label">Document Title *</label>
                                    <input type="text" class="form-control" id="title" name="title" required 
                                           placeholder="Enter the document title">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="authors" class="form-label">Authors *</label>
                                    <input type="text" class="form-control" id="authors" name="authors" required 
                                           placeholder="Comma-separated list of authors (e.g., John Doe, Jane Smith)">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="abstract" class="form-label">Abstract</label>
                                    <textarea class="form-control" id="abstract" name="abstract" rows="4" 
                                              placeholder="Brief description of the document"></textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="group" class="form-label">Workgroup (Optional)</label>
                                    <select class="form-select" id="group" name="group">
                                        {{WORKGROUP_OPTIONS}}
                                    </select>
                                </div>
                                {{DOCUMENT_META_FIELDS}}
                                
                                <div class="mb-3">
                                    <label for="file" class="form-label">Document File *</label>
                                    <input type="file" class="form-control" id="file" name="file" required 
                                           accept=".pdf,.txt,.xml,.doc,.docx">
                                    <div class="form-text">Supported formats: PDF, TXT, XML, DOC, DOCX (max 16MB)</div>
                                </div>
                                
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="terms" required>
                                        <label class="form-check-label" for="terms">
                                            I agree to the <a href="#" class="mlgh-terms-link" data-checkbox-id="terms">GovHub submission terms</a>
                                        </label>
                                    </div>
                                </div>
                                
                                <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                    <button type="submit" class="btn btn-primary">Submit Draft</button>
                                    <a href="/" class="btn btn-secondary">Cancel</a>
                                </div>
                            </form>
                        </div>
                        
                        <!-- From Ordinal Tab -->
                        <div class="tab-pane fade" id="ordinal" role="tabpanel">
                            <form method="POST" id="ordinalForm">
                                <input type="hidden" name="sourceType" value="ordinal">
                                {{LAYER_HIDDEN_FIELD}}
                                <input type="hidden" name="ordinalContentUrl" id="ordinalContentUrl">
                                <input type="hidden" name="ordinalContentType" id="ordinalContentType">
                                <input type="hidden" name="inscriptionNumber" id="inscriptionNumber">
                                <input type="hidden" name="blockHeight" id="blockHeight">
                                <input type="hidden" name="inscriptionTimestamp" id="inscriptionTimestamp">
                                
                                <div class="mb-3">
                                    <label for="ordinalId" class="form-label">Inscription ID *</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" id="ordinalId" name="ordinalId" required 
                                               placeholder="Enter Bitcoin Ordinal inscription ID">
                                        <button class="btn btn-outline-secondary" type="button" id="previewBtn">
                                            <i class="bi bi-eye"></i> Preview
                                        </button>
                                    </div>
                                    <div class="form-text">Enter the inscription ID from ordinals.com</div>
                                </div>

                                <div id="ordinalPreviewRequired" class="alert alert-warning mb-3" style="display: none;" role="alert">
                                    <i class="bi bi-exclamation-triangle"></i>
                                    <strong>Preview required.</strong> Click <strong>Preview</strong> to load the ordinal content before you can submit.
                                </div>
                                
                                <!-- Preview Area -->
                                <div id="ordinalPreview" class="mb-3" style="display: none;">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6 class="mb-0">Ordinal Preview</h6>
                                        </div>
                                        <div class="card-body">
                                            <div id="previewLoading" style="display: none;">
                                                <div class="text-center">
                                                    <div class="spinner-border text-primary" role="status">
                                                        <span class="visually-hidden">Loading...</span>
                                                    </div>
                                                    <p class="mt-2">Loading ordinal content...</p>
                                                </div>
                                            </div>
                                            <div id="previewError" class="alert alert-danger" style="display: none;"></div>
                                            <div id="previewContent"></div>
                                            <div id="previewMetadata" class="mt-3" style="display: none;">
                                                <hr>
                                                <h6>Metadata:</h6>
                                                <ul class="list-unstyled small">
                                                    <li><strong>Inscription ID:</strong> <span id="metaInscriptionId"></span></li>
                                                    <li><strong>Inscription Number:</strong> <span id="metaInscriptionNumber"></span></li>
                                                    <li><strong>Block Height:</strong> <span id="metaBlockHeight"></span></li>
                                                    <li><strong>Timestamp:</strong> <span id="metaTimestamp"></span></li>
                                                    <li><strong>Content Type:</strong> <span id="metaContentType"></span></li>
                                                    <li><strong>Content Size:</strong> <span id="metaContentSize"></span></li>
                                                </ul>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalTitle" class="form-label">Document Title *</label>
                                    <input type="text" class="form-control" id="ordinalTitle" name="title" required 
                                           placeholder="Enter the document title">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalAuthors" class="form-label">Authors *</label>
                                    <input type="text" class="form-control" id="ordinalAuthors" name="authors" required 
                                           placeholder="Comma-separated list of authors">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalAbstract" class="form-label">Abstract</label>
                                    <textarea class="form-control" id="ordinalAbstract" name="abstract" rows="4" 
                                              placeholder="Brief description of the document"></textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalGroup" class="form-label">Workgroup (Optional)</label>
                                    <select class="form-select" id="ordinalGroup" name="group">
                                        {{WORKGROUP_OPTIONS}}
                                    </select>
                                </div>
                                {{DOCUMENT_META_FIELDS}}
                                
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="ordinalTerms" required>
                                        <label class="form-check-label" for="ordinalTerms">
                                            I agree to the <a href="#" class="mlgh-terms-link" data-checkbox-id="ordinalTerms">GovHub submission terms</a>
                                        </label>
                                    </div>
                                </div>
                                
                                <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                    <button type="submit" class="btn btn-primary" id="ordinalSubmitBtn" disabled>Submit Draft</button>
                                    <a href="/" class="btn btn-secondary">Cancel</a>
                                </div>
                            </form>
                        </div>
                        
                        <!-- GH_IMMORTALIZE_PANE -->
                        <!-- Immortalize Tab -->
                        <div class="tab-pane fade" id="immortalize" role="tabpanel">
                            <!-- Choice screen (shown by default when tier pricing offered) -->
                            <div id="immortalizeChoice" data-offer-tier="{{OFFER_TIER_PRICING}}">
                                <p class="text-muted mb-3">How would you like to immortalize your content on Bitcoin?</p>
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <div class="card h-100 border-primary immortalize-option-card" id="chooseWizard" role="button" style="cursor:pointer;">
                                            <div class="card-body text-center p-4">
                                                <i class="bi bi-magic fs-1 mb-3 text-primary"></i>
                                                <h5 class="card-title">Immortalize with Us</h5>
                                                <p class="card-text text-muted">We handle everything. Pay with a credit or debit card. No Bitcoin wallet needed.</p>
                                                <ul class="list-unstyled text-start small mt-3">
                                                    <li><i class="bi bi-check text-success me-2"></i>Simple wizard</li>
                                                    <li><i class="bi bi-check text-success me-2"></i>Fiat payment (card)</li>
                                                    <li><i class="bi bi-check text-success me-2"></i>Country discounts available</li>
                                                </ul>
                                                <div class="mt-3"><span class="badge bg-primary fs-6">From $10</span></div>
                                            </div>
                                            <div class="card-footer text-center"><button class="btn btn-primary w-100">Get Started</button></div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="card h-100 immortalize-option-card" id="chooseSelfService" role="button" style="cursor:pointer;">
                                            <div class="card-body text-center p-4">
                                                <i class="bi bi-currency-bitcoin fs-1 mb-3 text-warning"></i>
                                                <h5 class="card-title">Self-Service</h5>
                                                <p class="card-text text-muted">Use your own Bitcoin wallet. Pay network fees directly. Full control.</p>
                                                <ul class="list-unstyled text-start small mt-3">
                                                    <li><i class="bi bi-check text-success me-2"></i>Pay only network fees</li>
                                                    <li><i class="bi bi-check text-success me-2"></i>Your Bitcoin wallet</li>
                                                </ul>
                                            </div>
                                            <div class="card-footer text-center"><button class="btn btn-outline-secondary w-100">Continue</button></div>
                                        </div>
                                    </div>
                                </div>
                                <div class="form-check mt-3">
                                    <input class="form-check-input" type="checkbox" id="immortalizeRemember">
                                    <label class="form-check-label text-muted small" for="immortalizeRemember">Remember my choice and skip this screen next time</label>
                                </div>
                            </div>
                            <!-- Wizard sub-flow -->
                            <div id="immortalizeWizard" style="display:none;">
                                <button class="btn btn-link btn-sm ps-0 mb-3" id="wizardBackToChoice">← Back to options</button>
                                <div id="wizardStep1" class="wizard-step">
                                    <h6>Step 1: Content</h6>
                                    <div class="mb-3">
                                        <ul class="nav nav-pills mb-2" id="wizardContentTabs" role="tablist">
                                            <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#wizardFile" type="button">Upload File</button></li>
                                            <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#wizardPaste" type="button">Paste Text</button></li>
                                        </ul>
                                        <div class="tab-content">
                                            <div class="tab-pane fade show active" id="wizardFile">
                                                <input type="file" class="form-control" id="wizardFileInput" accept=".txt,.md,.html,.json,.xml,.pdf,.doc,.docx,image/*">
                                            </div>
                                            <div class="tab-pane fade" id="wizardPaste">
                                                <textarea class="form-control font-monospace" id="wizardPasteInput" rows="8" placeholder="Paste text or markdown..."></textarea>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Title</label>
                                        <input type="text" class="form-control" id="wizardTitle" placeholder="Document title">
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Authors (comma-separated)</label>
                                        <input type="text" class="form-control" id="wizardAuthors" placeholder="Author 1, Author 2">
                                    </div>
                                    <button type="button" class="btn btn-primary" id="wizardStep1Next">Continue</button>
                                </div>
                                <div id="wizardStep2" class="wizard-step" style="display:none;">
                                    <h6>Step 2: Phone (for country tier)</h6>
                                    <div class="mb-3">
                                        <label class="form-label">Phone (E.164)</label>
                                        <input type="text" class="form-control" id="wizardPhone" placeholder="+1234567890">
                                    </div>
                                    <div id="wizardOtpSection" style="display:none;">
                                        <label class="form-label">Verification code</label>
                                        <input type="text" class="form-control mb-2" id="wizardOtp" placeholder="6-digit code" maxlength="6">
                                        <button type="button" class="btn btn-outline-primary btn-sm" id="wizardVerifyBtn">Verify</button>
                                    </div>
                                    <button type="button" class="btn btn-outline-primary" id="wizardSendOtpBtn">Send code</button>
                                    <div id="wizardPricePreview" class="mt-3" style="display:none;"></div>
                                    <button type="button" class="btn btn-primary" id="wizardStep2Next" style="display:none;">Continue</button>
                                </div>
                                <div id="wizardStep2_5" class="wizard-step" style="display:none;">
                                    <h6>Step 2.5: Acknowledge</h6>
                                    <div class="form-check mb-3">
                                        <input class="form-check-input" type="checkbox" id="wizardAckTiming" required>
                                        <label class="form-check-label" for="wizardAckTiming">I acknowledge that times to receive may vary.</label>
                                    </div>
                                    <div class="form-check mb-3">
                                        <input class="form-check-input" type="checkbox" id="wizardNotifyReady">
                                        <label class="form-check-label" for="wizardNotifyReady">Notify me when my inscription is ready</label>
                                    </div>
                                    <button type="button" class="btn btn-primary" id="wizardStep2_5Next" disabled>Continue to Payment</button>
                                </div>
                                <div id="wizardStep3" class="wizard-step" style="display:none;">
                                    <h6>Step 3: Payment</h6>
                                    <div id="wizardStripeContainer"></div>
                                    <button type="button" class="btn btn-primary" id="wizardPayBtn">Pay $<span id="wizardPayAmount">0</span></button>
                                </div>
                                <div id="wizardStep4" class="wizard-step" style="display:none;">
                                    <h6>Order submitted</h6>
                                    <div class="alert alert-info"><span class="badge bg-warning">Inscription Pending</span></div>
                                    <div id="wizardConfirmInfo"></div>
                                    <div id="wizardStatusPoll" class="mt-3"></div>
                                </div>
                            </div>
                            <!-- Self-service sub-flow -->
                            <div id="immortalizeSelfService" style="display:none;">
                                <button class="btn btn-link btn-sm ps-0 mb-3" id="selfServiceBackToChoice">← Back to options</button>
                            <div id="inscribeFlow">
                                <!-- Step 1: Content + Preview -->
                                <div id="inscribeStep1">
                                    <div class="mb-3">
                                        <label class="form-label">Content *</label>
                                        <ul class="nav nav-pills mb-2 inscribe-content-tabs" id="inscribeContentTabs" role="tablist">
                                            <li class="nav-item" role="presentation">
                                                <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#inscribeFile" type="button">Upload File</button>
                                            </li>
                                            <li class="nav-item" role="presentation">
                                                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#inscribePaste" type="button">Paste Text</button>
                                            </li>
                                        </ul>
                                        <div class="tab-content">
                                            <div class="tab-pane fade show active" id="inscribeFile">
                                                <input type="file" class="form-control" id="inscribeFileInput" accept=".txt,.md,.html,.json,.xml,.pdf,.doc,.docx,image/*">
                                                <div id="inscribeFileThumbnail" class="mt-2" style="display: none;">
                                                    <img id="inscribeFileThumbnailImg" src="" alt="Preview" class="img-thumbnail" style="max-width: 200px; max-height: 150px; object-fit: contain;">
                                                </div>
                                                <div class="form-text">Max 390KB. Text, markdown, HTML, images supported.</div>
                                            </div>
                                            <div class="tab-pane fade" id="inscribePaste">
                                                <textarea class="form-control font-monospace" id="inscribePasteInput" rows="8" placeholder="Paste text or markdown..."></textarea>
                                            </div>
                                        </div>
                                        <div id="inscribeSizeIndicator" class="form-text mt-1" style="display: none;"></div>
                                    </div>
                                    <div id="inscribePreviewArea" class="mb-3">
                                        <div class="card" id="inscribePreviewCard" style="display: none;">
                                            <div class="card-header"><h6 class="mb-0">Preview</h6></div>
                                            <div class="card-body" id="inscribePreviewContent"></div>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="inscribeCheckDuplicate">
                                            <label class="form-check-label" for="inscribeCheckDuplicate">Check for duplicate (text vs image use different APIs; API access pending)</label>
                                        </div>
                                        <div id="inscribeDuplicateResult" class="alert mt-2" style="display: none;"></div>
                                    </div>
                                    <div class="mb-3">
                                        <label for="inscribeReceiveAddress" class="form-label">Bitcoin Receive Address *</label>
                                        <input type="text" class="form-control font-monospace" id="inscribeReceiveAddress" placeholder="bc1q...">
                                    </div>
                                    <div class="mb-3">
                                        <label for="inscribeFeeRateSlider" class="form-label">Fee Rate (sat/vB)</label>
                                        <div class="d-flex justify-content-between align-items-center mb-1">
                                            <span id="inscribeFeeRateLabel" class="fw-bold">—</span>
                                            <span class="text-muted small">Current network: <span id="inscribeNetworkFee">—</span> sat/vB</span>
                                        </div>
                                        <div class="mb-2">
                                            <input type="range" class="form-range" id="inscribeFeeRateSlider" min="0" max="100" value="67" step="1" title="Log scale: 0.1 to 100 sat/vB" style="width: 100%; accent-color: var(--accent-color, #0d6efd);">
                                        </div>
                                        <div id="inscribeFeeCalculator" class="small text-muted mb-2">
                                            <span id="inscribeFeeSats">—</span> sats · <span id="inscribeFeeBtc">—</span> BTC · <span id="inscribeFeeUsd">—</span> USD
                                        </div>
                                        <div id="inscribeLowRateWarning" class="mt-2" style="display: none;">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" id="inscribeLowRateConfirm">
                                                <label class="form-check-label text-warning" for="inscribeLowRateConfirm">
                                                    I understand that setting a rate lower than current rates may result in delays in processing or never being processed.
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="d-flex gap-2">
                                        <button type="button" class="btn btn-primary" id="inscribeCreateBtn" disabled>
                                            <i class="bi bi-pencil-square"></i> Create Inscription
                                        </button>
                                        <a href="/inscribe/" class="btn btn-outline-secondary">Standalone Inscribe</a>
                                    </div>
                                </div>
                                <!-- Step 2: Payment -->
                                <div id="inscribeStep2" style="display: none;">
                                    <div class="card">
                                        <div class="card-header"><h6 class="mb-0">Pay to Inscribe</h6></div>
                                        <div class="card-body">
                                            <p>Send <strong id="inscribePayAmount">0</strong> sats to:</p>
                                            <code id="inscribePayAddress" class="d-block mb-2 p-2 bg-light rounded"></code>
                                            <div id="inscribePayQr" class="mb-3"></div>
                                            <div id="inscribePayStatus" class="alert alert-info">Waiting for payment...</div>
                                            <button type="button" class="btn btn-secondary" id="inscribeBackBtn">Back</button>
                                        </div>
                                    </div>
                                </div>
                                <!-- Step 3: Success -->
                                <div id="inscribeStep3" style="display: none;">
                                    <div class="alert alert-success">
                                        <h6><i class="bi bi-check-circle"></i> Inscription Created</h6>
                                        <p class="mb-1">Inscription ID: <code id="inscribeResultId"></code></p>
                                        <a id="inscribeResultLink" href="#" target="_blank" class="btn btn-sm btn-outline-primary">View on ordinals.com</a>
                                        <hr>
                                        <button type="button" class="btn btn-primary" id="inscribeSubmitDraftBtn">Submit as Draft</button>
                                        <a href="/immortalize/" class="btn btn-outline-secondary">Inscribe Another</a>
                                    </div>
                                </div>
                            </div>
                            </div>
                        </div>
                        <!-- /GH_IMMORTALIZE_PANE -->
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Submission Guidelines</h5>
                </div>
                <div class="card-body">
                    <h6>File Requirements:</h6>
                    <ul class="small">
                        <li>PDF format preferred</li>
                        <li>Maximum 16MB file size</li>
                        <li>Use standard GovHub formatting</li>
                    </ul>
                    
                    <h6>Ordinal Requirements:</h6>
                    <ul class="small">
                        <li>Content must be < 50KB</li>
                        <li>Supported: Images, Text, Markdown, HTML</li>
                        <li>Valid inscription ID required</li>
                    </ul>
                    
                    <h6>Content Requirements:</h6>
                    <ul class="small">
                        <li>Clear, descriptive title</li>
                        <li>Complete author information</li>
                        <li>Abstract describing the work</li>
                        <li>Proper GovHub document structure</li>
                    </ul>
                    
                    <h6>Review Process:</h6>
                    <ul class="small">
                        <li>Initial technical review</li>
                        <li>Workgroup consideration</li>
                        <li>IESG review (if applicable)</li>
                        <li>Publication decision</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- GovHub submission terms modal -->
<div class="modal fade" id="mlghTermsModal" tabindex="-1" aria-labelledby="mlghTermsModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="mlghTermsModalLabel">GovHub Submission Terms</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <p class="text-muted small">Draft placeholder — final legal text to be provided.</p>
                <h6>1. Grant of submission</h6>
                <p>By submitting a draft to the Interface Governance Hub, you represent that you have the right to submit the work and that it does not infringe the rights of others.</p>
                <h6>2. Review process</h6>
                <p>Submissions are subject to technical review, workgroup consideration, and publication decisions according to GovHub governance procedures. Submission does not guarantee approval or publication.</p>
                <h6>3. Content standards</h6>
                <p>Submitted materials must meet GovHub formatting and content requirements. Ordinals and uploaded files must be complete, accurately described, and accompanied by correct author attribution.</p>
                <h6>4. Licensing</h6>
                <p>You agree that approved documents may be published and distributed under the layer’s chosen open documentation license unless otherwise agreed in writing.</p>
                <h6>5. Ordinal submissions</h6>
                <p>For Bitcoin Ordinal submissions, you confirm the inscription ID refers to content you intend to submit and that previewed content matches what reviewers will evaluate.</p>
                <h6>6. Privacy</h6>
                <p>Contact information associated with your account may be used for submission-related correspondence. See the GovHub privacy policy for details.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" id="mlghTermsAccept">Accept</button>
            </div>
        </div>
    </div>
</div>

<script src="https://js.stripe.com/v3/"></script>
<script>
// Ordinal preview functionality
document.addEventListener('DOMContentLoaded', function() {
    {{WORKGROUP_LAYER_SCRIPT}}
    console.log('🔨 BUILD {build_number} - Ordinals Module Loaded');
    
    const previewBtn = document.getElementById('previewBtn');
    const ordinalIdInput = document.getElementById('ordinalId');
    const ordinalPreview = document.getElementById('ordinalPreview');
    const previewLoading = document.getElementById('previewLoading');
    const previewError = document.getElementById('previewError');
    const previewContent = document.getElementById('previewContent');
    const previewMetadata = document.getElementById('previewMetadata');
    const ordinalSubmitBtn = document.getElementById('ordinalSubmitBtn');
    const ordinalPreviewRequired = document.getElementById('ordinalPreviewRequired');
    const ordinalForm = document.getElementById('ordinalForm');
    
    let previewData = null;
    let previewComplete = false;

    function resetOrdinalPreviewState() {
        previewData = null;
        previewComplete = false;
        document.getElementById('ordinalContentUrl').value = '';
        document.getElementById('ordinalContentType').value = '';
        document.getElementById('inscriptionNumber').value = '';
        document.getElementById('blockHeight').value = '';
        document.getElementById('inscriptionTimestamp').value = '';
        previewError.style.display = 'none';
        previewContent.innerHTML = '';
        previewMetadata.style.display = 'none';
        previewLoading.style.display = 'none';
        ordinalSubmitBtn.disabled = true;
    }

    function updateOrdinalPreviewUi() {
        const inscriptionId = ordinalIdInput.value.trim();
        if (!inscriptionId) {
            ordinalPreview.style.display = 'none';
            if (ordinalPreviewRequired) ordinalPreviewRequired.style.display = 'none';
            resetOrdinalPreviewState();
            return;
        }
        ordinalPreview.style.display = 'block';
        if (ordinalPreviewRequired) ordinalPreviewRequired.style.display = previewComplete ? 'none' : 'block';
        if (!previewComplete) {
            ordinalSubmitBtn.disabled = true;
            if (!previewLoading.style.display || previewLoading.style.display === 'none') {
                previewContent.innerHTML = '<p class="text-muted mb-0"><i class="bi bi-eye"></i> Click <strong>Preview</strong> to load ordinal content before submitting.</p>';
            }
        }
    }

    ordinalIdInput.addEventListener('input', function() {
        resetOrdinalPreviewState();
        updateOrdinalPreviewUi();
    });

    ordinalForm?.addEventListener('submit', function(e) {
        if (!document.getElementById('ordinalContentUrl').value.trim()) {
            e.preventDefault();
            updateOrdinalPreviewUi();
            if (ordinalPreviewRequired) {
                ordinalPreviewRequired.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    });
    
    previewBtn.addEventListener('click', async function() {
        const inscriptionId = ordinalIdInput.value.trim();
        
        if (!inscriptionId) {
            alert('Please enter an inscription ID');
            return;
        }
        
        // Show preview area and loading
        ordinalPreview.style.display = 'block';
        previewLoading.style.display = 'block';
        previewError.style.display = 'none';
        previewContent.innerHTML = '';
        previewMetadata.style.display = 'none';
        ordinalSubmitBtn.disabled = true;
        previewComplete = false;
        if (ordinalPreviewRequired) ordinalPreviewRequired.style.display = 'block';
        
        try {
            const response = await fetch('/api/ordinal/preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ inscriptionId })
            });
            
            const data = await response.json();
            
            previewLoading.style.display = 'none';
            
            if (!data.success) {
                previewError.textContent = data.error || 'Failed to load ordinal';
                previewError.style.display = 'block';
                previewComplete = false;
                return;
            }
            
            // Store preview data
            previewData = data;
            previewComplete = true;
            if (ordinalPreviewRequired) ordinalPreviewRequired.style.display = 'none';
            
            // Populate hidden fields
            document.getElementById('ordinalContentUrl').value = data.contentUrl;
            document.getElementById('ordinalContentType').value = data.contentType;
            document.getElementById('inscriptionNumber').value = data.inscriptionNumber || '';
            document.getElementById('blockHeight').value = data.blockHeight || '';
            document.getElementById('inscriptionTimestamp').value = data.timestamp || '';
            
            // Display content based on type
            displayOrdinalContent(data);
            
            // Display metadata
            displayMetadata(data);
            
            // Enable submit button
            ordinalSubmitBtn.disabled = false;
            
        } catch (error) {
            previewLoading.style.display = 'none';
            previewError.textContent = 'Error: ' + error.message;
            previewError.style.display = 'block';
            previewComplete = false;
        }
    });
    
    function displayOrdinalContent(data) {
        const contentType = data.contentType;
        const contentUrl = data.contentUrl;
        
        console.log('=== displayOrdinalContent DEBUG ===');
        console.log('contentType:', contentType);
        console.log('contentUrl:', contentUrl);
        console.log('startsWith image:', contentType.startsWith('image/'));
        console.log('includes text/plain:', contentType.includes('text/plain'));
        console.log('includes text/javascript:', contentType.includes('text/javascript'));
        console.log('includes application/json:', contentType.includes('application/json'));
        console.log('includes text/markdown:', contentType.includes('text/markdown'));
        console.log('includes text/html:', contentType.includes('text/html'));
        
        if (contentType.startsWith('image/')) {
            console.log('→ RENDERING AS IMAGE');
            // Display image
            previewContent.innerHTML = `<img src="${contentUrl}" class="img-fluid" alt="Ordinal content" style="max-height: 400px;">`;
        } else if (contentType.includes('text/plain') || contentType.includes('text/javascript') || contentType.includes('application/json')) {
            console.log('→ RENDERING AS TEXT/PLAIN (checking for markdown)');
            // Display plain text (handles charset parameters), but check if it's actually markdown
            fetch(contentUrl)
                .then(res => {
                    console.log('Fetch response status:', res.status);
                    return res.text();
                })
                .then(text => {
                    console.log('Text content length:', text.length);
                    console.log('First 100 chars:', text.substring(0, 100));
                    
                    // Check if text looks like markdown
                    const markdownPatterns = [
                        /^#{1,6}\s+.+$/m,              // Headers: # Header
                        /\[.+\]\(.+\)/,                // Links: [text](url)
                        /!\[.*\]\(.+\)/,               // Images: ![alt](url)
                        /^\s*[-*+]\s+.+$/m,            // Unordered lists
                        /^\s*\d+\.\s+.+$/m,            // Ordered lists
                        /```[\s\S]*?```/,              // Code blocks
                        /^\s*>\s+.+$/m,                // Blockquotes
                        /\*\*.+?\*\*/,                 // Bold
                        /__(.+?)__/,                   // Bold (alt)
                        /\*.+?\*/,                     // Italic
                        /_(.+?)_/                      // Italic (alt)
                    ];
                    
                    const looksLikeMarkdown = markdownPatterns.some(pattern => pattern.test(text));
                    
                    if (looksLikeMarkdown) {
                        console.log('→ DETECTED MARKDOWN in text/plain, converting...');
                        // Treat as markdown
                        fetch('/api/ordinal/convert-markdown', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ markdown: text })
                        })
                        .then(res => {
                            console.log('✅ Markdown API response status:', res.status);
                            return res.json();
                        })
                        .then(result => {
                            console.log('✅ Markdown API result:', result);
                            if (result.success) {
                                console.log('✅ HTML length:', result.html.length);
                                console.log('📄 HTML first 500 chars:', result.html.substring(0, 500));
                                // Fix relative image URLs
                                let html = result.html;
                                const beforeFix = html;
                                html = html.replace(/src="\/content\//g, 'src="https://ordinals.com/content/');
                                html = html.replace(/src='\/content\//g, "src='https://ordinals.com/content/");
                                if (html !== beforeFix) {
                                    console.log('✅ FIXED relative image URLs in frontend');
                                    console.log('📄 Fixed HTML first 500 chars:', html.substring(0, 500));
                                } else {
                                    console.log('⚠️  No relative URLs found to fix in frontend');
                                }
                                previewContent.innerHTML = `<div class="border p-3" style="max-height: 400px; overflow-y: auto;">${html}</div>`;
                                console.log('✅ HTML injected into DOM');
                            } else {
                                console.error('❌ Markdown conversion failed:', result.error);
                                // Fallback to plain text
                                previewContent.innerHTML = `<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(text)}</pre>`;
                            }
                        })
                        .catch(err => {
                            console.error('❌ Error calling markdown API:', err);
                            // Fallback to plain text
                            previewContent.innerHTML = `<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(text)}</pre>`;
                        });
                    } else {
                        console.log('→ DISPLAYING AS PLAIN TEXT');
                        previewContent.innerHTML = `<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(text)}</pre>`;
                    }
                })
                .catch(err => {
                    console.error('Error fetching text:', err);
                    previewContent.innerHTML = `<div class="alert alert-danger">Error loading text: ${err.message}</div>`;
                });
        } else if (contentType.includes('text/markdown')) {
            console.log('→ RENDERING AS MARKDOWN');
            // Display markdown (convert to HTML)
            fetch(contentUrl)
                .then(res => res.text())
                .then(markdown => {
                    return fetch('/api/ordinal/convert-markdown', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ markdown })
                    });
                })
                .then(res => res.json())
                .then(result => {
                    if (result.success) {
                        // Fix relative image URLs to ordinals.com
                        let html = result.html;
                        html = html.replace(/src="\/content\//g, 'src="https://ordinals.com/content/');
                        html = html.replace(/src='\/content\//g, "src='https://ordinals.com/content/");
                        previewContent.innerHTML = `<div class="border p-3" style="max-height: 400px; overflow-y: auto;">${html}</div>`;
                    }
                });
        } else if (contentType.includes('text/html')) {
            console.log('→ RENDERING AS HTML');
            // Display HTML in sandboxed iframe
            previewContent.innerHTML = `<iframe src="${contentUrl}" sandbox="allow-same-origin" style="width: 100%; height: 400px; border: 1px solid var(--card-border);"></iframe>`;
        } else {
            console.log('→ UNSUPPORTED TYPE');
            previewContent.innerHTML = `<div class="alert alert-info">Content type: ${contentType}<br>Cannot preview this content type.</div>`;
        }
    }
    
    function displayMetadata(data) {
        document.getElementById('metaInscriptionId').textContent = data.inscriptionId;
        document.getElementById('metaInscriptionNumber').textContent = data.inscriptionNumber || 'N/A';
        document.getElementById('metaBlockHeight').textContent = data.blockHeight || 'N/A';
        document.getElementById('metaTimestamp').textContent = data.timestamp || 'N/A';
        document.getElementById('metaContentType').textContent = data.contentType;
        document.getElementById('metaContentSize').textContent = formatBytes(data.contentSize);
        previewMetadata.style.display = 'block';
    }
    
    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // GovHub submission terms modal
    let termsTargetCheckbox = null;
    const mlghTermsModalEl = document.getElementById('mlghTermsModal');
    document.querySelectorAll('.mlgh-terms-link').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            termsTargetCheckbox = document.getElementById(link.dataset.checkboxId);
            if (mlghTermsModalEl && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getOrCreateInstance(mlghTermsModalEl).show();
            }
        });
    });
    document.getElementById('mlghTermsAccept')?.addEventListener('click', function() {
        if (termsTargetCheckbox) termsTargetCheckbox.checked = true;
        if (mlghTermsModalEl && typeof bootstrap !== 'undefined') {
            bootstrap.Modal.getInstance(mlghTermsModalEl)?.hide();
        }
    });
});

// Immortalize choice + Wizard logic
document.addEventListener('DOMContentLoaded', function() {
    const choiceDiv = document.getElementById('immortalizeChoice');
    const wizardDiv = document.getElementById('immortalizeWizard');
    const selfServiceDiv = document.getElementById('immortalizeSelfService');
    if (!choiceDiv) return;

    function showChoice() {
        if (choiceDiv) choiceDiv.style.display = '';
        if (wizardDiv) wizardDiv.style.display = 'none';
        if (selfServiceDiv) selfServiceDiv.style.display = 'none';
    }
    function showWizard() {
        if (choiceDiv) choiceDiv.style.display = 'none';
        if (wizardDiv) wizardDiv.style.display = '';
        if (selfServiceDiv) selfServiceDiv.style.display = 'none';
    }
    function showSelfService() {
        if (choiceDiv) choiceDiv.style.display = 'none';
        if (wizardDiv) wizardDiv.style.display = 'none';
        if (selfServiceDiv) selfServiceDiv.style.display = '';
    }

    document.getElementById('chooseWizard')?.addEventListener('click', function() {
        if (document.getElementById('immortalizeRemember')?.checked) localStorage.setItem('immortalizeDefault', 'wizard');
        showWizard();
        wizardShowStep(1);
    });
    document.getElementById('chooseSelfService')?.addEventListener('click', function() {
        if (document.getElementById('immortalizeRemember')?.checked) localStorage.setItem('immortalizeDefault', 'self-service');
        showSelfService();
    });
    document.getElementById('wizardBackToChoice')?.addEventListener('click', showChoice);
    document.getElementById('selfServiceBackToChoice')?.addEventListener('click', showChoice);

    document.getElementById('immortalize-tab')?.addEventListener('shown.bs.tab', function() {
        const offerTier = choiceDiv?.getAttribute('data-offer-tier') === 'true';
        if (!offerTier) { showSelfService(); return; }
        const def = localStorage.getItem('immortalizeDefault');
        if (def === 'wizard') { showWizard(); wizardShowStep(1); }
        else if (def === 'self-service') showSelfService();
    });
    const tabParam = new URLSearchParams(window.location.search).get('tab');
    if (tabParam === 'immortalize') document.getElementById('immortalize-tab')?.click();

    // Wizard step visibility
    function wizardShowStep(n) {
        [1,2,3,4].forEach(i => {
            const el = document.getElementById('wizardStep' + (i === 3 && n === 3 ? '2_5' : i === 4 ? '4' : i));
            if (el) el.style.display = (i === 3 && n === 3) ? 'none' : (i === 2 && n === 2.5) ? 'none' : (i === 2.5 && n === 2.5) ? '' : (i === n && i !== 2.5) ? '' : (i === 4 && n === 4) ? '' : 'none';
        });
        const s25 = document.getElementById('wizardStep2_5');
        const s3 = document.getElementById('wizardStep3');
        const s4 = document.getElementById('wizardStep4');
        if (n === 2.5) { if (s25) s25.style.display = ''; if (s3) s3.style.display = 'none'; if (s4) s4.style.display = 'none'; }
        else if (n === 3) { if (s25) s25.style.display = 'none'; if (s3) s3.style.display = ''; if (s4) s4.style.display = 'none'; }
        else if (n === 4) { if (s25) s25.style.display = 'none'; if (s3) s3.style.display = 'none'; if (s4) s4.style.display = ''; }
    }
    function wizardShowStepNum(n) {
        for (let i = 1; i <= 4; i++) {
            const id = (i === 3) ? 'wizardStep2_5' : (i === 4) ? 'wizardStep3' : (i === 5) ? 'wizardStep4' : 'wizardStep' + i;
            const el = document.getElementById(id);
            if (el) el.style.display = (n === 2.5 && id === 'wizardStep2_5') || (n === 3 && id === 'wizardStep3') || (n === 4 && id === 'wizardStep4') || (n === i && id === 'wizardStep' + i) ? '' : 'none';
        }
        if (n === 2.5) { document.getElementById('wizardStep1')?.style.setProperty('display','none'); document.getElementById('wizardStep2')?.style.setProperty('display','none'); document.getElementById('wizardStep2_5')?.style.setProperty('display',''); document.getElementById('wizardStep3')?.style.setProperty('display','none'); document.getElementById('wizardStep4')?.style.setProperty('display','none'); }
        else if (n === 3) { document.getElementById('wizardStep2_5')?.style.setProperty('display','none'); document.getElementById('wizardStep3')?.style.setProperty('display',''); }
        else if (n === 4) { document.getElementById('wizardStep3')?.style.setProperty('display','none'); document.getElementById('wizardStep4')?.style.setProperty('display',''); }
    }

    // Simpler step show
    function showWizardStep(step) {
        ['wizardStep1','wizardStep2','wizardStep2_5','wizardStep3','wizardStep4'].forEach((id,i) => {
            const el = document.getElementById(id);
            if (el) el.style.display = (i + 1 === step || (step === 3 && id === 'wizardStep2_5') || (step === 4 && id === 'wizardStep3') || (step === 5 && id === 'wizardStep4')) ? '' : 'none';
        });
        const idx = step;
        document.getElementById('wizardStep1').style.display = idx === 1 ? '' : 'none';
        document.getElementById('wizardStep2').style.display = idx === 2 ? '' : 'none';
        document.getElementById('wizardStep2_5').style.display = idx === 3 ? '' : 'none';
        document.getElementById('wizardStep3').style.display = idx === 4 ? '' : 'none';
        document.getElementById('wizardStep4').style.display = idx === 5 ? '' : 'none';
    }

    let wizardData = {};
    document.getElementById('wizardStep1Next')?.addEventListener('click', async function() {
        const fileInput = document.getElementById('wizardFileInput');
        const pasteInput = document.getElementById('wizardPasteInput');
        let content = '', filename = 'content.txt', pageCount = 1, imageCount = 0;
        if (fileInput?.files?.length) {
            const f = fileInput.files[0];
            filename = f.name;
            content = await new Promise(r => { const rd = new FileReader(); rd.onload = () => r(rd.result); rd.readAsDataURL(f); });
            if (f.type.startsWith('image/')) { imageCount = 1; pageCount = 0; } else { pageCount = 1; imageCount = 0; }
        } else if (pasteInput?.value?.trim()) {
            content = pasteInput.value.trim();
            pageCount = Math.max(1, Math.ceil(content.length / 2000));
            imageCount = 0;
        }
        if (!content) { alert('Please add content'); return; }
        wizardData = { content_text: typeof content === 'string' && content.startsWith('data:') ? null : content, content_file_b64: typeof content === 'string' && content.startsWith('data:') ? content : null, content_filename: filename, page_count: pageCount, image_count: imageCount, title: document.getElementById('wizardTitle')?.value || 'Untitled', authors: (document.getElementById('wizardAuthors')?.value || '').split(',').map(a=>a.trim()).filter(Boolean) };
        showWizardStep(2);
    });
    document.getElementById('wizardSendOtpBtn')?.addEventListener('click', async function() {
        const phone = document.getElementById('wizardPhone')?.value?.trim();
        if (!phone) { alert('Enter phone'); return; }
        const r = await fetch('/api/inscribe/send-otp/', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({phone}) });
        const d = await r.json();
        if (!d.success) { alert(d.error || 'Failed'); return; }
        document.getElementById('wizardOtpSection').style.display = '';
        document.getElementById('wizardSendOtpBtn').style.display = 'none';
    });
    document.getElementById('wizardVerifyBtn')?.addEventListener('click', async function() {
        const phone = document.getElementById('wizardPhone')?.value?.trim();
        const code = document.getElementById('wizardOtp')?.value?.trim();
        if (!phone || !code) { alert('Phone and code required'); return; }
        const r = await fetch('/api/inscribe/verify-otp/', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ phone, code, page_count: wizardData.page_count || 1, image_count: wizardData.image_count || 0 }) });
        const d = await r.json();
        if (!d.success) { alert(d.error || 'Failed'); return; }
        wizardData.phone = phone; wizardData.tier = d.tier; wizardData.final_price_usd = d.final_price_usd; wizardData.base_price_usd = d.base_price_usd; wizardData.discount_pct = d.discount_pct;
        document.getElementById('wizardPricePreview').innerHTML = '<div class="alert alert-success">Tier ' + d.tier + ' · $' + d.final_price_usd + '</div>';
        document.getElementById('wizardPricePreview').style.display = '';
        document.getElementById('wizardStep2Next').style.display = '';
    });
    document.getElementById('wizardStep2Next')?.addEventListener('click', function() { showWizardStep(3); });
    document.getElementById('wizardAckTiming')?.addEventListener('change', function() {
        document.getElementById('wizardStep2_5Next').disabled = !this.checked;
    });
    document.getElementById('wizardStep2_5Next')?.addEventListener('click', async function() {
        wizardData.acknowledged_timing = true;
        wizardData.notify_when_ready = document.getElementById('wizardNotifyReady')?.checked || false;
        document.getElementById('wizardStep2_5Next').disabled = true;
        const payload = { ...wizardData, group: '' };
        if (wizardData.content_text) payload.content_text = wizardData.content_text;
        else if (wizardData.content_file_b64) payload.content_file_b64 = wizardData.content_file_b64;
        const r = await fetch('/api/inscribe/create-payment/', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        const d = await r.json();
        document.getElementById('wizardStep2_5Next').disabled = false;
        if (!d.success) { alert(d.error || 'Failed'); return; }
        wizardData.order_id = d.order_id;
        wizardData.client_secret = d.client_secret;
        document.getElementById('wizardPayAmount').textContent = wizardData.final_price_usd || '0';
        showWizardStep(4);
        initWizardStripe();
    });
    function initWizardStripe() {
        if (window._wizardStripeInit) return;
        const payBtn = document.getElementById('wizardPayBtn');
        const container = document.getElementById('wizardStripeContainer');
        if (!payBtn || !container || !wizardData.client_secret) return;
        const pk = document.querySelector('[data-stripe-key]')?.getAttribute('data-stripe-key') || '';
        if (!pk) { container.innerHTML = '<p class="text-warning">Stripe not configured. Set STRIPE_PUBLISHABLE_KEY.</p>'; return; }
        if (typeof Stripe === 'undefined') { container.innerHTML = '<p class="text-warning">Stripe.js not loaded.</p>'; return; }
        const stripe = Stripe(pk);
        const elements = stripe.elements({ clientSecret: wizardData.client_secret });
        const paymentElement = elements.create('payment');
        paymentElement.mount(container);
        payBtn.addEventListener('click', async function() {
            payBtn.disabled = true;
            const { error } = await stripe.confirmPayment({
                elements,
                clientSecret: wizardData.client_secret,
                confirmParams: { return_url: window.location.origin + '/immortalize/success/' + wizardData.order_id + '/' }
            });
            payBtn.disabled = false;
            if (error) alert(error.message || 'Payment failed');
        });
        window._wizardStripeInit = true;
    }
    function pollWizardStatus(orderId) {
        const poll = async () => {
            const r = await fetch('/api/inscribe/' + orderId + '/status/');
            const d = await r.json();
            document.getElementById('wizardStatusPoll').innerHTML = '<p>Status: <span class="badge bg-secondary">' + (d.status || 'pending') + '</span></p>';
            if (d.status === 'completed' && d.submission_id) {
                document.getElementById('wizardStatusPoll').innerHTML = '<p><a href="/submit/status/' + d.submission_id + '/">View submission</a></p>';
                return;
            }
            setTimeout(poll, 5000);
        };
        poll();
    }
});

// Inscribe tab logic (works on submit page Inscribe tab and standalone /inscribe/ page)
document.addEventListener('DOMContentLoaded', function() {
    const inscribeFlow = document.getElementById('inscribeFlow');
    if (!inscribeFlow) return;
    
    const fileInput = document.getElementById('inscribeFileInput');
    const pasteInput = document.getElementById('inscribePasteInput');
    const previewCard = document.getElementById('inscribePreviewCard');
    const previewContent = document.getElementById('inscribePreviewContent');
    const checkDuplicate = document.getElementById('inscribeCheckDuplicate');
    const duplicateResult = document.getElementById('inscribeDuplicateResult');
    const receiveAddress = document.getElementById('inscribeReceiveAddress');
    const feeRateSlider = document.getElementById('inscribeFeeRateSlider');
    const feeRateLabel = document.getElementById('inscribeFeeRateLabel');
    const networkFeeEl = document.getElementById('inscribeNetworkFee');
    const lowRateWarning = document.getElementById('inscribeLowRateWarning');
    const lowRateConfirm = document.getElementById('inscribeLowRateConfirm');
    const feeSatsEl = document.getElementById('inscribeFeeSats');
    const feeBtcEl = document.getElementById('inscribeFeeBtc');
    const feeUsdEl = document.getElementById('inscribeFeeUsd');
    const createBtn = document.getElementById('inscribeCreateBtn');
    const step1 = document.getElementById('inscribeStep1');
    const step2 = document.getElementById('inscribeStep2');
    const step3 = document.getElementById('inscribeStep3');
    const payAmount = document.getElementById('inscribePayAmount');
    const payAddress = document.getElementById('inscribePayAddress');
    const payStatus = document.getElementById('inscribePayStatus');
    const backBtn = document.getElementById('inscribeBackBtn');
    const resultId = document.getElementById('inscribeResultId');
    const resultLink = document.getElementById('inscribeResultLink');
    const submitDraftBtn = document.getElementById('inscribeSubmitDraftBtn');
    
    let inscribeContent = null;
    let inscribeContentType = 'text/plain';
    let inscribeFilename = 'content.txt';
    let networkFeeRate = 10;
    
    function getFeeRateFromSlider() {
        const s = parseInt(feeRateSlider.value) || 67;
        return Math.pow(10, (s / 100) * 3 - 1);
    }
    function formatFeeRate(v) {
        return v < 1 ? v.toFixed(2) : (v < 10 ? v.toFixed(1) : Math.round(v).toString());
    }
    let btcPriceUsd = 0;
    function updateFeeRateUI() {
        const rate = getFeeRateFromSlider();
        if (feeRateLabel) feeRateLabel.textContent = formatFeeRate(rate) + ' sat/vB';
        if (networkFeeEl) networkFeeEl.textContent = formatFeeRate(networkFeeRate);
        const isLow = rate < networkFeeRate;
        if (lowRateWarning) lowRateWarning.style.display = isLow ? 'block' : 'none';
        if (lowRateConfirm) lowRateConfirm.checked = false;
        // Fee calculator: ~1000 vB typical inscription + 546 output + ~2000 commit ≈ rate*1000 + 2500
        const estSats = Math.round(rate * 1000 + 2500);
        if (feeSatsEl) feeSatsEl.textContent = estSats.toLocaleString();
        if (feeBtcEl) feeBtcEl.textContent = (estSats / 1e8).toFixed(8);
        if (feeUsdEl && btcPriceUsd > 0) feeUsdEl.textContent = '$' + (estSats / 1e8 * btcPriceUsd).toFixed(2);
        else if (feeUsdEl) feeUsdEl.textContent = '—';
        updateCreateBtnState();
    }
    function updateCreateBtnState() {
        const rate = getFeeRateFromSlider();
        const needsConfirm = rate < networkFeeRate && lowRateConfirm && !lowRateConfirm.checked;
        const canProceed = inscribeContent && receiveAddress.value.trim() && (!needsConfirm || (lowRateConfirm && lowRateConfirm.checked));
        createBtn.disabled = !canProceed;
    }
    
    function rateToSliderValue(rate) {
        const s = 100 * (Math.log10(Math.max(0.1, rate)) + 1) / 3;
        return Math.round(Math.max(0, Math.min(100, s)));
    }
    updateFeeRateUI();
    fetch('/api/inscription/network-fee').then(r => r.json()).then(d => {
        networkFeeRate = d.success ? (d.economyFee || d.hourFee || 10) : 10;
        if (networkFeeEl) networkFeeEl.textContent = formatFeeRate(networkFeeRate);
        if (feeRateSlider) feeRateSlider.value = rateToSliderValue(networkFeeRate);
        updateFeeRateUI();
    }).catch(() => { updateFeeRateUI(); });
    fetch('/api/inscription/btc-price').then(r => r.json()).then(d => {
        if (d.success && d.usd) btcPriceUsd = d.usd;
        updateFeeRateUI();
    }).catch(() => {});
    
    if (feeRateSlider) feeRateSlider.addEventListener('input', updateFeeRateUI);
    if (lowRateConfirm) lowRateConfirm.addEventListener('change', updateCreateBtnState);
    
    function runPreview() {
        const content = getInscribeContent();
        if (!content) {
            if (previewCard) previewCard.style.display = 'none';
            return;
        }
        if (previewCard) previewCard.style.display = 'block';
        previewContent.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Loading...';
        
        (async function() {
            try {
                if (content.text !== undefined) {
                    const size = new Blob([content.text]).size;
                    if (size > 390 * 1024) {
                        previewContent.innerHTML = '<div class="alert alert-danger">Content too large: ' + (size/1024).toFixed(1) + ' KB (max 390KB)</div>';
                        return;
                    }
                    const looksLikeMd = /^#{1,6}\\s+|\\[.+\\]\\(.+\\)|!\\[.*\\]\\(.+\\)|```|\\*\\*.+?\\*\\*/.test(content.text);
                    if (looksLikeMd) {
                        const res = await fetch('/api/ordinal/convert-markdown', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ markdown: content.text })
                        });
                        const data = await res.json();
                        previewContent.innerHTML = data.success ? '<div class="border p-3" style="max-height: 400px; overflow-y: auto;">' + data.html + '</div>' : '<pre>' + escapeHtml(content.text) + '</pre>';
                    } else {
                        previewContent.innerHTML = '<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">' + escapeHtml(content.text) + '</pre>';
                    }
                    inscribeContent = content;
                    inscribeContentType = 'text/plain';
                    inscribeFilename = 'content.txt';
                    updateCreateBtnState();
                } else {
                    const reader = new FileReader();
                    reader.onload = async function() {
                        const base64 = reader.result.split(',')[1];
                        const size = (base64.length * 3) / 4;
                        if (size > 390 * 1024) {
                            previewContent.innerHTML = '<div class="alert alert-danger">File too large (max 390KB)</div>';
                            return;
                        }
                        inscribeContent = { dataUrl: reader.result, filename: content.filename, type: content.type };
                        inscribeContentType = content.type;
                        inscribeFilename = content.filename;
                        if (content.type.startsWith('image/')) {
                            previewContent.innerHTML = '<img src="' + reader.result + '" class="img-fluid" style="max-height: 400px;">';
                        } else if (content.type.includes('text') || content.type.includes('json') || content.type.includes('html')) {
                            const text = atob(base64);
                            const res = await fetch('/api/ordinal/convert-markdown', {
                                method: 'POST', headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ markdown: text })
                            });
                            const data = await res.json();
                            previewContent.innerHTML = data.success ? '<div class="border p-3" style="max-height: 400px; overflow-y: auto;">' + data.html + '</div>' : '<pre>' + escapeHtml(text) + '</pre>';
                        } else {
                            previewContent.innerHTML = '<div class="alert alert-info">Binary file: ' + content.filename + '</div>';
                        }
                        updateCreateBtnState();
                    };
                    reader.readAsDataURL(content.file);
                    return;
                }
            } catch (e) {
                previewContent.innerHTML = '<div class="alert alert-danger">Error: ' + e.message + '</div>';
            }
        })();
    }
    
    let pasteDebounce;
    fileInput.addEventListener('change', function() {
        const thumb = document.getElementById('inscribeFileThumbnail');
        const thumbImg = document.getElementById('inscribeFileThumbnailImg');
        if (!thumb || !thumbImg) return;
        const file = fileInput.files[0];
        if (!file) {
            thumb.style.display = 'none';
            thumbImg.src = '';
            runPreview();
            return;
        }
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function() {
                thumbImg.src = reader.result;
                thumb.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            thumb.style.display = 'none';
            thumbImg.src = '';
        }
        runPreview();
    });
    pasteInput.addEventListener('input', function() {
        clearTimeout(pasteDebounce);
        pasteDebounce = setTimeout(runPreview, 300);
    });
    pasteInput.addEventListener('paste', function() {
        setTimeout(runPreview, 100);
    });
    const contentTabs = document.getElementById('inscribeContentTabs');
    if (contentTabs) contentTabs.addEventListener('shown.bs.tab', runPreview);
    
    function getInscribeContent() {
        const pasteTab = document.querySelector('[data-bs-target="#inscribePaste"]');
        if (pasteTab && pasteTab.classList.contains('active') && pasteInput.value.trim()) {
            return { text: pasteInput.value, type: 'text/plain', filename: 'content.txt' };
        }
        const file = fileInput.files[0];
        if (!file) return null;
        return { file, type: file.type || 'application/octet-stream', filename: file.name };
    }
    
    receiveAddress.addEventListener('input', updateCreateBtnState);
    
    checkDuplicate.addEventListener('change', async function() {
        if (!checkDuplicate.checked || !inscribeContent) return;
        duplicateResult.style.display = 'block';
        duplicateResult.className = 'alert alert-secondary mt-2';
        duplicateResult.textContent = 'Duplicate search: API access pending. Proceeding without check.';
    });
    
    createBtn.addEventListener('click', async function() {
        if (!inscribeContent || !receiveAddress.value.trim()) return;
        if (checkDuplicate.checked) {
            try {
                const isImage = inscribeContentType.startsWith('image/');
                const endpoint = isImage ? '/api/inscription/search-duplicate/image' : '/api/inscription/search-duplicate/text';
                const body = isImage && inscribeContent.dataUrl
                    ? { contentHash: 'placeholder-when-api-ready' }
                    : { text: inscribeContent.text || '' };
                const res = await fetch(endpoint, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                const data = await res.json();
                if (data.placeholder) {
                    duplicateResult.className = 'alert alert-info mt-2';
                    duplicateResult.textContent = data.message || 'Duplicate search: API access pending.';
                } else if (data.found && data.inscriptionId) {
                    duplicateResult.className = 'alert alert-warning mt-2';
                    duplicateResult.innerHTML = 'Similar content may exist: <a href="https://ordinals.com/inscription/' + data.inscriptionId + '" target="_blank">View</a>. Proceed anyway?';
                }
            } catch (e) {
                duplicateResult.className = 'alert alert-secondary mt-2';
                duplicateResult.textContent = 'Duplicate check skipped (API pending).';
            }
        }
        
        createBtn.disabled = true;
        createBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creating...';
        try {
            const payload = {
                receiveAddress: receiveAddress.value.trim(),
                feeRate: getFeeRateFromSlider()
            };
            if (inscribeContent.dataUrl) {
                payload.files = [{ filename: inscribeFilename, dataURL: inscribeContent.dataUrl }];
            } else {
                const b64 = btoa(unescape(encodeURIComponent(inscribeContent.text)));
                payload.files = [{ filename: inscribeFilename, dataURL: 'data:text/plain;base64,' + b64 }];
            }
            const res = await fetch('/api/inscription/create', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            createBtn.disabled = false;
            createBtn.innerHTML = '<i class="bi bi-pencil-square"></i> Create Inscription';
            
            if (!data.success) {
                alert(data.error || 'Failed to create inscription order');
                return;
            }
            step1.style.display = 'none';
            step2.style.display = 'block';
            payAmount.textContent = data.amount || 0;
            payAddress.textContent = data.pay_address || '';
            window._inscribeOrderId = data.order_id;
            if (data.qr_code) {
                document.getElementById('inscribePayQr').innerHTML = '<img src="' + data.qr_code + '" alt="QR" style="max-width: 200px;">';
            }
            const pollStatus = async () => {
                const s = await fetch('/api/inscription/status/' + data.order_id);
                const st = await s.json();
                payStatus.textContent = st.status === 'completed' ? 'Confirmed!' : (st.status || 'Waiting...');
                if (st.status === 'completed' && st.inscription_id) {
                    step2.style.display = 'none';
                    step3.style.display = 'block';
                    resultId.textContent = st.inscription_id;
                    resultLink.href = 'https://ordinals.com/inscription/' + st.inscription_id;
                    window._inscribeResultId = st.inscription_id;
                    return;
                }
                if (st.status !== 'failed') setTimeout(pollStatus, 5000);
            };
            setTimeout(pollStatus, 3000);
        } catch (e) {
            createBtn.disabled = false;
            createBtn.innerHTML = '<i class="bi bi-pencil-square"></i> Create Inscription';
            alert('Error: ' + e.message);
        }
    });
    
    backBtn.addEventListener('click', function() {
        step2.style.display = 'none';
        step1.style.display = 'block';
    });
    
    if (submitDraftBtn) {
        submitDraftBtn.addEventListener('click', function() {
            const id = window._inscribeResultId;
            if (id) {
                document.getElementById('ordinal-tab').click();
                document.getElementById('ordinalId').value = id;
                document.getElementById('previewBtn').click();
            }
        });
    }
});
</script>
"""


PROFILE_TEMPLATE = """
<div class="gh-page container mt-4 gh-profile-edit-page">
    <header class="gh-page-header mb-4">
        <div class="gh-page-header-main">
            <div class="gh-page-header-icon"><i class="fas fa-user-cog"></i></div>
            <div><h1 class="gh-page-title">User Profile</h1><p class="gh-page-lead">Manage your account settings</p></div>
        </div>
    </header>
    <div class="row">
        <div class="col-md-8">
            <div class="living-module">
                <div class="living-module-body">
                    <div id="flash-messages"></div>
                    
                    <!-- Profile Information -->
                    <h5>Profile Information</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_profile">
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" value="{current_user_name}" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" value="{current_user_email}" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" value="{session_user}" readonly>
                        </div>
                        <button type="submit" class="btn btn-primary">Update Profile</button>
                    </form>
                    
                    <hr>
                    
                    <!-- Password Change -->
                    <h5>Change Password</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_password">
                        <div class="mb-3">
                            <label for="old_password" class="form-label">Current Password</label>
                            <input type="password" class="form-control" id="old_password" name="old_password" required>
                        </div>
                        <div class="mb-3">
                            <label for="new_password" class="form-label">New Password</label>
                            <input type="password" class="form-control" id="new_password" name="new_password" required minlength="6">
                        </div>
                        <button type="submit" class="btn btn-warning">Change Password</button>
                    </form>

                    <hr>

                    <!-- Theme Preferences -->
                    <h5>Theme Preferences</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_theme">
                        <div class="mb-3">
                            <label class="form-label">Preferred Theme</label>
                            <select class="form-select" name="theme" id="theme-select">
                                <option value="light" {light_selected}>Light Mode</option>
                                <option value="dark" {dark_selected}>Dark Mode</option>
                                <option value="auto" {auto_selected}>Auto (System)</option>
                            </select>
                            <div class="form-text">Choose your preferred theme. Auto will follow your system's preference.</div>
                        </div>
                        <button type="submit" class="btn btn-secondary">Save Theme Preference</button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Account Status</h5>
                </div>
                <div class="card-body">
                    <p><strong>Username:</strong> {session_user}</p>
                    <p><strong>Name:</strong> {current_user_name}</p>
                    <p><strong>Email:</strong> {current_user_email}</p>
                    <p><strong>Status:</strong> <span class="badge bg-success">Active</span></p>
                </div>
            </div>
        </div>
    </div>
</div>
"""


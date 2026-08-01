/**
 * GovHub directory UI helpers – shared tile rendering, search, and sort.
 */
(function (global) {
  'use strict';

  var SORT_RECENT = 'recent';
  var SORT_OLDEST = 'oldest';
  var SORT_NAME_ASC = 'name-asc';
  var SORT_NAME_DESC = 'name-desc';
  var SORT_ID_ASC = 'id-asc';
  var SORT_ID_DESC = 'id-desc';

  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function emptyState(message, variant) {
    var cls = variant === 'danger' ? 'gh-alert-danger' : 'gh-alert-info';
    return '<div class="col-12"><div class="gh-alert ' + cls + '">' + esc(message) + '</div></div>';
  }

  function tile(o) {
    o = o || {};
    var title = esc(o.title || 'Untitled');
    var href = o.href || '#';
    var desc = (o.description || '').trim();
    var descHtml = desc
      ? '<p class="gh-directory-tile-desc">' + esc(desc.length > 160 ? desc.slice(0, 157) + '…' : desc) + '</p>'
      : '';
    var pulse = o.pulse ? '<span class="gh-directory-tile-pulse">' + esc(o.pulse) + '</span>' : '';
    var visual;
    if (o.imageUrl) {
      visual =
        '<div class="gh-directory-tile-visual">' +
        '<img src="' + esc(o.imageUrl) + '" alt="' + title + '">' +
        pulse +
        '</div>';
    } else {
      visual =
        '<div class="gh-directory-tile-visual">' +
        '<span class="gh-directory-placeholder"><i class="fas ' + esc(o.icon || 'fa-circle') + '"></i></span>' +
        pulse +
        '</div>';
    }
    var badges = o.badgesHtml
      ? '<div class="gh-directory-tile-badges">' + o.badgesHtml + '</div>'
      : '';
    var meta = o.metaHtml
      ? '<span class="gh-directory-tile-meta">' + o.metaHtml + '</span>'
      : '';
    var footerInner = badges || meta
      ? '<div class="gh-directory-tile-footer">' + badges + meta + '</div>'
      : '';
    var foot = o.footerHtml
      ? '<div class="gh-directory-tile-foot">' + o.footerHtml + '</div>'
      : '';
    return (
      '<div class="col d-flex">' +
      '<div class="gh-directory-tile">' +
      visual +
      '<div class="gh-directory-tile-body">' +
      '<h6 class="gh-directory-tile-title"><a href="' + esc(href) + '">' + title + '</a></h6>' +
      descHtml +
      footerInner +
      foot +
      '</div></div></div>'
    );
  }

  function getField(item, field) {
    if (typeof field === 'function') return field(item);
    if (field == null) return '';
    return item[field];
  }

  function parseItemDate(item, dateKeys) {
    var keys = dateKeys || ['updated_at', 'created_at', 'submitted_at', 'date', 'last_activity_at'];
    for (var i = 0; i < keys.length; i++) {
      var raw = getField(item, keys[i]);
      if (!raw) continue;
      var t = Date.parse(String(raw));
      if (!isNaN(t)) return t;
    }
    return 0;
  }

  function sortByName(items, nameKey) {
    nameKey = nameKey || 'name';
    return (items || []).slice().sort(function (a, b) {
      var aName = String(getField(a, nameKey) || '').toLowerCase();
      var bName = String(getField(b, nameKey) || '').toLowerCase();
      return aName.localeCompare(bName, undefined, { numeric: true, sensitivity: 'base' });
    });
  }

  function sortByRecent(items, dateKeys) {
    return (items || []).slice().sort(function (a, b) {
      return parseItemDate(b, dateKeys) - parseItemDate(a, dateKeys);
    });
  }

  /** Parse ML-Draft-NNN / ML-RFC-NNN sequence for document lists. */
  function parseMlNumberSeq(item, field) {
    field = field || 'ml_number';
    var ml = String(getField(item, field) || '').trim();
    var matches = ml.match(/\d+/g);
    if (!matches || !matches.length) return -1;
    return parseInt(matches[matches.length - 1], 10);
  }

  function mlNumberCompare(a, b, mlField, direction) {
    mlField = mlField || 'ml_number';
    var na = parseMlNumberSeq(a, mlField);
    var nb = parseMlNumberSeq(b, mlField);
    if (na !== nb) return direction * (na - nb);
    var ra = parseInt(String(getField(a, 'revision_number') || '0'), 10) || 0;
    var rb = parseInt(String(getField(b, 'revision_number') || '0'), 10) || 0;
    if (ra !== rb) return direction * (ra - rb);
    return direction * String(getField(a, 'title') || '').localeCompare(
      String(getField(b, 'title') || ''),
      undefined,
      { numeric: true, sensitivity: 'base' }
    );
  }

  /** Highest ML draft number first; ties broken by revision then title. */
  function sortByMlNumberDesc(items, mlField) {
    mlField = mlField || 'ml_number';
    return (items || []).slice().sort(function (a, b) {
      return mlNumberCompare(a, b, mlField, -1);
    });
  }

  /** Lowest ML draft number first; ties broken by revision then title. */
  function sortByMlNumberAsc(items, mlField) {
    mlField = mlField || 'ml_number';
    return (items || []).slice().sort(function (a, b) {
      return mlNumberCompare(a, b, mlField, 1);
    });
  }

  function sortByOldest(items, dateKeys) {
    return sortByRecent(items, dateKeys).reverse();
  }

  function matchesSearch(item, term, fields) {
    if (!term) return true;
    var q = String(term).trim().toLowerCase();
    if (!q) return true;
    fields = fields || ['name'];
    return fields.some(function (field) {
      var val = getField(item, field);
      if (val == null) return false;
      if (Array.isArray(val)) {
        return val.some(function (part) {
          return String(part).toLowerCase().indexOf(q) !== -1;
        });
      }
      return String(val).toLowerCase().indexOf(q) !== -1;
    });
  }

  /**
   * Filter by search term then sort (recent | name-asc | name-desc).
   */
  function filterAndSort(items, options) {
    options = options || {};
    var term = options.searchTerm || '';
    var sort = options.sort || SORT_RECENT;
    var searchFields = options.searchFields || ['name'];
    var nameKey = options.nameKey || 'name';
    var dateKeys = options.dateKeys || ['updated_at', 'created_at', 'submitted_at', 'date', 'last_activity_at', 'badge_earliest_start'];

    var filtered = (items || []).filter(function (item) {
      return matchesSearch(item, term, searchFields);
    });

    if (sort === SORT_NAME_ASC) return sortByName(filtered, nameKey);
    if (sort === SORT_NAME_DESC) return sortByName(filtered, nameKey).reverse();
    if (sort === SORT_OLDEST) return sortByOldest(filtered, dateKeys);
    if (sort === SORT_ID_ASC) {
      return sortByMlNumberAsc(filtered, options.mlNumberField || 'ml_number');
    }
    if (sort === SORT_ID_DESC) {
      return sortByMlNumberDesc(filtered, options.mlNumberField || 'ml_number');
    }
    if (sort === SORT_RECENT && options.recentSort === 'ml_number') {
      return sortByMlNumberDesc(filtered, options.mlNumberField || 'ml_number');
    }
    return sortByRecent(filtered, dateKeys);
  }

  /** Wire search + sort controls without replacing the inputs (preserves focus). */
  function bindControls(searchId, sortId, onApply) {
    var searchEl = document.getElementById(searchId);
    var sortEl = document.getElementById(sortId);
    if (searchEl && !searchEl.dataset.ghDirectoryBound) {
      searchEl.dataset.ghDirectoryBound = '1';
      searchEl.addEventListener('input', onApply);
    }
    if (sortEl && !sortEl.dataset.ghDirectoryBound) {
      sortEl.dataset.ghDirectoryBound = '1';
      sortEl.addEventListener('change', onApply);
    }
  }

  function getSortValue(sortId) {
    var el = document.getElementById(sortId);
    return (el && el.value) ? el.value : SORT_RECENT;
  }

  function getSearchValue(searchId) {
    var el = document.getElementById(searchId);
    return el ? el.value : '';
  }

  /** Drop duplicate workgroups when the same group is linked to multiple layers. */
  function dedupeById(items, idKey) {
    idKey = idKey || 'id';
    var seen = Object.create(null);
    var out = [];
    (items || []).forEach(function (item) {
      if (!item) return;
      var id = item[idKey];
      if (id == null || id === '') {
        out.push(item);
        return;
      }
      var key = String(id);
      if (seen[key]) return;
      seen[key] = true;
      out.push(item);
    });
    return out;
  }

  global.GhDirectory = {
    esc: esc,
    emptyState: emptyState,
    tile: tile,
    sortByName: sortByName,
    sortByRecent: sortByRecent,
    sortByMlNumberDesc: sortByMlNumberDesc,
    sortByMlNumberAsc: sortByMlNumberAsc,
    sortByOldest: sortByOldest,
    parseMlNumberSeq: parseMlNumberSeq,
    matchesSearch: matchesSearch,
    filterAndSort: filterAndSort,
    bindControls: bindControls,
    getSortValue: getSortValue,
    getSearchValue: getSearchValue,
    dedupeById: dedupeById,
    SORT_RECENT: SORT_RECENT,
    SORT_OLDEST: SORT_OLDEST,
    SORT_NAME_ASC: SORT_NAME_ASC,
    SORT_NAME_DESC: SORT_NAME_DESC,
    SORT_ID_ASC: SORT_ID_ASC,
    SORT_ID_DESC: SORT_ID_DESC,
  };
})(typeof window !== 'undefined' ? window : this);

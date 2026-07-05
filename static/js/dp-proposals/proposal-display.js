/**
 * DP Proposal display: truncation, diff rendering, pre-wrap blocks.
 */
(function (global) {
  'use strict';

  function collapseSentence(s) {
    return String(s || '').replace(/\s+/g, ' ').trim();
  }

  function segmentSentences(text) {
    if (global.DpSentenceTools && global.DpSentenceTools.segmentSentences) {
      return global.DpSentenceTools.segmentSentences(text);
    }
    var out = [];
    var re = /[^.!?\u3002\n]+[.!?\u3002\n]+|[^.!?\u3002\n]+$/g;
    var m;
    while ((m = re.exec(text)) !== null) {
      out.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
    }
    if (!out.length && text.length) out.push({ start: 0, end: text.length, text: text });
    return out;
  }

  /** Core changed sentences only (no ellipsis) – for in-document highlight anchoring. */
  function focusedPassageCore(original, proposed) {
    var oS = segmentSentences(original || '');
    var pS = segmentSentences(proposed || '');
    var start = 0;
    while (start < oS.length && start < pS.length &&
      collapseSentence(oS[start].text) === collapseSentence(pS[start].text)) {
      start += 1;
    }
    var oEnd = oS.length - 1;
    var pEnd = pS.length - 1;
    while (oEnd >= start && pEnd >= start &&
      collapseSentence(oS[oEnd].text) === collapseSentence(pS[pEnd].text)) {
      oEnd -= 1;
      pEnd -= 1;
    }
    if (start > oEnd) {
      return {
        original: (original || '').trim(),
        proposed: (proposed || '').trim(),
      };
    }
    return {
      original: (original || '').slice(oS[start].start, oS[oEnd].end).trim(),
      proposed: (proposed || '').slice(pS[start].start, pS[pEnd].end).trim(),
    };
  }

  function truncateUnchangedSentences(original, proposed) {
    var oS = segmentSentences(original || '');
    var pS = segmentSentences(proposed || '');
    var start = 0;
    while (start < oS.length && start < pS.length &&
      collapseSentence(oS[start].text) === collapseSentence(pS[start].text)) {
      start += 1;
    }
    var oEnd = oS.length - 1;
    var pEnd = pS.length - 1;
    while (oEnd >= start && pEnd >= start &&
      collapseSentence(oS[oEnd].text) === collapseSentence(pS[pEnd].text)) {
      oEnd -= 1;
      pEnd -= 1;
    }
    if (start > oEnd) {
      return {
        original: original || '',
        proposed: proposed || '',
        trimmedStart: false,
        trimmedEnd: false,
      };
    }
    var origSlice = original.slice(oS[start].start, oS[oEnd].end);
    var propSlice = proposed.slice(pS[start].start, pS[pEnd].end);
    return {
      original: (start > 0 ? '\u2026\n\n' : '') + origSlice + (oEnd < oS.length - 1 ? '\n\n\u2026' : ''),
      proposed: (start > 0 ? '\u2026\n\n' : '') + propSlice + (pEnd < pS.length - 1 ? '\n\n\u2026' : ''),
      trimmedStart: start > 0,
      trimmedEnd: oEnd < oS.length - 1,
    };
  }

  function tokenizeWords(text) {
    return String(text || '').match(/\S+|\s+/g) || [];
  }

  function diffWords(original, proposed) {
    var a = tokenizeWords(original);
    var b = tokenizeWords(proposed);
    var n = a.length;
    var m = b.length;
    var dp = [];
    var i;
    var j;
    for (i = 0; i <= n; i += 1) {
      dp[i] = new Array(m + 1).fill(0);
    }
    for (i = 1; i <= n; i += 1) {
      for (j = 1; j <= m; j += 1) {
        if (a[i - 1] === b[j - 1]) dp[i][j] = dp[i - 1][j - 1] + 1;
        else dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
    var ops = [];
    i = n;
    j = m;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
        ops.unshift({ type: 'equal', text: a[i - 1] });
        i -= 1;
        j -= 1;
      } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
        ops.unshift({ type: 'ins', text: b[j - 1] });
        j -= 1;
      } else {
        ops.unshift({ type: 'del', text: a[i - 1] });
        i -= 1;
      }
    }
    return ops;
  }

  function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function buildDiffHtml(original, proposed) {
    var ops = diffWords(original, proposed);
    var html = '';
    ops.forEach(function (op) {
      var chunk = escHtml(op.text);
      if (op.type === 'equal') html += chunk;
      else if (op.type === 'del') html += '<del class="dp-diff-del">' + chunk + '</del>';
      else if (op.type === 'ins') html += '<mark class="dp-diff-ins">' + chunk + '</mark>';
    });
    return html;
  }

  function formatPreHtml(text) {
    return escHtml(text || '');
  }

  /** Character counts for insertions/deletions (uses focused passage when possible). */
  function charChangeCounts(original, proposed) {
    var o = String(original || '');
    var p = String(proposed || '');
    var core = focusedPassageCore(o, p);
    o = core.original;
    p = core.proposed;
    var ops = diffWords(o, p);
    var added = 0;
    var removed = 0;
    ops.forEach(function (op) {
      if (op.type === 'ins') added += op.text.length;
      else if (op.type === 'del') removed += op.text.length;
    });
    return { added: added, removed: removed };
  }

  function formatCharDeltaHtml(original, proposed) {
    var counts = charChangeCounts(original, proposed);
    var parts = [];
    if (counts.added > 0) {
      parts.push('<span class="dp-proposal-char-plus">+' + counts.added + '</span>');
    }
    if (counts.removed > 0) {
      parts.push('<span class="dp-proposal-char-minus">-' + counts.removed + '</span>');
    }
    if (!parts.length) {
      parts.push('<span class="dp-proposal-char-neutral">0</span>');
    }
    var label = counts.added + ' characters added, ' + counts.removed + ' characters removed';
    return '<span class="dp-proposal-char-delta" aria-label="' + escHtml(label) + '">' +
      parts.join('') + '</span>';
  }

  global.DpProposalDisplay = {
    focusedPassageCore: focusedPassageCore,
    truncateUnchangedSentences: truncateUnchangedSentences,
    charChangeCounts: charChangeCounts,
    formatCharDeltaHtml: formatCharDeltaHtml,
    buildDiffHtml: buildDiffHtml,
    formatPreHtml: formatPreHtml,
  };
})(typeof window !== 'undefined' ? window : globalThis);

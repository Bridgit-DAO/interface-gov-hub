/**
 * Sentence selection gate + expansion (Canopi-compatible algorithms).
 */
(function (global) {
  'use strict';

  var SENTENCE_CLOSE_RE = /[.!?…。！？]["'\u201d\u2019]?(\s|$)/;
  var EXPANSION_MAX_CHARS = 800;
  var EXPANSION_MAX_LENGTH_RATIO = 4;
  var DEFAULT_MIN_FRACTION = 0.75;

  function normalizeForMatch(s) {
    return String(s || '')
      .replace(/\u00a0/g, ' ')
      .replace(/\r\n/g, '\n');
  }

  function lastSentenceBreakEnd(s) {
    var last = -1;
    var re = new RegExp(SENTENCE_CLOSE_RE.source, 'g');
    var m;
    while ((m = re.exec(s)) !== null) {
      last = m.index + m[0].length;
    }
    return last;
  }

  function firstSentenceBreakEnd(s) {
    var m = SENTENCE_CLOSE_RE.exec(s);
    if (!m) return s.length;
    return m.index + m[0].length;
  }

  function expandToSentences(exact, fullText) {
    var ft = normalizeForMatch(fullText);
    var ex = normalizeForMatch(exact).trim();
    if (!ex || !ft) return exact;
    var idx = ft.indexOf(ex);
    if (idx < 0) return exact;
    var before = ft.slice(0, idx);
    var lastBreak = lastSentenceBreakEnd(before);
    var start = lastBreak >= 0 ? lastBreak : before.search(/\S/);
    if (start < 0) start = 0;
    var after = ft.slice(idx + ex.length);
    var relEnd = firstSentenceBreakEnd(after);
    var end = Math.min(ft.length, idx + ex.length + relEnd);
    var expanded = ft.slice(start, end).trim();
    if (expanded.length > ex.length * EXPANSION_MAX_LENGTH_RATIO || expanded.length > EXPANSION_MAX_CHARS) {
      return exact;
    }
    return expanded || exact;
  }

  function findBlockElement(node) {
    var blockish = {
      P: 1, LI: 1, BLOCKQUOTE: 1, TD: 1, TH: 1, DIV: 1, SECTION: 1, ARTICLE: 1,
      ASIDE: 1, MAIN: 1, HEADER: 1, FOOTER: 1, NAV: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, PRE: 1
    };
    var n = node;
    for (var i = 0; i < 20 && n; i += 1) {
      if (n.nodeType === 1 && blockish[n.tagName]) return n;
      n = n.parentNode;
    }
    return null;
  }

  function getSelectionCharOffsetsInBlock(block, range) {
    try {
      if (!block.contains(range.startContainer) || !block.contains(range.endContainer)) return null;
      var blockText = block.textContent || '';
      var fromStart = document.createRange();
      fromStart.setStart(block, 0);
      fromStart.setEnd(range.startContainer, range.startOffset);
      var start = fromStart.toString().length;
      var end = start + range.toString().length;
      return { blockText: blockText, start: start, end: end, block: block };
    } catch (_e) {
      return null;
    }
  }

  function segmentSentencesHeuristic(s) {
    var out = [];
    var re = /[^.!?\u3002\n]+[.!?\u3002\n]+|[^.!?\u3002\n]+$/g;
    var m;
    while ((m = re.exec(s)) !== null) {
      out.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
    }
    if (!out.length && s.length) out.push({ start: 0, end: s.length, text: s });
    return out;
  }

  function segmentSentences(text, locale) {
    var Seg = typeof Intl !== 'undefined' && Intl.Segmenter;
    if (Seg) {
      try {
        var seg = new Seg(locale || 'en', { granularity: 'sentence' });
        var parts = [];
        var iter = seg.segment(text);
        for (var step = iter.next(); !step.done; step = iter.next()) {
          var s = step.value;
          if (!s.segment.length) continue;
          parts.push({ start: s.index, end: s.index + s.segment.length, text: s.segment });
        }
        if (parts.length > 1 || (parts.length === 1 && parts[0].text.length < text.length * 0.99)) {
          return parts;
        }
      } catch (_e) { /* fall through */ }
    }
    return segmentSentencesHeuristic(text);
  }

  function listWordsInSlice(text, sliceStart, sliceEnd, locale) {
    var slice = text.slice(sliceStart, sliceEnd);
    var out = [];
    var Seg = typeof Intl !== 'undefined' && Intl.Segmenter;
    if (Seg) {
      try {
        var wseg = new Seg(locale || 'en', { granularity: 'word' });
        var iter = wseg.segment(slice);
        for (var step = iter.next(); !step.done; step = iter.next()) {
          var w = step.value;
          if (w.isWordLike) out.push({ segment: w.segment, index: sliceStart + w.index });
        }
        if (out.length) return out;
      } catch (_e) { /* fall through */ }
    }
    var re = /[\p{L}\p{N}]+/gu;
    var m;
    while ((m = re.exec(slice)) !== null) {
      out.push({ segment: m[0], index: sliceStart + m.index });
    }
    return out;
  }

  function userSelectionMeetsMinSentenceWordFraction(range, minF) {
    minF = minF == null ? DEFAULT_MIN_FRACTION : minF;
    if (!range || range.collapsed) return false;
    var block = findBlockElement(range.commonAncestorContainer);
    if (!block) return false;
    var off = getSelectionCharOffsetsInBlock(block, range);
    if (!off) return false;
    var locale = (document.documentElement && document.documentElement.lang) || navigator.language || 'en';
    var sentences = segmentSentences(off.blockText, locale);
    for (var i = 0; i < sentences.length; i += 1) {
      var s = sentences[i];
      if (s.end <= off.start || s.start >= off.end) continue;
      var words = listWordsInSlice(off.blockText, s.start, s.end, locale);
      if (!words.length) continue;
      var sum = 0;
      for (var w = 0; w < words.length; w += 1) {
        var w0 = words[w].index;
        var w1 = w0 + words[w].segment.length;
        var lo = Math.max(off.start, w0);
        var hi = Math.min(off.end, w1);
        sum += hi > lo ? (hi - lo) / (w1 - w0) : 0;
      }
      if (sum / words.length >= minF) return true;
    }
    return false;
  }

  function buildTextQuoteSelector(blockText, exact) {
    var norm = normalizeForMatch(blockText);
    var ex = normalizeForMatch(exact).trim();
    var idx = norm.indexOf(ex);
    if (idx < 0) {
      var flex = locateWithQuote(norm, ex, '', '');
      if (flex) {
        idx = flex.start;
      }
    }
    if (idx < 0) {
      return { type: 'TextQuoteSelector', exact: ex, prefix: '', suffix: '' };
    }
    var prefix = norm.slice(Math.max(0, idx - 64), idx);
    var suffix = norm.slice(idx + ex.length, idx + ex.length + 64);
    return {
      type: 'TextQuoteSelector',
      exact: ex,
      prefix: prefix.length > 64 ? '…' + prefix.slice(-64) : prefix,
      suffix: suffix.length > 64 ? suffix.slice(0, 64) + '…' : suffix,
    };
  }

  function escapeRegExp(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function whitespaceFlexiblePattern(phrase) {
    return escapeRegExp(normalizeForMatch(phrase).trim()).replace(/\s+/g, '\\s+');
  }

  function locateWithQuote(haystack, exact, prefix, suffix) {
    if (!exact) return null;
    var exactPattern = whitespaceFlexiblePattern(exact);
    if (prefix || suffix) {
      var pattern = '';
      if (prefix) pattern += whitespaceFlexiblePattern(String(prefix).slice(-48)) + '\\s*';
      pattern += exactPattern;
      if (suffix) pattern += '\\s*' + whitespaceFlexiblePattern(String(suffix).slice(0, 48));
      var re = new RegExp(pattern);
      var m = re.exec(haystack);
      if (m) {
        var exactRe = new RegExp(exactPattern);
        var em = exactRe.exec(m[0]);
        if (em) {
          return { start: m.index + em.index, end: m.index + em.index + em[0].length };
        }
        return { start: m.index, end: m.index + m[0].length };
      }
    }
    var onlyExact = new RegExp(exactPattern);
    var match = onlyExact.exec(haystack);
    if (!match) return null;
    return { start: match.index, end: match.index + match[0].length };
  }

  function buildTextNodeMap(root) {
    var nodes = [];
    var pos = 0;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      var len = node.textContent.length;
      if (!len) continue;
      nodes.push({ node: node, start: pos, end: pos + len });
      pos += len;
    }
    var text = '';
    for (var i = 0; i < nodes.length; i += 1) {
      text += nodes[i].node.textContent;
    }
    return { text: text, nodes: nodes };
  }

  function splitAnchorChunks(text) {
    return String(text || '')
      .split(/\n+|[.!?…]+/)
      .map(function (part) { return part.trim(); })
      .filter(function (part) { return part.length >= 24; })
      .sort(function (a, b) { return b.length - a.length; });
  }

  function trimLocatedSpan(haystack, start, end) {
    while (start < end && /\s/.test(haystack[start]) && haystack[start] !== '\n') {
      start += 1;
    }
    while (end > start && /\s/.test(haystack[end - 1]) && haystack[end - 1] !== '\n') {
      end -= 1;
    }
    while (start < end && (haystack[start] === '\n' || haystack[start] === '\r')) {
      start += 1;
    }
    while (end > start && (haystack[end - 1] === '\n' || haystack[end - 1] === '\r')) {
      end -= 1;
    }
    return { start: start, end: end };
  }

  function locateTextInRoot(root, opts) {
    opts = opts || {};
    var map = buildTextNodeMap(root);
    var haystack = normalizeForMatch(map.text);
    var original = normalizeForMatch(opts.original_text || '').trim();
    var textQuote = opts.textQuote || null;

    function finalize(loc) {
      if (!loc) return null;
      var trimmed = trimLocatedSpan(haystack, loc.start, loc.end);
      if (trimmed.end <= trimmed.start) return null;
      return { start: trimmed.start, end: trimmed.end, map: map };
    }

    if (original) {
      var direct = haystack.indexOf(original);
      if (direct >= 0) {
        return finalize({ start: direct, end: direct + original.length });
      }
      var flexOriginal = locateWithQuote(haystack, original, '', '');
      if (flexOriginal) {
        return finalize(flexOriginal);
      }
    }

    if (textQuote && textQuote.exact) {
      var quoted = locateWithQuote(
        haystack,
        textQuote.exact,
        textQuote.prefix || '',
        textQuote.suffix || ''
      );
      if (quoted) {
        return finalize(quoted);
      }
      var quotedExact = locateWithQuote(haystack, textQuote.exact, '', '');
      if (quotedExact) {
        return finalize(quotedExact);
      }
    }

    var chunks = splitAnchorChunks(original || (textQuote && textQuote.exact) || '');
    for (var i = 0; i < chunks.length; i += 1) {
      var chunkLoc = locateWithQuote(haystack, chunks[i], '', '');
      if (chunkLoc) {
        return finalize(chunkLoc);
      }
    }
    return null;
  }

  function rangeFromOffsets(map, start, end) {
    var startNode = null;
    var startOff = 0;
    var endNode = null;
    var endOff = 0;
    for (var i = 0; i < map.nodes.length; i += 1) {
      var entry = map.nodes[i];
      if (!startNode && start < entry.end) {
        startNode = entry.node;
        startOff = Math.max(0, start - entry.start);
      }
      if (end <= entry.end) {
        endNode = entry.node;
        endOff = Math.max(0, end - entry.start);
        break;
      }
    }
    if (!startNode || !endNode) return null;
    if (startNode === endNode && startOff >= endOff) return null;
    try {
      var range = document.createRange();
      range.setStart(startNode, Math.min(startOff, startNode.textContent.length));
      range.setEnd(endNode, Math.min(endOff, endNode.textContent.length));
      if (range.collapsed) return null;
      var text = range.toString();
      if (!text || !text.trim()) return null;
      return range;
    } catch (_e) {
      return null;
    }
  }

  function ensureHighlightLayer(root) {
    var layer = root.querySelector(':scope > .dp-proposal-highlight-layer');
    if (!layer) {
      if (window.getComputedStyle(root).position === 'static') {
        root.style.position = 'relative';
      }
      layer = document.createElement('div');
      layer.className = 'dp-proposal-highlight-layer';
      layer.setAttribute('aria-hidden', 'true');
      root.appendChild(layer);
    }
    return layer;
  }

  function unionClientRects(clientRects) {
    var minL = Infinity;
    var minT = Infinity;
    var maxR = -Infinity;
    var maxB = -Infinity;
    var i;
    for (i = 0; i < clientRects.length; i += 1) {
      var r = clientRects[i];
      if (r.width < 0.5 && r.height < 0.5) continue;
      minL = Math.min(minL, r.left);
      minT = Math.min(minT, r.top);
      maxR = Math.max(maxR, r.right);
      maxB = Math.max(maxB, r.bottom);
    }
    if (minL === Infinity) return null;
    return {
      left: minL,
      top: minT,
      width: maxR - minL,
      height: maxB - minT,
    };
  }

  function layoutHighlightBoxes(root, range, anchorHash) {
    var layer = ensureHighlightLayer(root);
    var rootRect = root.getBoundingClientRect();
    var scrollLeft = root.scrollLeft || 0;
    var scrollTop = root.scrollTop || 0;
    var union = unionClientRects(range.getClientRects());
    if (!union) return [];
    var box = document.createElement('div');
    box.className = 'dp-proposal-highlight-rect';
    box.dataset.dpAnchorHash = anchorHash;
    box.style.left = (union.left - rootRect.left + scrollLeft) + 'px';
    box.style.top = (union.top - rootRect.top + scrollTop) + 'px';
    box.style.width = union.width + 'px';
    box.style.height = union.height + 'px';
    layer.appendChild(box);
    return [box];
  }

  function createHighlightOverlays(root, located, anchorHash) {
    if (!located || !located.map) return null;
    var range = rangeFromOffsets(located.map, located.start, located.end);
    if (!range) return null;
    var boxes = layoutHighlightBoxes(root, range, anchorHash);
    if (!boxes.length) return null;
    return {
      anchorHash: anchorHash,
      located: located,
      boxes: boxes,
      range: range,
    };
  }

  function repositionHighlightOverlays(root, overlay) {
    if (!overlay || !overlay.located) return overlay;
    overlay.boxes.forEach(function (box) {
      if (box.parentNode) box.parentNode.removeChild(box);
    });
    var range = rangeFromOffsets(overlay.located.map, overlay.located.start, overlay.located.end);
    if (!range) {
      overlay.boxes = [];
      return overlay;
    }
    overlay.boxes = layoutHighlightBoxes(root, range, overlay.anchorHash);
    overlay.range = range;
    return overlay;
  }

  global.DpSentenceTools = {
    normalizeForMatch: normalizeForMatch,
    expandToSentences: expandToSentences,
    userSelectionMeetsMinSentenceWordFraction: userSelectionMeetsMinSentenceWordFraction,
    getSelectionCharOffsetsInBlock: getSelectionCharOffsetsInBlock,
    findBlockElement: findBlockElement,
    buildTextQuoteSelector: buildTextQuoteSelector,
    segmentSentences: segmentSentences,
    locateTextInRoot: locateTextInRoot,
    createHighlightOverlays: createHighlightOverlays,
    repositionHighlightOverlays: repositionHighlightOverlays,
    rangeFromOffsets: rangeFromOffsets,
    trimLocatedSpan: trimLocatedSpan,
    DEFAULT_MIN_FRACTION: DEFAULT_MIN_FRACTION,
  };
})(typeof window !== 'undefined' ? window : globalThis);

/**
 * Gov Hub image upload helper.
 *
 * Intercepts <input type="file" accept="image..."> (capture phase), opens
 * GhImageCrop for a single image, and always exports WebP. Multiple files
 * skip the crop UI and POST /api/images/optimize instead.
 *
 * Opt out: data-gh-crop="off"
 * Options: data-gh-aspect="16/9", data-gh-output-width, data-gh-output-height,
 *          data-gh-output-size, data-gh-title
 */
(function () {
  'use strict';

  var OPTIMIZE_URL = '/api/images/optimize';

  function parseAspect(raw) {
    if (!raw) return null;
    var s = String(raw).trim();
    if (s === 'free' || s === 'nan') return NaN;
    if (s.indexOf('/') >= 0) {
      var parts = s.split('/');
      var a = parseFloat(parts[0]);
      var b = parseFloat(parts[1]);
      if (a > 0 && b > 0) return a / b;
    }
    var n = parseFloat(s);
    return n > 0 ? n : null;
  }

  function optsFromInput(el) {
    var aspect = parseAspect(el.getAttribute('data-gh-aspect'));
    return {
      title: el.getAttribute('data-gh-title') || 'Crop image',
      aspectRatio: aspect == null ? 1 : aspect,
      outputSize: parseInt(el.getAttribute('data-gh-output-size') || '0', 10) || 600,
      outputWidth: parseInt(el.getAttribute('data-gh-output-width') || '0', 10) || 0,
      outputHeight: parseInt(el.getAttribute('data-gh-output-height') || '0', 10) || 0,
      mime: 'image/webp',
      quality: 0.82,
    };
  }

  function isImageInput(el) {
    if (!el || el.tagName !== 'INPUT' || String(el.type).toLowerCase() !== 'file') return false;
    if (el.getAttribute('data-gh-crop') === 'off') return false;
    var oc = (el.getAttribute('onchange') || '') + (el.getAttribute('data-onchange') || '');
    if (/crop/i.test(oc)) return false;
    var accept = (el.getAttribute('accept') || '').toLowerCase();
    if (accept && accept.indexOf('image') === -1 && accept.indexOf('.png') === -1 &&
        accept.indexOf('.jpg') === -1 && accept.indexOf('.webp') === -1 &&
        accept.indexOf('.gif') === -1) {
      return false;
    }
    return true;
  }

  function blobToWebpFile(blob, sourceName) {
    var base = String(sourceName || 'image').replace(/\.[^.]+$/, '');
    return new File([blob], base + '.webp', { type: 'image/webp' });
  }

  function cropFile(file, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      if (!file || (file.type && file.type === 'image/svg+xml') || /\.svg$/i.test(file.name || '')) {
        resolve(file);
        return;
      }
      if (!window.GhImageCrop || typeof window.GhImageCrop.open !== 'function') {
        optimizeViaApi(file, opts).then(resolve).catch(function () { resolve(file); });
        return;
      }
      window.GhImageCrop.open(file, {
        title: opts.title || 'Crop image',
        aspectRatio: opts.aspectRatio == null ? 1 : opts.aspectRatio,
        outputSize: opts.outputSize || 600,
        outputWidth: opts.outputWidth || 0,
        outputHeight: opts.outputHeight || 0,
        mime: 'image/webp',
        quality: opts.quality == null ? 0.82 : opts.quality,
        onConfirm: function (blob, sourceFile) {
          resolve(blobToWebpFile(blob, (sourceFile && sourceFile.name) || file.name));
        },
        onCancel: function () { resolve(null); },
      });
    });
  }

  function optimizeViaApi(file, opts) {
    opts = opts || {};
    var fd = new FormData();
    fd.append('file', file, file.name || 'image');
    if (opts.outputWidth) fd.append('max_width', String(opts.outputWidth));
    else if (opts.outputSize) fd.append('max_width', String(opts.outputSize));
    if (opts.outputHeight) fd.append('max_height', String(opts.outputHeight));
    else if (opts.outputSize) fd.append('max_height', String(opts.outputSize));
    fd.append('quality', String(Math.round((opts.quality == null ? 0.82 : opts.quality) * 100)));
    fd.append('fit', opts.fit || 'inside');
    return fetch(OPTIMIZE_URL, { method: 'POST', credentials: 'include', body: fd })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data || !res.data.data_base64) throw new Error((res.data && res.data.error) || 'optimize failed');
        var bin = atob(res.data.data_base64);
        var arr = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        var blob = new Blob([arr], { type: 'image/webp' });
        return blobToWebpFile(blob, file.name);
      });
  }

  function assignFiles(input, files) {
    var dt = new DataTransfer();
    files.forEach(function (f) { if (f) dt.items.add(f); });
    input.files = dt.files;
  }

  async function prepareInputFiles(input) {
    var list = Array.prototype.slice.call(input.files || []);
    var rasters = list.filter(function (f) {
      return f && (!f.type || f.type.indexOf('image/') === 0) && f.type !== 'image/svg+xml';
    });
    if (!rasters.length) return true;
    var opts = optsFromInput(input);
    var out = [];
    if (rasters.length === 1 && !input.multiple) {
      var cropped = await cropFile(rasters[0], opts);
      if (!cropped) return false;
      out.push(cropped);
    } else {
      for (var i = 0; i < rasters.length; i++) {
        try {
          out.push(await optimizeViaApi(rasters[i], opts));
        } catch (err) {
          out.push(rasters[i]);
        }
      }
    }
    assignFiles(input, out);
    return true;
  }

  document.addEventListener('change', function (e) {
    var el = e.target;
    if (!isImageInput(el)) return;
    if (el.dataset.ghCropReady === '1') {
      el.dataset.ghCropReady = '';
      return;
    }
    var files = el.files;
    if (!files || !files.length) return;
    var first = files[0];
    if (!first || (first.type && first.type.indexOf('image/') !== 0 && !/\.(png|jpe?g|gif|webp)$/i.test(first.name || ''))) {
      return;
    }
    e.stopImmediatePropagation();
    e.stopPropagation();
    prepareInputFiles(el).then(function (ok) {
      if (!ok) {
        el.value = '';
        return;
      }
      el.dataset.ghCropReady = '1';
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }, true);

  window.GhImageUpload = {
    cropFile: cropFile,
    optimizeViaApi: optimizeViaApi,
    prepareInputFiles: prepareInputFiles,
  };
})();

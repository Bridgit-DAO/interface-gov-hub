/**
 * GhImageCrop - image crop modal (Gov Hub + Agent Drop).
 *
 * Vendored Cropper.js (window.Cropper). Drag to pan, scroll or slider to zoom.
 * Confirm exports a Blob. Pass mime: 'image/webp' to force WebP.
 *
 * Bootstrap 5 modal is used when present; otherwise a built-in overlay is used.
 *
 *   GhImageCrop.open(file, {
 *     outputSize: 600,
 *     outputWidth: 1920,
 *     outputHeight: 1080,
 *     aspectRatio: 1,
 *     title: 'Crop Profile Picture',
 *     mime: 'image/webp',
 *     quality: 0.92,
 *     onConfirm: function(blob, sourceFile) { ... },
 *     onCancel: function() { ... },
 *   });
 *
 * Aliases: outputSize, aspectRatio, title, onConfirm, onCancel.
 */
(function () {
  'use strict';

  const MODAL_ID = 'ghImageCropModal';
  const DEFAULT_OUTPUT_SIZE = 600;
  const DEFAULT_ASPECT = 1;
  const DEFAULT_QUALITY = 0.92;

  let _cropper = null;
  let _modal = null;
  let _useBootstrap = false;
  let _callbacks = {};
  let _opts = {};
  let _objectUrl = null;

  function loadVendorCss() {
    if (document.querySelector('link[href*="cropper.min.css"]')) return Promise.resolve();
    return new Promise(function (resolve) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/static/vendor/cropperjs/cropper.min.css';
      link.onload = resolve;
      link.onerror = resolve;
      document.head.appendChild(link);
    });
  }

  function loadVendorJs() {
    if (window.Cropper) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      const script = document.createElement('script');
      script.src = '/static/vendor/cropperjs/cropper.min.js';
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('Failed to load Cropper.js')); };
      document.head.appendChild(script);
    });
  }

  const VIEWPORT_MIN_WIDTH = 560;
  const VIEWPORT_MAX_VH = 0.52;

  function cropAspectRatio(opts) {
    const aspectRatio = opts && opts.aspectRatio;
    if (typeof aspectRatio === 'number' && !isNaN(aspectRatio) && aspectRatio > 0) return aspectRatio;
    return DEFAULT_ASPECT;
  }

  function modalDialogMaxWidth(aspectRatio) {
    return aspectRatio >= 1.4 ? 720 : 640;
  }

  function layoutViewport(viewportEl, opts) {
    if (!viewportEl) return { width: VIEWPORT_MIN_WIDTH, height: VIEWPORT_MIN_WIDTH };

    const aspectRatio = cropAspectRatio(opts);
    const modalEl = viewportEl.closest('.modal');
    const dialogEl = viewportEl.closest('.modal-dialog');
    const bodyEl = viewportEl.parentElement;
    const dialogMax = modalDialogMaxWidth(aspectRatio);

    if (dialogEl) dialogEl.style.maxWidth = dialogMax + 'px';

    const bodyWidth = (bodyEl && bodyEl.clientWidth) || 0;
    const targetWidth = Math.max(
      VIEWPORT_MIN_WIDTH,
      Math.min(
        dialogMax,
        bodyWidth || Math.min(dialogMax, Math.floor(window.innerWidth * 0.9))
      )
    );
    const maxHeight = Math.min(window.innerHeight * VIEWPORT_MAX_VH, Math.round(targetWidth / aspectRatio));
    const height = Math.max(1, Math.round(Math.min(targetWidth / aspectRatio, maxHeight)));
    const width = Math.max(VIEWPORT_MIN_WIDTH, Math.round(height * aspectRatio));

    viewportEl.style.width = width + 'px';
    viewportEl.style.height = height + 'px';
    viewportEl.style.maxWidth = '100%';
    viewportEl.style.margin = '0 auto';
    viewportEl.dataset.ghCropAspect = String(aspectRatio);

    if (modalEl) modalEl.dataset.ghCropWide = aspectRatio >= 1.4 ? '1' : '';

    return { width: width, height: height };
  }

  function primeCropImage(img, viewportSize) {
    if (!img) return;
    img.style.display = 'block';
    img.style.width = viewportSize.width + 'px';
    img.style.height = 'auto';
    img.style.maxWidth = 'none';
    img.style.maxHeight = 'none';
  }

  function syncCropperContainer(viewportEl) {
    if (!viewportEl) return;
    const container = viewportEl.querySelector('.cropper-container');
    if (!container) return;
    container.style.width = '100%';
    container.style.height = '100%';
  }

  function ensureFallbackCss() {
    if (document.getElementById('ghCropFallbackCss')) return;
    const style = document.createElement('style');
    style.id = 'ghCropFallbackCss';
    style.textContent = [
      '.gh-crop-viewport{width:100%;min-width:0;max-width:100%;margin:0 auto;',
      'background:#111;overflow:hidden;position:relative;}',
      '.gh-crop-viewport>img{display:block;width:100%;height:auto;max-width:none!important;max-height:none!important;}',
      '.gh-crop-viewport>.cropper-container{width:100%!important;height:100%!important;}',
      '.gh-crop-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;}',
      '.gh-crop-toolbar-group{display:flex;gap:.35rem;}',
      '.gh-crop-toolbar-spacer{flex:1;}',
      '#ghImageCropModal.gh-crop-no-bs{position:fixed;inset:0;z-index:1080;display:none;',
      'align-items:center;justify-content:center;background:rgba(0,0,0,.65);padding:1rem;}',
      '#ghImageCropModal.gh-crop-no-bs.gh-crop-open{display:flex;}',
      '#ghImageCropModal.gh-crop-no-bs .modal-dialog{width:min(720px,100%);margin:0;}',
      '#ghImageCropModal.gh-crop-no-bs .modal-content{background:#1a1f2b;color:#e8eef8;',
      'border:1px solid #3a4254;border-radius:10px;overflow:hidden;}',
      '#ghImageCropModal.gh-crop-no-bs .modal-header,#ghImageCropModal.gh-crop-no-bs .modal-footer{',
      'display:flex;align-items:center;gap:.75rem;padding:.75rem 1rem;border-color:#3a4254;}',
      '#ghImageCropModal.gh-crop-no-bs .modal-header{border-bottom:1px solid #3a4254;}',
      '#ghImageCropModal.gh-crop-no-bs .modal-footer{border-top:1px solid #3a4254;}',
      '#ghImageCropModal.gh-crop-no-bs .modal-title{margin:0;font-size:1rem;flex:1;}',
      '#ghImageCropModal.gh-crop-no-bs .btn{background:#2a3142;color:#e8eef8;border:1px solid #4a5568;',
      'border-radius:6px;padding:.35rem .7rem;cursor:pointer;}',
      '#ghImageCropModal.gh-crop-no-bs .btn-primary{background:#3b82f6;border-color:#3b82f6;}',
      '#ghImageCropModal.gh-crop-no-bs .form-range{width:100%;}',
      '#ghImageCropModal.gh-crop-no-bs .px-3{padding:0 .75rem .75rem;}',
    ].join('');
    document.head.appendChild(style);
  }

  function guessMimeFromName(name) {
    if (!name) return '';
    const m = String(name).toLowerCase().match(/\.([a-z0-9]+)(?:\?.*)?$/);
    if (!m) return '';
    const ext = m[1];
    if (ext === 'png') return 'image/png';
    if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
    if (ext === 'gif') return 'image/gif';
    if (ext === 'webp') return 'image/webp';
    if (ext === 'svg') return 'image/svg+xml';
    return '';
  }

  function resolveOutputMime(file, requested) {
    if (requested) return requested;
    let mime = (file && file.type) ? String(file.type).toLowerCase() : '';
    if (!mime || !mime.startsWith('image/')) {
      mime = guessMimeFromName(file && file.name);
    }
    if (!mime) mime = 'image/jpeg';
    if (mime === 'image/gif' || mime === 'image/svg+xml') return 'image/png';
    return mime;
  }

  function isGifFile(file) {
    if (!file) return false;
    if (file.type && file.type.toLowerCase() === 'image/gif') return true;
    return /\.gif$/i.test(file.name || '');
  }

  function extensionForMime(mime) {
    switch (mime) {
      case 'image/png': return 'png';
      case 'image/jpeg': return 'jpg';
      case 'image/webp': return 'webp';
      case 'image/gif': return 'gif';
      default: return 'bin';
    }
  }

  function pick(opts, a, b, fallback) {
    if (opts[a] != null) return opts[a];
    if (b && opts[b] != null) return opts[b];
    return fallback;
  }

  function outputCanvasSize(opts, cropper) {
    const data = cropper.getData(true);
    const srcW = Math.max(1, data.width || 1);
    const srcH = Math.max(1, data.height || 1);
    const aspect = srcW / srcH;
    if (opts.outputWidth && opts.outputHeight) {
      return { width: opts.outputWidth | 0, height: opts.outputHeight | 0 };
    }
    const ar = opts.aspectRatio;
    const cap = (opts.outputWidth || opts.outputSize || DEFAULT_OUTPUT_SIZE) | 0;
    if (typeof ar === 'number' && ar === 1 && !opts.outputWidth) {
      return { width: cap, height: cap };
    }
    if (aspect >= 1) {
      const width = Math.min(cap, Math.round(srcW));
      return { width: width, height: Math.max(1, Math.round(width / aspect)) };
    }
    const height = Math.min(opts.outputHeight || cap, Math.round(srcH));
    return { width: Math.max(1, Math.round(height * aspect)), height: height };
  }

  function hideModal() {
    if (_useBootstrap && _modal) {
      _modal.hide();
      return;
    }
    const el = document.getElementById(MODAL_ID);
    if (!el) return;
    el.classList.remove('gh-crop-open');
    el.setAttribute('aria-hidden', 'true');
    el.dispatchEvent(new Event('hidden.bs.modal'));
  }

  function showModal(modalEl) {
    if (_useBootstrap) {
      _modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      _modal.show();
      return;
    }
    _modal = { hide: hideModal };
    modalEl.classList.add('gh-crop-open');
    modalEl.setAttribute('aria-hidden', 'false');
  }

  function onModalHidden() {
    destroyCropper();
    if (_callbacks.onCancel) _callbacks.onCancel();
    _callbacks = {};
    _opts = {};
  }

  function ensureModal() {
    ensureFallbackCss();
    if (document.getElementById(MODAL_ID)) return;

    const html = `
      <div class="modal fade" id="${MODAL_ID}" tabindex="-1" aria-labelledby="${MODAL_ID}Label" aria-hidden="true" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered gh-crop-dialog">
          <div class="modal-content bg-dark text-light border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title" id="${MODAL_ID}Label">
                <span id="${MODAL_ID}Title">Crop Image</span>
              </h5>
              <button type="button" class="btn-close btn-close-white gh-crop-dismiss" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body p-0">
              <div class="gh-crop-viewport">
                <img id="ghCropImage" src="" alt="Crop preview">
              </div>
              <div class="px-3 py-2">
                <label class="form-label text-muted small mb-1">Zoom</label>
                <input type="range" class="form-range" id="ghCropZoom" min="0" max="3" step="0.01" value="1">
                <p class="text-muted small mt-2 mb-0" id="ghCropHint">Drag to reposition, scroll to zoom.</p>
              </div>
            </div>
            <div class="modal-footer border-secondary gh-crop-toolbar">
              <div class="gh-crop-toolbar-group" role="group" aria-label="Transform tools">
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropRotateLeft" title="Rotate left 90 degrees">Rotate left</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropRotateRight" title="Rotate right 90 degrees">Rotate right</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropFlipH" title="Flip horizontal">Flip H</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropFlipV" title="Flip vertical">Flip V</button>
              </div>
              <div class="gh-crop-toolbar-spacer"></div>
              <button type="button" class="btn btn-outline-secondary gh-crop-dismiss" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" id="ghCropConfirmBtn">Use Image</button>
            </div>
          </div>
        </div>
      </div>`;

    document.body.insertAdjacentHTML('beforeend', html);

    document.getElementById('ghCropConfirmBtn').addEventListener('click', handleConfirm);
    document.getElementById('ghCropRotateLeft').addEventListener('click', function () { if (_cropper) _cropper.rotate(-90); });
    document.getElementById('ghCropRotateRight').addEventListener('click', function () { if (_cropper) _cropper.rotate(90); });
    document.getElementById('ghCropFlipH').addEventListener('click', function () {
      if (!_cropper) return;
      const d = _cropper.getData();
      _cropper.scaleX(d.scaleX === -1 ? 1 : -1);
    });
    document.getElementById('ghCropFlipV').addEventListener('click', function () {
      if (!_cropper) return;
      const d = _cropper.getData();
      _cropper.scaleY(d.scaleY === -1 ? 1 : -1);
    });

    const modalEl = document.getElementById(MODAL_ID);
    modalEl.addEventListener('hidden.bs.modal', onModalHidden);
    modalEl.querySelectorAll('.gh-crop-dismiss').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!_useBootstrap) hideModal();
      });
    });

    document.getElementById('ghCropZoom').addEventListener('input', function (e) {
      if (_cropper) _cropper.zoomTo(parseFloat(e.target.value));
    });
  }

  function configureZoomSlider() {
    const zoomSlider = document.getElementById('ghCropZoom');
    if (!zoomSlider || !_cropper) return;
    const imageData = _cropper.getImageData();
    const containerData = _cropper.getContainerData();
    const naturalRatio = Math.min(
      containerData.width / imageData.naturalWidth,
      containerData.height / imageData.naturalHeight
    );
    const currentRatio = imageData.width / imageData.naturalWidth;
    zoomSlider.value = currentRatio;
    zoomSlider.min = String(naturalRatio * 0.5);
    zoomSlider.max = String(Math.max(currentRatio * 4, naturalRatio * 6));
    zoomSlider.step = '0.001';
  }

  function startCropper(img, modalEl) {
    const viewportEl = modalEl.querySelector('.gh-crop-viewport');
    const viewportSize = layoutViewport(viewportEl, _opts);
    primeCropImage(img, viewportSize);

    const aspectRatio = _opts.aspectRatio;
    const isFreeForm = (typeof aspectRatio !== 'number') || isNaN(aspectRatio);

    _cropper = new Cropper(img, {
      aspectRatio: isFreeForm ? NaN : aspectRatio,
      viewMode: 1,
      dragMode: 'move',
      autoCropArea: 1,
      cropBoxResizable: isFreeForm,
      cropBoxMovable: isFreeForm,
      toggleDragModeOnDblclick: false,
      guides: false,
      center: true,
      background: false,
      modal: true,
      responsive: true,
      minContainerWidth: viewportSize.width,
      minContainerHeight: viewportSize.height,
      minCanvasWidth: 0,
      minCanvasHeight: 0,
      ready: function () {
        layoutViewport(viewportEl, _opts);
        syncCropperContainer(viewportEl);
        if (_cropper) {
          _cropper.reset();
          configureZoomSlider();
        }
      },
    });
  }

  function destroyCropper() {
    if (_cropper) {
      try { _cropper.destroy(); } catch (e) { /* ignore */ }
      _cropper = null;
    }
    const img = document.getElementById('ghCropImage');
    if (img) {
      img.removeAttribute('src');
      img.onload = null;
      img.style.width = '';
      img.style.height = '';
      img.style.maxWidth = '';
      img.style.maxHeight = '';
    }
    const viewportEl = document.querySelector('#' + MODAL_ID + ' .gh-crop-viewport');
    if (viewportEl) {
      viewportEl.style.width = '';
      viewportEl.style.height = '';
      viewportEl.style.maxWidth = '';
      viewportEl.style.margin = '';
      delete viewportEl.dataset.ghCropAspect;
    }
    const modalEl = document.getElementById(MODAL_ID);
    if (modalEl) delete modalEl.dataset.ghCropWide;
    const dialogEl = document.querySelector('#' + MODAL_ID + ' .modal-dialog');
    if (dialogEl) dialogEl.style.maxWidth = '';
    if (_objectUrl) {
      try { URL.revokeObjectURL(_objectUrl); } catch (e) { /* ignore */ }
      _objectUrl = null;
    }
  }

  function handleConfirm() {
    if (!_cropper) return;

    const mime = resolveOutputMime(_opts.sourceFile, _opts.mime);
    const quality = (_opts.quality == null) ? DEFAULT_QUALITY : _opts.quality;
    const dims = outputCanvasSize(_opts, _cropper);

    const canvas = _cropper.getCroppedCanvas({
      width: dims.width,
      height: dims.height,
      imageSmoothingEnabled: true,
      imageSmoothingQuality: 'high',
      fillColor: mime === 'image/jpeg' ? '#ffffff' : 'transparent',
    });

    if (!canvas) {
      console.error('GhImageCrop: getCroppedCanvas returned null');
      if (_callbacks.onCancel) _callbacks.onCancel();
      return;
    }

    canvas.toBlob(
      function (blob) {
        if (!blob) {
          console.error('GhImageCrop: toBlob returned null');
          if (_callbacks.onCancel) _callbacks.onCancel();
          return;
        }
        const cb = _callbacks.onConfirm;
        const sourceFile = _callbacks.sourceFile;
        _callbacks = {};
        hideModal();
        if (cb) cb(blob, sourceFile);
      },
      mime,
      quality
    );
  }

  async function open(file, opts) {
    opts = opts || {};
    if (!file || !(file.type ? file.type.startsWith('image/') : /\.(png|jpe?g|gif|webp|svg)$/i.test(file.name || ''))) {
      const cancel = pick(opts, 'onCancel', 'onCancel');
      if (cancel) cancel();
      return;
    }

    _callbacks = {
      onConfirm: pick(opts, 'onConfirm', 'onConfirm'),
      onCancel: pick(opts, 'onCancel', 'onCancel'),
      sourceFile: file,
    };
    _opts = {
      outputSize: pick(opts, 'outputSize', 'outputSize', DEFAULT_OUTPUT_SIZE),
      outputWidth: pick(opts, 'outputWidth', 'outputWidth', 0),
      outputHeight: pick(opts, 'outputHeight', 'outputHeight', 0),
      aspectRatio: pick(opts, 'aspectRatio', 'aspectRatio', DEFAULT_ASPECT),
      title: pick(opts, 'title', 'title', 'Crop Image'),
      mime: pick(opts, 'mime', null, 'image/webp'),
      quality: pick(opts, 'quality', null, DEFAULT_QUALITY),
      sourceFile: file,
    };

    try {
      await Promise.all([loadVendorCss(), loadVendorJs()]);
    } catch (e) {
      console.error('GhImageCrop: failed to load Cropper.js', e);
      if (_callbacks.onCancel) _callbacks.onCancel();
      _callbacks = {};
      return;
    }

    if (!window.Cropper) {
      console.error('GhImageCrop: window.Cropper missing after load');
      if (_callbacks.onCancel) _callbacks.onCancel();
      _callbacks = {};
      return;
    }

    _useBootstrap = !!(window.bootstrap && bootstrap.Modal);
    ensureModal();
    destroyCropper();

    const modalEl = document.getElementById(MODAL_ID);
    if (!_useBootstrap) modalEl.classList.add('gh-crop-no-bs');

    const titleEl = document.getElementById(MODAL_ID + 'Title');
    if (titleEl) titleEl.textContent = _opts.title;
    const hintEl = document.getElementById('ghCropHint');
    if (hintEl) {
      const fmt = _opts.mime || 'original format';
      const note = isGifFile(file)
        ? 'GIF: the first frame will be exported.'
        : 'Drag to reposition, scroll or use the slider to zoom. Export: ' + fmt + '.';
      hintEl.textContent = note;
    }

    const img = document.getElementById('ghCropImage');
    _objectUrl = URL.createObjectURL(file);
    img.src = _objectUrl;

    img.onload = function () {
      const viewportEl = modalEl.querySelector('.gh-crop-viewport');
      layoutViewport(viewportEl, _opts);

      const beginCrop = function () {
        startCropper(img, modalEl);
      };

      if (_useBootstrap) {
        modalEl.addEventListener('shown.bs.modal', beginCrop, { once: true });
        showModal(modalEl);
        return;
      }

      showModal(modalEl);
      requestAnimationFrame(function () {
        requestAnimationFrame(beginCrop);
      });
    };

    img.onerror = function () {
      console.error('GhImageCrop: image failed to load');
      if (_callbacks.onCancel) _callbacks.onCancel();
      _callbacks = {};
    };
  }

  window.GhImageCrop = {
    open: open,
    extensionForMime: extensionForMime,
  };
})();

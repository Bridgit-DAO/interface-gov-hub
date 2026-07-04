/**
 * GhImageCrop — image crop modal for Gov Hub.
 *
 * Uses a locally vendored Cropper.js (window.Cropper). Produces a square (or
 * custom-aspect) cropped Blob whose MIME matches the input file's format
 * (PNG → image/png, JPEG → image/jpeg, WebP → image/webp, GIF → image/gif,
 * unknown → image/jpeg). For GIF inputs, only the first frame is exported.
 *
 * Requires: Bootstrap 5 (modal), Cropper.js CSS+JS loaded on the page (vendored).
 *
 * Usage:
 *   GhImageCrop.open(file, {
 *     outputSize: 600,                // width AND height of output
 *     aspectRatio: 1,                 // 1 = square, 16/5 for banner, NaN to free-form
 *     title: 'Crop Profile Picture',
 *     mime: null,                     // force output MIME or null to follow input
 *     quality: 0.92,
 *     onConfirm: function(blob, sourceFile) { ... },
 *     onCancel:  function() { ... },
 *   });
 */
(function () {
  'use strict';

  const MODAL_ID = 'ghImageCropModal';
  const DEFAULT_OUTPUT_SIZE = 600;
  const DEFAULT_ASPECT = 1;
  const DEFAULT_QUALITY = 0.92;

  let _cropper = null;
  let _modal = null;
  let _callbacks = {};
  let _opts = {};
  let _objectUrl = null;
  let _imgLoadBound = false;

  // ---------------------------------------------------------------------------
  // Vendor loaders — vendored Cropper is loaded via <head>, but if a page misses
  // the script tag we still lazy-load it as a fallback. CSS is loaded the same
  // way.
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // MIME handling — preserve input format on output.
  // ---------------------------------------------------------------------------
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
    // Cropper.toBlob does not support gif/svg; for those we fall back to png.
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

  // ---------------------------------------------------------------------------
  // Modal construction (idempotent).
  // ---------------------------------------------------------------------------
  function ensureModal() {
    if (document.getElementById(MODAL_ID)) return;

    const html = `
      <div class="modal fade" id="${MODAL_ID}" tabindex="-1" aria-labelledby="${MODAL_ID}Label" aria-hidden="true" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered" style="max-width: 560px;">
          <div class="modal-content bg-dark text-light border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title" id="${MODAL_ID}Label">
                <i class="fas fa-crop-alt me-2"></i><span id="${MODAL_ID}Title">Crop Image</span>
              </h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body p-0">
              <div class="gh-crop-viewport">
                <img id="ghCropImage" src="" alt="Crop preview" style="max-width:100%;display:block;">
              </div>
              <div class="px-3 py-2">
                <label class="form-label text-muted small mb-1">Zoom</label>
                <div class="d-flex align-items-center gap-2">
                  <i class="fas fa-search-minus text-muted"></i>
                  <input type="range" class="form-range flex-grow-1" id="ghCropZoom" min="0" max="3" step="0.01" value="0">
                  <i class="fas fa-search-plus text-muted"></i>
                </div>
                <p class="text-muted small mt-2 mb-0" id="ghCropHint">Drag to reposition, scroll to zoom.</p>
              </div>
            </div>
            <div class="modal-footer border-secondary gh-crop-toolbar">
              <div class="gh-crop-toolbar-group" role="group" aria-label="Transform tools">
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropRotateLeft" title="Rotate left 90°">
                  <i class="fas fa-rotate-left"></i>
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropRotateRight" title="Rotate right 90°">
                  <i class="fas fa-rotate-right"></i>
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropFlipH" title="Flip horizontal">
                  <i class="fas fa-arrows-left-right"></i>
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="ghCropFlipV" title="Flip vertical">
                  <i class="fas fa-arrows-up-down"></i>
                </button>
              </div>
              <div class="gh-crop-toolbar-spacer"></div>
              <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" id="ghCropConfirmBtn">
                <i class="fas fa-check me-1"></i>Use Image
              </button>
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
    modalEl.addEventListener('hidden.bs.modal', function () {
      destroyCropper();
      if (_callbacks.onCancel) _callbacks.onCancel();
      _callbacks = {};
      _opts = {};
    });

    document.getElementById('ghCropZoom').addEventListener('input', function (e) {
      if (_cropper) {
        const val = parseFloat(e.target.value);
        _cropper.zoomTo(val);
      }
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
      _imgLoadBound = false;
    }
    if (_objectUrl) {
      try { URL.revokeObjectURL(_objectUrl); } catch (e) { /* ignore */ }
      _objectUrl = null;
    }
  }

  function handleConfirm() {
    if (!_cropper) return;

    const size = (_opts.outputSize || DEFAULT_OUTPUT_SIZE) | 0;
    const mime = resolveOutputMime(_opts.sourceFile, _opts.mime);
    const quality = (_opts.quality == null) ? DEFAULT_QUALITY : _opts.quality;

    const canvas = _cropper.getCroppedCanvas({
      width: size,
      height: size,
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
        if (_modal) {
          _modal.hide();
        }
        if (cb) cb(blob, sourceFile);
      },
      mime,
      quality
    );
  }

  /**
   * Open the crop modal with a File object.
   * @param {File} file - Image file from <input type="file">.
   * @param {Object} opts - see header docblock.
   */
  async function open(file, opts) {
    opts = opts || {};
    if (!file || !(file.type ? file.type.startsWith('image/') : /\.(png|jpe?g|gif|webp|svg)$/i.test(file.name || ''))) {
      if (opts.onCancel) opts.onCancel();
      return;
    }

    _callbacks = {
      onConfirm: opts.onConfirm,
      onCancel: opts.onCancel,
      sourceFile: file,
    };
    _opts = {
      outputSize: opts.outputSize || DEFAULT_OUTPUT_SIZE,
      aspectRatio: opts.aspectRatio == null ? DEFAULT_ASPECT : opts.aspectRatio,
      title: opts.title || 'Crop Image',
      mime: opts.mime == null ? null : opts.mime,
      quality: opts.quality == null ? DEFAULT_QUALITY : opts.quality,
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

    ensureModal();
    destroyCropper();

    const titleEl = document.getElementById(MODAL_ID + 'Title');
    if (titleEl) titleEl.textContent = _opts.title;
    const hintEl = document.getElementById('ghCropHint');
    if (hintEl) {
      const w = _opts.outputSize;
      const note = isGifFile(file)
        ? 'GIF: the first frame will be exported.'
        : 'Image will be exported as ' + w + '×' + w + ' matching the original format.';
      hintEl.textContent = note;
    }

    const img = document.getElementById('ghCropImage');
    _objectUrl = URL.createObjectURL(file);
    img.src = _objectUrl;
    _imgLoadBound = true;

    const modalEl = document.getElementById(MODAL_ID);
    _modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    img.onload = function () {
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
        ready: function () {
          const zoomSlider = document.getElementById('ghCropZoom');
          const imageData = _cropper.getImageData();
          const containerData = _cropper.getContainerData();
          const naturalRatio = Math.min(
            containerData.width / imageData.naturalWidth,
            containerData.height / imageData.naturalHeight
          );
          const currentRatio = imageData.width / imageData.naturalWidth;
          zoomSlider.value = currentRatio;
          zoomSlider.min = naturalRatio * 0.5;
          zoomSlider.max = Math.max(currentRatio * 4, naturalRatio * 6);
          zoomSlider.step = '0.001';
        },
      });

      _modal.show();
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

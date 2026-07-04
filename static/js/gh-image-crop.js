/**
 * GhImageCrop — square image crop modal for Gov Hub.
 *
 * Uses Cropper.js (loaded from CDN). Produces a 600×600 JPEG for upload.
 * Requires: Bootstrap 5 (modal), Cropper.js CSS+JS loaded on the page.
 *
 * Usage:
 *   GhImageCrop.open(file, { onConfirm(blob) { ... }, onCancel() { ... } })
 */
(function () {
  'use strict';

  const OUTPUT_SIZE = 600;
  const JPEG_QUALITY = 0.88;
  const MODAL_ID = 'ghImageCropModal';

  let _cropper = null;
  let _modal = null;
  let _callbacks = {};

  function ensureModal() {
    if (document.getElementById(MODAL_ID)) return;

    const html = `
      <div class="modal fade" id="${MODAL_ID}" tabindex="-1" aria-labelledby="${MODAL_ID}Label" aria-hidden="true" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered" style="max-width: 540px;">
          <div class="modal-content bg-dark text-light border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title" id="${MODAL_ID}Label">
                <i class="fas fa-crop-alt me-2"></i>Crop Layer Image
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
                <p class="text-muted small mt-2 mb-0">Drag to reposition. Image will be saved as a 600×600 square.</p>
              </div>
            </div>
            <div class="modal-footer border-secondary">
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

    const modalEl = document.getElementById(MODAL_ID);
    modalEl.addEventListener('hidden.bs.modal', function () {
      destroyCropper();
      if (_callbacks.onCancel) _callbacks.onCancel();
      _callbacks = {};
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
      _cropper.destroy();
      _cropper = null;
    }
    const img = document.getElementById('ghCropImage');
    if (img) img.src = '';
  }

  function handleConfirm() {
    if (!_cropper) return;

    const canvas = _cropper.getCroppedCanvas({
      width: OUTPUT_SIZE,
      height: OUTPUT_SIZE,
      imageSmoothingEnabled: true,
      imageSmoothingQuality: 'high',
    });

    if (!canvas) {
      console.error('GhImageCrop: getCroppedCanvas returned null');
      return;
    }

    canvas.toBlob(
      function (blob) {
        if (!blob) return;
        const cb = _callbacks.onConfirm;
        _callbacks = {};
        if (_modal) {
          _modal.hide();
        }
        if (cb) cb(blob);
      },
      'image/jpeg',
      JPEG_QUALITY
    );
  }

  function loadCropperCSS() {
    if (document.querySelector('link[href*="cropper"]')) return Promise.resolve();
    return new Promise(function (resolve) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.css';
      link.onload = resolve;
      link.onerror = resolve;
      document.head.appendChild(link);
    });
  }

  function loadCropperJS() {
    if (window.Cropper) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  /**
   * Open the crop modal with a File object.
   * @param {File} file - Image file from input
   * @param {Object} opts - { onConfirm(blob), onCancel() }
   */
  async function open(file, opts) {
    if (!file || !file.type.startsWith('image/')) {
      if (opts && opts.onCancel) opts.onCancel();
      return;
    }

    _callbacks = opts || {};

    await Promise.all([loadCropperCSS(), loadCropperJS()]);
    ensureModal();
    destroyCropper();

    const img = document.getElementById('ghCropImage');
    const url = URL.createObjectURL(file);
    img.src = url;

    const modalEl = document.getElementById(MODAL_ID);
    _modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    img.onload = function () {
      _cropper = new Cropper(img, {
        aspectRatio: 1,
        viewMode: 1,
        dragMode: 'move',
        autoCropArea: 1,
        cropBoxResizable: false,
        cropBoxMovable: false,
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
  }

  window.GhImageCrop = { open: open };
})();

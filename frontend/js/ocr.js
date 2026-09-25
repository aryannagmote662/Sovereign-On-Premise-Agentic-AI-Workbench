/**
 * OCR & Vision Inspection Module for MRPL Sovereign AI Workbench UI.
 */

const OCRPage = {
  initialized: false,

  async load() {
    if (!this.initialized) {
      this.bindEvents();
      this.initialized = true;
    }
    await this.fetchOCRHealth();
  },

  bindEvents() {
    const form = document.getElementById('ocr-upload-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.processOCR();
      });
    }
  },

  async fetchOCRHealth() {
    const healthDiv = document.getElementById('ocr-health-panel');
    if (!healthDiv) return;

    try {
      const data = await API.get('/ocr/health');
      healthDiv.innerHTML = `
        <div class="posture-strip">
          <div class="posture-cell">
            <span class="posture-label">OCR Engine</span>
            <span class="posture-value">${Utils.escapeHtml(data.ocr_engine)}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Vision Model</span>
            <span class="posture-value">${Utils.escapeHtml(data.vision_model)}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Execution Mode</span>
            <span class="posture-value" style="color: var(--status-success);">${data.local ? 'LOCAL // VERIFIED' : 'LOCAL'}</span>
          </div>
        </div>
      `;
    } catch (err) {
      healthDiv.innerHTML = `
        <div style="padding: 12px; color: var(--status-error); font-size: 0.8rem; font-family: var(--font-mono);">
          OCR TELEMETRY DESYNCHRONIZED (${Utils.escapeHtml(err.message)})
        </div>
      `;
    }
  },

  async processOCR() {
    const fileInput = document.getElementById('ocr-file-input');
    const promptInput = document.getElementById('ocr-prompt-input');
    const resultDiv = document.getElementById('ocr-result-panel');
    const submitBtn = document.getElementById('ocr-submit-btn');

    if (!fileInput || !fileInput.files.length) {
      Utils.showToast('Please select an image or scanned file', true);
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    if (promptInput && promptInput.value.trim()) {
      formData.append('prompt', promptInput.value.trim());
    }

    try {
      submitBtn.disabled = true;
      if (resultDiv) {
        resultDiv.innerHTML = `
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Optical Character Extraction</span>
              <span class="badge badge-info">PROCESSING</span>
            </div>
            <div class="tech-section-body">
              <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Executing visual analysis on '${Utils.escapeHtml(file.name)}'...</p>
            </div>
          </div>
        `;
      }

      const res = await API.upload('/ocr/process', formData);

      if (resultDiv) {
        resultDiv.innerHTML = `
          <div class="tech-section" style="border-color: var(--border-strong);">
            <div class="tech-section-header">
              <span class="tech-section-title">Extraction Matrix: ${Utils.escapeHtml(res.filename || file.name)}</span>
              ${Utils.createBadge(res.extraction_mode || 'TEXT')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix" style="margin-bottom: 16px;">
                <div class="matrix-row"><span class="matrix-label">Page Classification</span><span class="matrix-value">${Utils.escapeHtml(res.page_type || 'MIXED')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Characters Extracted</span><span class="matrix-value">${res.total_characters || 0}</span></div>
                <div class="matrix-row"><span class="matrix-label">Confidence Score</span><span class="matrix-value">${res.confidence ? res.confidence.toFixed(2) : '1.00'}</span></div>
              </div>

              <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 8px;">
                EXTRACTED OCR TERMINAL OUTPUT
              </div>
              <div style="background-color: var(--surface-2); border: 1px solid var(--border-base); border-radius: var(--radius-sm); padding: 14px; white-space: pre-wrap; font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-primary); line-height: 1.5; max-height: 500px; overflow-y: auto;">
                ${Utils.escapeHtml(res.extracted_text || 'No text extracted.')}
              </div>
            </div>
          </div>
        `;
      }

      fileInput.value = '';
    } catch (err) {
      if (resultDiv) {
        resultDiv.innerHTML = `
          <div class="tech-section" style="border-color: var(--status-error);">
            <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
              <span class="tech-section-title" style="color: var(--status-error);">OCR Extraction Fault</span>
              <span class="badge badge-error">FAULT</span>
            </div>
            <div class="tech-section-body">
              <p class="text-secondary" style="font-size: 0.8rem;">${Utils.escapeHtml(err.message)}</p>
            </div>
          </div>
        `;
      }
      Utils.showToast(err.message, true);
    } finally {
      submitBtn.disabled = false;
    }
  }
};

window.OCRPage = OCRPage;


/**
 * Document Management Module for MRPL Sovereign AI Workbench UI.
 */

const DocumentsPage = {
  initialized: false,

  async load() {
    if (!this.initialized) {
      this.bindEvents();
      this.initialized = true;
    }
    await this.fetchDocumentList();
  },

  bindEvents() {
    const form = document.getElementById('document-upload-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.uploadDocument();
      });
    }
  },

  async uploadDocument() {
    const fileInput = document.getElementById('doc-file-input');
    const statusDiv = document.getElementById('upload-status-result');
    const submitBtn = document.getElementById('doc-upload-btn');

    if (!fileInput || !fileInput.files.length) {
      Utils.showToast('Please select a file to upload', true);
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
      submitBtn.disabled = true;
      if (statusDiv) {
        statusDiv.innerHTML = `
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Document Parsing in Progress</span>
              <span class="badge badge-info">PROCESSING</span>
            </div>
            <div class="tech-section-body">
              <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Uploading and chunking document '${Utils.escapeHtml(file.name)}'...</p>
            </div>
          </div>
        `;
      }

      const res = await API.upload('/workbench/documents', formData);
      Utils.showToast(`Document '${file.name}' processed successfully!`);

      if (statusDiv) {
        statusDiv.innerHTML = `
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Ingestion Completed Successfully</span>
              ${Utils.createBadge('SUCCESS')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Filename</span><span class="matrix-value">${Utils.escapeHtml(res.filename)}</span></div>
                <div class="matrix-row"><span class="matrix-label">Document ID</span><span class="matrix-value">${Utils.escapeHtml(res.document_id)}</span></div>
                <div class="matrix-row"><span class="matrix-label">Total Pages</span><span class="matrix-value">${res.total_pages}</span></div>
                <div class="matrix-row"><span class="matrix-label">Indexed Chunks</span><span class="matrix-value">${res.indexed_chunks_count}</span></div>
                <div class="matrix-row"><span class="matrix-label">Extraction Mode</span><span class="matrix-value">${Utils.escapeHtml(res.extraction_mode)}</span></div>
              </div>
            </div>
          </div>
        `;
      }

      fileInput.value = '';
      await this.fetchDocumentList();
    } catch (err) {
      if (statusDiv) {
        statusDiv.innerHTML = `
          <div class="tech-section" style="border-color: var(--status-error);">
            <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
              <span class="tech-section-title" style="color: var(--status-error);">Ingestion Fault</span>
              <span class="badge badge-error">FAILED</span>
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
  },

  async fetchDocumentList() {
    const listContainer = document.getElementById('documents-list-container');
    if (!listContainer) return;

    try {
      const docs = await API.get('/documents');
      State.documents = docs;

      if (!docs || docs.length === 0) {
        listContainer.innerHTML = `
          <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">
            NO DOCUMENTS INDEXED IN VECTOR COLLECTION
          </div>
        `;
        return;
      }

      const rows = docs.map(d => `
        <tr>
          <td><strong style="color: var(--text-primary); font-size: 0.82rem;">${Utils.escapeHtml(d.filename)}</strong></td>
          <td><code style="color: var(--text-secondary); font-size: 0.75rem;">${Utils.escapeHtml(d.document_id)}</code></td>
          <td style="font-family: var(--font-mono); font-weight: 700;">${d.total_chunks || d.indexed_chunks_count || 0}</td>
          <td style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--text-muted);">${Utils.formatDate(d.created_at)}</td>
          <td>
            <button class="btn btn-danger btn-sm" onclick="DocumentsPage.deleteDoc('${Utils.escapeHtml(d.document_id)}')">
              Purge
            </button>
          </td>
        </tr>
      `).join('');

      listContainer.innerHTML = `
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Document ID</th>
                <th>Chunks</th>
                <th>Uploaded At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rows}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      listContainer.innerHTML = `
        <div style="padding: 16px; color: var(--status-warning); font-size: 0.8rem;">
          Could not load document repository (${Utils.escapeHtml(err.message)})
        </div>
      `;
    }
  },

  async deleteDoc(documentId) {
    if (!confirm(`Are you sure you want to delete document '${documentId}' and purge its vector entries?`)) {
      return;
    }

    try {
      const res = await API.delete(`/documents/${encodeURIComponent(documentId)}`);
      Utils.showToast(`Deleted document '${documentId}' (${res.deleted_chunks_count || 0} chunks purged).`);
      await this.fetchDocumentList();
    } catch (err) {
      Utils.showToast(`Failed to delete document: ${err.message}`, true);
    }
  }
};

window.DocumentsPage = DocumentsPage;


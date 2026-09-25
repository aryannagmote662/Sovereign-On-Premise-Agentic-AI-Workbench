/**
 * Unified Chat & Grounded QA Module for MRPL Sovereign AI Workbench UI.
 * Supports document generation (Word, PPT, PDF, Excel) and file attachments.
 */

const ChatPage = {
  initialized: false,
  selectedAttachmentFile: null,

  load() {
    if (!this.initialized) {
      this.bindEvents();
      this.initialized = true;
    }
  },

  bindEvents() {
    const sendBtn = document.getElementById('chat-send-btn');
    const inputEl = document.getElementById('chat-input');
    const clearBtn = document.getElementById('chat-clear-btn');
    const attachBtn = document.getElementById('chat-attach-btn');
    const fileInput = document.getElementById('chat-file-input');

    if (sendBtn && inputEl) {
      sendBtn.addEventListener('click', () => this.sendMessage());
      inputEl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.clearChat());
    }

    if (attachBtn && fileInput) {
      attachBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => this.handleFileSelected(e));
    }
  },

  handleFileSelected(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    this.selectedAttachmentFile = files[0];
    this.renderAttachmentPreview();
  },

  renderAttachmentPreview() {
    const previewBar = document.getElementById('chat-attachment-preview-bar');
    if (!previewBar) return;

    if (!this.selectedAttachmentFile) {
      previewBar.style.display = 'none';
      previewBar.innerHTML = '';
      return;
    }

    const file = this.selectedAttachmentFile;
    const sizeKb = (file.size / 1024).toFixed(1);
    const ext = file.name.split('.').pop().toLowerCase();
    
    let icon = '📄';
    if (['png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(ext)) icon = '🖼️';
    else if (['pdf'].includes(ext)) icon = '📕';
    else if (['xlsx', 'xls', 'csv'].includes(ext)) icon = '📈';
    else if (['pptx', 'ppt'].includes(ext)) icon = '📊';

    previewBar.style.display = 'flex';
    previewBar.innerHTML = `
      <span style="color: var(--text-secondary); font-size: 0.8rem; font-weight: 600;">Attached File:</span>
      <span class="attachment-pill">
        ${icon} <strong>${Utils.escapeHtml(file.name)}</strong> (${sizeKb} KB)
        <button type="button" class="attachment-remove-btn" title="Remove attachment" onclick="ChatPage.removeAttachment()">✕</button>
      </span>
    `;
  },

  removeAttachment() {
    this.selectedAttachmentFile = null;
    const fileInput = document.getElementById('chat-file-input');
    if (fileInput) fileInput.value = '';
    this.renderAttachmentPreview();
  },

  clearChat() {
    State.chatMessages = [];
    this.removeAttachment();
    const container = document.getElementById('chat-messages-container');
    if (container) {
      container.innerHTML = `
        <div class="message-bubble assistant">
          <div class="assistant-response-content">
            MRPL Sovereign AI Workbench initialized. System posture air-gapped. State your query, operational request, or document analysis command.
          </div>
        </div>
      `;
    }
  },

  async sendMessage() {
    const inputEl = document.getElementById('chat-input');
    const forceRagEl = document.getElementById('chat-force-rag');
    const sendBtn = document.getElementById('chat-send-btn');
    const container = document.getElementById('chat-messages-container');

    if (!inputEl || !container) return;
    const query = inputEl.value.trim();
    if (!query && !this.selectedAttachmentFile) return;

    const forceRag = forceRagEl ? forceRagEl.checked : false;
    const attachment = this.selectedAttachmentFile;

    // Build User Display Text
    let userDisplayText = query || `Processing attached file: ${attachment.name}`;
    if (attachment && query) {
      userDisplayText = `[ATTACHMENT: ${attachment.name}]\n${query}`;
    }

    // Append User Message Bubble
    this.appendMessage('user', userDisplayText);
    inputEl.value = '';

    // Disable send button & show loading bubble
    sendBtn.disabled = true;
    const loadingBubble = this.appendLoadingBubble();

    try {
      let res;
      if (attachment) {
        // Send via multipart form data with attachment
        const formData = new FormData();
        formData.append('query', query || `Analyze attached file ${attachment.name}`);
        formData.append('file', attachment);
        formData.append('force_rag', forceRag);

        res = await API.post('/workbench/chat/with-attachment', formData);
        this.removeAttachment();
      } else {
        // Standard JSON payload
        const payload = {
          query: query,
          force_rag: forceRag,
          top_k: 3
        };
        res = await API.post('/workbench/chat', payload);
      }

      loadingBubble.remove();
      this.appendAssistantResponse(res);
    } catch (err) {
      loadingBubble.remove();
      this.appendErrorMessage(err.message || 'Failed to process chat turn');
      Utils.showToast(err.message, true);
    } finally {
      sendBtn.disabled = false;
    }
  },

  appendMessage(role, text) {
    const container = document.getElementById('chat-messages-container');
    if (!container) return;

    const div = document.createElement('div');
    div.className = `message-bubble ${role}`;
    div.style.whiteSpace = 'pre-wrap';
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  },

  appendLoadingBubble() {
    const container = document.getElementById('chat-messages-container');
    const div = document.createElement('div');
    div.className = 'message-bubble assistant';
    div.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary);">
        <div class="spinner"></div> Executing local model inference & grounding vector search...
      </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  },

  appendAssistantResponse(res) {
    const container = document.getElementById('chat-messages-container');
    if (!container) return;

    const div = document.createElement('div');
    div.className = 'message-bubble assistant';

    let answerHtml = `<div class="assistant-response-content">${Utils.renderMarkdown(res.answer)}</div>`;

    if (res.status === 'FALLBACK_NO_CONTEXT') {
      answerHtml = `
        <div style="color: var(--status-warning); font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
          ⚠ Insufficient Grounding Context — Falling Back to Base LLM Knowledge
        </div>
        <div class="assistant-response-content">${Utils.renderMarkdown(res.answer)}</div>
      `;
    }

    // Deliverable Card for Generated Document Artifacts (Word, PPT, PDF, Excel, CSV)
    let artifactCardHtml = '';
    if (res.generated_artifact) {
      const art = res.generated_artifact;
      const fileType = (art.file_type || 'docx').toLowerCase();
      
      let icon = '📄';
      let iconClass = 'artifact-icon-docx';
      if (fileType === 'pptx') { icon = '📊'; iconClass = 'artifact-icon-pptx'; }
      else if (fileType === 'pdf') { icon = '📕'; iconClass = 'artifact-icon-pdf'; }
      else if (fileType === 'xlsx') { icon = '📈'; iconClass = 'artifact-icon-xlsx'; }
      else if (fileType === 'csv') { icon = '📋'; iconClass = 'artifact-icon-csv'; }

      artifactCardHtml = `
        <div class="generated-artifact-card" style="margin-top: 12px; padding: 12px; background: var(--surface-2); border: 1px solid var(--border-base); border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center;">
          <div class="artifact-left-content" style="display: flex; align-items: center; gap: 12px;">
            <div class="artifact-icon-box ${iconClass}" style="font-size: 1.2rem;">
              ${icon}
            </div>
            <div class="artifact-info-text">
              <span class="artifact-filename" style="font-weight: 700; font-size: 0.82rem; color: var(--text-primary); display: block;">${Utils.escapeHtml(art.filename)}</span>
              <span class="artifact-subtitle" style="font-size: 0.75rem; color: var(--text-secondary); display: block;">${Utils.escapeHtml(art.description || 'Generated and verified locally')}</span>
            </div>
          </div>
          <a href="${Utils.escapeHtml(art.download_url)}" download="${Utils.escapeHtml(art.filename)}" target="_blank" class="btn btn-primary btn-sm">
            Download File
          </a>
        </div>
      `;
    }

    let citationsHtml = '';
    if (res.sources && res.sources.length > 0) {
      citationsHtml = `
        <div class="citation-list" style="margin-top: 12px; border-top: 1px dashed var(--border-subtle); padding-top: 10px;">
          <div style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 6px;">
            VERIFIED GROUNDING CITATIONS (${res.sources.length})
          </div>
          ${res.sources.map(s => `
            <div class="citation-item" style="background: var(--surface-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 8px 10px; margin-bottom: 6px; font-size: 0.78rem;">
              <span style="font-weight: 700; color: var(--text-primary);">${Utils.escapeHtml(s.filename)}</span> 
              <span style="font-family: var(--font-mono); color: var(--text-muted); font-size: 0.72rem;">[Page ${s.page || 1} // Chunk ${s.chunk_id}]</span>
              ${s.snippet ? `<div style="margin-top: 4px; color: var(--text-secondary); font-size: 0.75rem; line-height: 1.4;">${Utils.escapeHtml(s.snippet)}</div>` : ''}
            </div>
          `).join('')}
        </div>
      `;
    }

    const metaHtml = `
      <div class="message-meta" style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-subtle); display: flex; flex-wrap: wrap; gap: 16px; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted);">
        <span>INTENT: <strong style="color: var(--text-secondary);">${Utils.escapeHtml(res.intent)}</strong></span>
        <span>MODEL: <strong style="color: var(--text-secondary);">${Utils.escapeHtml(res.selected_model)}</strong></span>
        <span>GROUNDED: <strong style="color: ${res.grounded_in_docs ? 'var(--status-success)' : 'var(--text-muted)'};">${res.grounded_in_docs ? 'YES' : 'NO'}</strong></span>
        <span>LATENCY: <strong style="color: var(--text-secondary);">${res.execution_time_seconds ? res.execution_time_seconds.toFixed(2) : '0.00'}s</strong></span>
      </div>
    `;

    div.innerHTML = answerHtml + artifactCardHtml + citationsHtml + metaHtml;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  },

  appendErrorMessage(errMsg) {
    const container = document.getElementById('chat-messages-container');
    if (!container) return;

    const div = document.createElement('div');
    div.className = 'message-bubble assistant';
    div.style.borderColor = 'var(--status-error)';
    div.innerHTML = `
      <div style="color: var(--status-error); font-weight: 700; font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
        Execution Fault
      </div>
      <div style="font-size: 0.8rem; color: var(--text-secondary);">${Utils.escapeHtml(errMsg)}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }
};

window.ChatPage = ChatPage;

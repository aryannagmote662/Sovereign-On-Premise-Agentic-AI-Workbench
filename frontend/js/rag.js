/**
 * Knowledge Base & RAG Query Module for MRPL Sovereign AI Workbench UI.
 */

const RAGPage = {
  initialized: false,

  async load() {
    if (!this.initialized) {
      this.bindEvents();
      this.initialized = true;
    }
    await this.fetchRAGHealth();
  },

  bindEvents() {
    const btn = document.getElementById('rag-query-btn');
    if (btn) {
      btn.addEventListener('click', () => this.runQuery());
    }
  },

  async fetchRAGHealth() {
    const headerEl = document.getElementById('rag-status-header');
    if (!headerEl) return;

    try {
      const data = await API.get('/documents/rag/health');
      headerEl.innerHTML = `
        <div class="posture-strip">
          <div class="posture-cell">
            <span class="posture-label">Vector Collection</span>
            <span class="posture-value">${Utils.escapeHtml(data.collection_name)}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Indexed Chunks</span>
            <span class="posture-value">${data.total_chunks_indexed}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Embedding Engine</span>
            <span class="posture-value">${Utils.escapeHtml(data.embedding_provider?.model_name || 'all-MiniLM-L6-v2')}</span>
          </div>
        </div>
      `;
    } catch (err) {
      headerEl.innerHTML = `
        <div style="padding: 12px; color: var(--status-error); font-size: 0.8rem; font-family: var(--font-mono);">
          RAG TELEMETRY DESYNCHRONIZED (${Utils.escapeHtml(err.message)})
        </div>
      `;
    }
  },

  async runQuery() {
    const queryEl = document.getElementById('rag-query-input');
    const topKEl = document.getElementById('rag-topk-select');
    const resultDiv = document.getElementById('rag-query-result');
    const btn = document.getElementById('rag-query-btn');

    if (!queryEl || !queryEl.value.trim()) {
      Utils.showToast('Please enter a query string', true);
      return;
    }

    const query = queryEl.value.trim();
    const topK = parseInt(topKEl ? topKEl.value : '3', 10);

    try {
      btn.disabled = true;
      if (resultDiv) {
        resultDiv.innerHTML = `
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Vector Search Execution</span>
              <span class="badge badge-info">SEARCHING</span>
            </div>
            <div class="tech-section-body">
              <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Retrieving grounded vector passages...</p>
            </div>
          </div>
        `;
      }

      const res = await API.post('/documents/query', {
        query: query,
        top_k: topK
      });

      if (resultDiv) {
        let sourcesHtml = '';
        if (res.sources && res.sources.length > 0) {
          sourcesHtml = res.sources.map(s => `
            <div class="tech-section" style="margin-bottom: 12px;">
              <div class="tech-section-header">
                <span class="tech-section-title">📄 ${Utils.escapeHtml(s.filename)} [Chunk ${s.chunk_id} // Page ${s.page || 1}]</span>
                <span class="badge badge-info">SIMILARITY: ${s.score ? s.score.toFixed(3) : 'N/A'}</span>
              </div>
              <div class="tech-section-body">
                <p style="font-size: 0.84rem; color: var(--text-primary); margin-bottom: 8px; line-height: 1.5;">
                  ${Utils.escapeHtml(s.snippet || '')}
                </p>
                <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">
                  Doc ID: ${Utils.escapeHtml(s.document_id)}
                </div>
              </div>
            </div>
          `).join('');
        } else {
          sourcesHtml = `
            <div style="padding: 16px; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">
              NO MATCHING VECTOR CHUNKS EXCEEDED SIMILARITY THRESHOLD
            </div>
          `;
        }

        resultDiv.innerHTML = `
          <div style="margin-top: 16px; display: flex; flex-direction: column; gap: 16px;">
            <div class="tech-section" style="border-color: var(--border-strong);">
              <div class="tech-section-header">
                <span class="tech-section-title">Grounded Intelligence Synthesis</span>
                <span class="badge badge-success">MODEL: ${Utils.escapeHtml(res.model_used)}</span>
              </div>
              <div class="tech-section-body">
                <div class="assistant-response-content">${Utils.renderMarkdown(res.answer)}</div>
              </div>
            </div>

            <div>
              <div style="font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-secondary); margin-bottom: 10px;">
                Retrieved Vector Passages
              </div>
              ${sourcesHtml}
            </div>
          </div>
        `;
      }
    } catch (err) {
      if (resultDiv) {
        resultDiv.innerHTML = `
          <div class="tech-section" style="border-color: var(--status-error);">
            <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
              <span class="tech-section-title" style="color: var(--status-error);">Vector Search Fault</span>
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
      btn.disabled = false;
    }
  }
};

window.RAGPage = RAGPage;


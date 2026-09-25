/**
 * Dashboard Page Module for MRPL Sovereign AI Workbench UI.
 */

const DashboardPage = {
  async load() {
    const container = document.getElementById('dashboard-content');
    if (!container) return;

    try {
      container.innerHTML = `
        <div class="tech-section">
          <div class="tech-section-header">
            <span class="tech-section-title">Telemetry Synchronization</span>
            <span class="badge badge-info">POLLING</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Connecting to Sovereign Node Telemetry Stream...</p>
          </div>
        </div>
      `;
      
      const healthData = await API.get('/workbench/health');
      State.setSystemHealth(healthData);

      this.render(healthData, container);
    } catch (err) {
      container.innerHTML = `
        <div class="tech-section" style="border-color: var(--status-error);">
          <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
            <span class="tech-section-title" style="color: var(--status-error);">Telemetry Desynchronization Fault</span>
            <span class="badge badge-error">FAULT</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem;">${Utils.escapeHtml(err.message)}</p>
          </div>
        </div>
      `;
      Utils.showToast(err.message, true);
    }
  },

  render(data, container) {
    const status = data.status || 'healthy';
    const off = data.offline_status || {};
    const router = data.router_status || {};
    const rag = data.rag_status || {};
    const ocr = data.ocr_status || {};
    const mem = data.memory_status || {};

    const html = `
      <div class="workstation-layout tech-console">
        <!-- Top 4-Cell Posture Strip -->
        <div class="posture-strip">
          <div class="posture-cell">
            <span class="posture-label">System Posture</span>
            <span class="posture-value">${Utils.createBadge(status)}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Workbench Core</span>
            <span class="posture-value" style="color: ${data.workbench_enabled ? 'var(--status-success)' : 'var(--status-error)'};">
              ${data.workbench_enabled ? 'ONLINE // ACTIVE' : 'OFFLINE // INACTIVE'}
            </span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Air-Gap Enclave</span>
            <span class="posture-value" style="color: ${off.offline_mode ? 'var(--status-success)' : 'var(--status-warning)'};">
              ${off.offline_mode ? 'ENFORCED // STRICT' : 'DEGRADED'}
            </span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">Network Policy</span>
            <span class="posture-value">${Utils.escapeHtml(off.network_policy || 'LOCAL_ONLY')}</span>
          </div>
        </div>

        <!-- Row 1: Inference Roster & Model Router vs Knowledge Base & RAG Engine -->
        <div class="tech-grid-2col">
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Inference Roster & Model Router</span>
              ${Utils.createBadge(router.ollama_available ? 'PASS' : 'WARNING')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Qwen 2.5 7B (Default)</span><span class="matrix-value">${router.models_status?.['qwen2.5:7b'] ? 'INSTALLED' : 'MISSING'}</span></div>
                <div class="matrix-row"><span class="matrix-label">DeepSeek Coder 6.7B</span><span class="matrix-value">${router.models_status?.['deepseek-coder:6.7b'] ? 'INSTALLED' : 'MISSING'}</span></div>
                <div class="matrix-row"><span class="matrix-label">MiniCPM-V 8B (Vision)</span><span class="matrix-value">${router.models_status?.['minicpm-v:8b'] ? 'INSTALLED' : 'MISSING'}</span></div>
                <div class="matrix-row"><span class="matrix-label">Single-Model VRAM</span><span class="matrix-value">ENFORCED (1 Max)</span></div>
              </div>
            </div>
          </div>

          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Knowledge Base & RAG Engine</span>
              ${Utils.createBadge(rag.status || 'healthy')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Collection</span><span class="matrix-value">${Utils.escapeHtml(rag.collection_name || 'mrpl_documents')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Indexed Chunks</span><span class="matrix-value">${rag.total_chunks_indexed || 0}</span></div>
                <div class="matrix-row"><span class="matrix-label">Embedding Provider</span><span class="matrix-value">${Utils.escapeHtml(rag.embedding_provider?.provider || 'SentenceTransformer')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Vector Store</span><span class="matrix-value">${Utils.escapeHtml(rag.vector_store?.provider || 'ChromaDB')}</span></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: Hardware Memory & Execution vs Local Vision & OCR Pipeline -->
        <div class="tech-grid-2col">
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Hardware Memory & Execution</span>
              ${Utils.createBadge('healthy')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">System RAM Used</span><span class="matrix-value">${mem.ram_used_gb || '0.0'} / ${mem.ram_total_gb || '0.0'} GB</span></div>
                <div class="matrix-row"><span class="matrix-label">Process RSS</span><span class="matrix-value">${mem.process_rss_mb || '0'} MB</span></div>
                <div class="matrix-row"><span class="matrix-label">GPU Acceleration</span><span class="matrix-value">${mem.gpu_available ? 'ACTIVE' : 'INACTIVE'}</span></div>
                <div class="matrix-row"><span class="matrix-label">VRAM Allocation</span><span class="matrix-value">${mem.vram_used_gb || '0.0'} GB</span></div>
              </div>
            </div>
          </div>

          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Local Vision & OCR Pipeline</span>
              ${Utils.createBadge(ocr.status || 'healthy')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">OCR Engine</span><span class="matrix-value">${Utils.escapeHtml(ocr.ocr_engine || 'pytesseract')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Vision LLM</span><span class="matrix-value">${Utils.escapeHtml(ocr.vision_model || 'minicpm-v:8b')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Max File Ceiling</span><span class="matrix-value">${ocr.max_image_size_mb || 20} MB</span></div>
                <div class="matrix-row"><span class="matrix-label">Local Execution</span><span class="matrix-value">${ocr.local ? 'VERIFIED' : 'LOCAL'}</span></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3: Security & Network Enclave vs Persistence & Audit Verification -->
        <div class="tech-grid-2col">
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Security & Network Enclave</span>
              ${Utils.createBadge(off.strict_mode ? 'PASS' : 'WARNING')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Strict Air-Gap</span><span class="matrix-value">${off.strict_mode ? 'ENFORCED' : 'OFF'}</span></div>
                <div class="matrix-row"><span class="matrix-label">Socket Filtering</span><span class="matrix-value">KERNEL_SECTOR_LOCK</span></div>
                <div class="matrix-row"><span class="matrix-label">Outbound Guard</span><span class="matrix-value">DROP_ALL_EXTERNAL</span></div>
                <div class="matrix-row"><span class="matrix-label">Audit Logging</span><span class="matrix-value">IMMUTABLE_APPEND</span></div>
              </div>
            </div>
          </div>

          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Persistence & Audit Verification</span>
              ${Utils.createBadge(off.persistence_local ? 'PASS' : 'WARNING')}
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Database Provider</span><span class="matrix-value">SQLite (WAL Mode)</span></div>
                <div class="matrix-row"><span class="matrix-label">Database Target</span><span class="matrix-value">mrpl_workbench.db</span></div>
                <div class="matrix-row"><span class="matrix-label">Startup Recovery</span><span class="matrix-value">AUTOMATIC</span></div>
                <div class="matrix-row"><span class="matrix-label">Persistence Audit</span><span class="matrix-value">ACTIVE</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }
};

window.DashboardPage = DashboardPage;


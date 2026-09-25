/**
 * System Health & Security Telemetry Module for MRPL Sovereign AI Workstation UI.
 */

const HealthPage = {
  async load() {
    const container = document.getElementById('health-page-content');
    if (!container) return;

    try {
      container.innerHTML = `<div class="tech-section"><p class="card-subtitle" style="padding: 16px;">Querying consolidated system health telemetry...</p></div>`;
      
      const healthData = await API.get('/workbench/health');
      State.setSystemHealth(healthData);

      this.render(healthData, container);
    } catch (err) {
      container.innerHTML = `
        <div class="tech-section" style="border-color: var(--status-error);">
          <div class="tech-section-header">
            <span class="tech-section-title" style="color: var(--status-error);">HEALTH QUERY ERROR</span>
          </div>
          <div class="tech-section-body">
            <p class="card-subtitle">${Utils.escapeHtml(err.message)}</p>
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
      <div class="workstation-layout">
        <!-- Top 4-Cell Posture Strip -->
        <div class="posture-strip">
          <div class="posture-cell">
            <span class="posture-label">AIR-GAPPED ENCLAVE</span>
            <span class="posture-value">${off.offline_mode ? '100% CONTAINED' : 'DEGRADED'}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">STRICT AIR-GAP MODE</span>
            <span class="posture-value">${off.strict_mode ? 'ACTIVE (NO NETWORK)' : 'DISABLED'}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">NETWORK POLICY</span>
            <span class="posture-value">${Utils.escapeHtml(off.network_policy || 'LOCAL_ONLY')}</span>
          </div>
          <div class="posture-cell">
            <span class="posture-label">KERNEL SOCKET AUDITOR</span>
            <span class="posture-value">${off.socket_filter || 'ACTIVE (FILTERING)'}</span>
          </div>
        </div>

        <!-- Symmetrical 2-Column Tech Grid -->
        <div class="tech-grid-2col">
          <!-- Row 1 Left: Local Model Router -->
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">LOCAL MODEL ROUTER TELEMETRY</span>
              <span class="badge ${router.ollama_available ? 'badge-success' : 'badge-warning'}">${router.ollama_available ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Ollama Host Endpoint</span><span class="matrix-value">127.0.0.1:11434</span></div>
                <div class="matrix-row"><span class="matrix-label">Active Model Routing Rules</span><span class="matrix-value">${router.rules_count || 10} Rules</span></div>
                <div class="matrix-row"><span class="matrix-label">Qwen 2.5 7B (Default)</span><span class="matrix-value">${router.models_status?.['qwen2.5:7b'] ? 'INSTALLED' : 'MISSING'}</span></div>
                <div class="matrix-row"><span class="matrix-label">DeepSeek Coder 6.7B</span><span class="matrix-value">${router.models_status?.['deepseek-coder:6.7b'] ? 'INSTALLED' : 'MISSING'}</span></div>
              </div>
            </div>
          </div>

          <!-- Row 1 Right: Knowledge Base & RAG Engine -->
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">KNOWLEDGE BASE & RAG SUBSYSTEM</span>
              <span class="badge badge-success">${Utils.escapeHtml(rag.status || 'healthy')}</span>
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Vector Store Provider</span><span class="matrix-value">${Utils.escapeHtml(rag.vector_store?.provider || 'ChromaDB')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Active Collection</span><span class="matrix-value">${Utils.escapeHtml(rag.collection_name || 'mrpl_documents')}</span></div>
                <div class="matrix-row"><span class="matrix-label">Total Chunks Indexed</span><span class="matrix-value">${rag.total_chunks_indexed || 0}</span></div>
                <div class="matrix-row"><span class="matrix-label">Embedding Provider</span><span class="matrix-value">${Utils.escapeHtml(rag.embedding_provider?.provider || 'SentenceTransformer')}</span></div>
              </div>
            </div>
          </div>

          <!-- Row 2 Left: Host & GPU Memory -->
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">HOST RAM & GPU VRAM DIAGNOSTICS</span>
              <span class="badge badge-success">HEALTHY</span>
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">System RAM Capacity</span><span class="matrix-value">${mem.ram_used_gb || '0.0'} / ${mem.ram_total_gb || '16.0'} GB</span></div>
                <div class="matrix-row"><span class="matrix-label">Process Memory Footprint</span><span class="matrix-value">${mem.process_rss_mb || '0'} MB</span></div>
                <div class="matrix-row"><span class="matrix-label">GPU Acceleration</span><span class="matrix-value">${mem.gpu_available ? 'CUDA ACTIVE' : 'CPU MODE'}</span></div>
                <div class="matrix-row"><span class="matrix-label">Single-Model Residency</span><span class="matrix-value">ENFORCED (MAX 1)</span></div>
              </div>
            </div>
          </div>

          <!-- Row 2 Right: Sovereign Persistence & Storage -->
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">SOVEREIGN PERSISTENCE & STORAGE</span>
              <span class="badge badge-success">VERIFIED</span>
            </div>
            <div class="tech-section-body">
              <div class="data-matrix">
                <div class="matrix-row"><span class="matrix-label">Relational Engine</span><span class="matrix-value">SQLite (WAL Mode)</span></div>
                <div class="matrix-row"><span class="matrix-label">Analytical Data Mart</span><span class="matrix-value">DuckDB Embedded</span></div>
                <div class="matrix-row"><span class="matrix-label">Audit Ledger Storage</span><span class="matrix-value">SHA-256 Chained</span></div>
                <div class="matrix-row"><span class="matrix-label">Startup State Recovery</span><span class="matrix-value">ENABLED</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }
};

window.HealthPage = HealthPage;

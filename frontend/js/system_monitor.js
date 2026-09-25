/**
 * Live AI System Monitor Visualization Controller for MRPL Sovereign AI Workbench UI.
 * Handles WebSocket / SSE streaming telemetry updates for Model Router, VRAM,
 * Network Security, Capability Performance, Workflow Trajectory, and Event Log Stream.
 */

const SystemMonitor = {
  socket: null,
  sseSource: null,
  pollingInterval: null,
  demoMode: false,
  collapsed: false,

  init() {
    console.log('Initializing SystemMonitor controller...');
    this.bindControls();
    this.connectTelemetryStream();
  },

  bindControls() {
    const demoBtn = document.getElementById('demo-mode-toggle-btn');
    if (demoBtn) {
      demoBtn.addEventListener('click', () => this.toggleDemoMode());
    }

    const collapseBtn = document.getElementById('monitor-collapse-btn');
    const drawerBtn = document.getElementById('toggle-monitor-drawer-btn');
    const panel = document.getElementById('system-monitor-panel');

    if (collapseBtn && panel) {
      collapseBtn.addEventListener('click', () => {
        this.collapsed = !this.collapsed;
        panel.classList.toggle('collapsed', this.collapsed);
        collapseBtn.textContent = this.collapsed ? '◀' : '⏩';
      });
    }

    if (drawerBtn && panel) {
      drawerBtn.addEventListener('click', () => {
        this.collapsed = !this.collapsed;
        panel.classList.toggle('collapsed', this.collapsed);
      });
    }
  },

  async toggleDemoMode() {
    try {
      this.demoMode = !this.demoMode;
      const res = await API.post('/system/telemetry/demo-mode', { enabled: this.demoMode });
      Utils.showToast(`Telemetry Mode: ${res.mode_label}`);
      await this.fetchTelemetryREST();
    } catch (err) {
      Utils.showToast(`Failed to toggle demo mode: ${err.message}`, true);
    }
  },

  connectTelemetryStream() {
    // Attempt WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/system/telemetry/stream`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('Telemetry WebSocket connected.');
      };

      this.socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.data) {
            this.updateUI(msg.data);
          }
        } catch (e) {
          console.error('Error parsing telemetry WS frame:', e);
        }
      };

      this.socket.onerror = () => {
        console.warn('Telemetry WS error. Falling back to SSE / REST polling.');
        this.fallbackToSSE();
      };

      this.socket.onclose = () => {
        console.log('Telemetry WS closed. Attempting reconnect in 5s...');
        setTimeout(() => this.connectTelemetryStream(), 5000);
      };
    } catch (e) {
      this.fallbackToSSE();
    }
  },

  fallbackToSSE() {
    if (this.sseSource) return;
    try {
      this.sseSource = new EventSource('/system/telemetry/stream-sse');
      this.sseSource.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.data) this.updateUI(msg.data);
        } catch (err) {}
      };
      this.sseSource.onerror = () => {
        this.sseSource.close();
        this.sseSource = null;
        this.startRESTPolling();
      };
    } catch (e) {
      this.startRESTPolling();
    }
  },

  startRESTPolling() {
    if (this.pollingInterval) return;
    this.fetchTelemetryREST();
    this.pollingInterval = setInterval(() => this.fetchTelemetryREST(), 1500);
  },

  async fetchTelemetryREST() {
    try {
      const data = await API.get('/system/telemetry');
      this.updateUI(data);
    } catch (err) {
      console.warn('Telemetry REST query notice:', err);
    }
  },

  updateUI(data) {
    if (!data) return;

    // 1. Header Badge & Demo Mode Toggle Button
    const badgeEl = document.getElementById('monitor-mode-badge');
    const demoBtn = document.getElementById('demo-mode-toggle-btn');
    const isDemo = data.telemetry_mode === 'DEMO MODE';

    if (badgeEl) {
      badgeEl.className = isDemo ? 'monitor-badge demo' : 'monitor-badge online';
      badgeEl.textContent = isDemo ? '🎭 DEMO MODE' : '● ONLINE';
    }

    if (demoBtn) {
      demoBtn.classList.toggle('active', isDemo);
    }

    // 2. Current Task Box
    const task = data.current_task || {};
    const taskNameEl = document.getElementById('current-task-name');
    const taskModelEl = document.getElementById('current-task-model');
    const taskIntentEl = document.getElementById('current-task-intent');
    const taskBadgeEl = document.getElementById('current-task-status-badge');

    if (taskNameEl) taskNameEl.textContent = `● ${task.query || 'Standby / System Ready'}`;
    if (taskModelEl) taskModelEl.textContent = `Model: ${task.model || data.active_model || 'None'}`;
    if (taskIntentEl) taskIntentEl.textContent = `Route: ${task.route || 'IDLE'} | Stage: ${task.workflow_stage || 'IDLE'}`;
    
    if (taskBadgeEl) {
      const isProcessing = task.status === 'PROCESSING';
      taskBadgeEl.className = isProcessing ? 'status-pill processing' : 'status-pill idle';
      taskBadgeEl.textContent = isProcessing ? 'PROCESSING...' : 'IDLE';
    }

    // 3. VRAM Visualization Container
    const gpu = data.gpu || {};
    const vramNoticeEl = document.getElementById('vram-telemetry-notice');
    const deviceNameEl = document.getElementById('vram-device-name');
    const usageTextEl = document.getElementById('vram-usage-text');
    const barFillEl = document.getElementById('vram-bar-fill');
    const activeModelTagEl = document.getElementById('vram-active-model-name');

    if (vramNoticeEl) {
      vramNoticeEl.textContent = gpu.telemetry_status || (gpu.available ? 'REAL TELEMETRY' : 'VRAM TELEMETRY UNAVAILABLE');
      vramNoticeEl.className = gpu.available ? 'vram-notice' : 'vram-notice warning';
    }

    if (deviceNameEl) deviceNameEl.textContent = gpu.device_name || 'NVIDIA GPU / System Budget';
    if (usageTextEl) {
      if (gpu.available) {
        usageTextEl.textContent = `${gpu.used_vram_gb || 0.0} GB / ${gpu.total_vram_gb || 16.0} GB`;
      } else {
        usageTextEl.textContent = 'TELEMETRY UNAVAILABLE';
      }
    }

    if (barFillEl) {
      const pct = gpu.available ? Math.min(100, Math.max(0, gpu.utilization_percent || 0)) : 0;
      barFillEl.style.width = `${pct}%`;
    }

    if (activeModelTagEl) {
      activeModelTagEl.textContent = data.active_model || 'None (VRAM Clear)';
    }

    // 4. Model Registry & Switch List
    this.renderModelRegistry(data.models || []);

    // 5. Workflow Stage Pipeline
    this.renderWorkflowPipeline(task.stages || {}, task.workflow_stage);

    // 6. Network Security Monitor
    const net = data.network || {};
    const netOllamaEl = document.getElementById('network-ollama-status');
    if (netOllamaEl) {
      netOllamaEl.textContent = `${net.ollama_endpoint || '127.0.0.1:11434'} ● ${net.ollama_status || 'AVAILABLE'}`;
    }

    // 7. Capability Performance Metrics
    const perf = data.performance || {};
    this.updatePerformanceMetric('code', perf.CODE);
    this.updatePerformanceMetric('ocr', perf.OCR);
    this.updatePerformanceMetric('vision', perf.VISION);
    this.updatePerformanceMetric('docgen', perf.DOCUMENT_GENERATION);

    // 8. Model Activity History
    this.renderModelHistory(data.model_history || []);

    // 9. Live Event Stream Log
    this.renderEventStream(data.event_stream || []);
  },

  renderModelRegistry(models) {
    const listEl = document.getElementById('model-registry-list');
    if (!listEl) return;

    if (!models || models.length === 0) {
      listEl.innerHTML = `<div class="history-item empty">No registered models discovered</div>`;
      return;
    }

    listEl.innerHTML = models.map(m => {
      const status = m.status || 'UNLOADED';
      let dot = '○';
      if (status === 'ACTIVE') dot = '●';
      else if (status === 'LOADED') dot = '●';
      else if (['LOADING', 'UNLOADING'].includes(status)) dot = '◐';
      else if (status === 'ERROR') dot = '×';

      return `
        <div class="model-registry-item">
          <div class="model-item-info">
            <span class="model-name-text">${Utils.escapeHtml(m.display_name || m.model_id)}</span>
            <span class="model-size-badge">${Utils.escapeHtml(m.model_size || '7B')}</span>
          </div>
          <span class="model-status-badge ${status}">
            ${dot} ${status}
          </span>
        </div>
      `;
    }).join('');
  },

  renderWorkflowPipeline(stages, activeStage) {
    const pipelineBox = document.getElementById('workflow-pipeline-box');
    if (!pipelineBox) return;

    const items = pipelineBox.querySelectorAll('.workflow-stage-item');
    items.forEach(el => {
      const stageName = el.getAttribute('data-stage');
      const st = stages[stageName] || (stageName === activeStage ? 'ACTIVE' : 'PENDING');

      el.className = `workflow-stage-item ${st}`;
      const dotEl = el.querySelector('.stage-dot');
      if (dotEl) {
        if (st === 'COMPLETED') dotEl.textContent = '✓';
        else if (st === 'ACTIVE') dotEl.textContent = '●';
        else dotEl.textContent = '○';
      }
    });
  },

  updatePerformanceMetric(key, data) {
    if (!data) return;
    const statusEl = document.getElementById(`perf-status-${key}`);
    const modelEl = document.getElementById(`perf-model-${key}`);
    const latencyEl = document.getElementById(`perf-latency-${key}`);
    const reqsEl = document.getElementById(`perf-reqs-${key}`);

    if (statusEl) statusEl.textContent = data.status || 'IDLE';
    if (modelEl) modelEl.textContent = data.model || '--';
    if (latencyEl) latencyEl.textContent = data.last_latency_seconds || '--';
    if (reqsEl) reqsEl.textContent = data.requests_processed || 0;
  },

  renderModelHistory(history) {
    const listEl = document.getElementById('model-history-list');
    if (!listEl) return;

    if (!history || history.length === 0) {
      listEl.innerHTML = `<div class="history-item empty">No model switches recorded yet</div>`;
      return;
    }

    listEl.innerHTML = history.slice(-5).reverse().map(h => `
      <div class="history-item">
        <span>${Utils.escapeHtml(h.to_model)}</span>
        <span style="color: var(--text-muted);">${h.timestamp} (${Utils.escapeHtml(h.status)})</span>
      </div>
    `).join('');
  },

  renderEventStream(events) {
    const streamEl = document.getElementById('event-stream-log');
    if (!streamEl) return;

    if (!events || events.length === 0) {
      streamEl.innerHTML = `<div class="log-entry" style="color: var(--text-muted);">Awaiting telemetry events...</div>`;
      return;
    }

    streamEl.innerHTML = events.slice(-10).map(e => `
      <div class="log-entry">
        <span class="log-time">[${e.timestamp}]</span>
        <span class="log-source">[${Utils.escapeHtml(e.source)}]</span>
        ${Utils.escapeHtml(e.message)}
      </div>
    `).join('');

    streamEl.scrollTop = streamEl.scrollHeight;
  }
};

window.SystemMonitor = SystemMonitor;

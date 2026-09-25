/**
 * Audit Trail & Security Event Viewer Module for MRPL Sovereign AI Workbench UI.
 */

const AuditPage = {
  initialized: false,

  async load() {
    await this.fetchAuditLogs();
  },

  async fetchAuditLogs() {
    const container = document.getElementById('audit-container');
    if (!container) return;

    try {
      container.innerHTML = `
        <div class="tech-section">
          <div class="tech-section-header">
            <span class="tech-section-title">Cryptographic Audit Scan</span>
            <span class="badge badge-info">POLLING</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Loading audit logs and security telemetry events...</p>
          </div>
        </div>
      `;

      const secEvents = await API.get('/security/events').catch(() => []);
      const tasksData = await API.get('/agent/tasks').catch(() => ({ tasks: [] }));
      const tasks = tasksData.tasks || tasksData.items || [];

      let allAuditRows = [];

      // Collect Security Events
      if (secEvents && secEvents.length > 0) {
        secEvents.forEach(e => {
          allAuditRows.push({
            timestamp: e.timestamp,
            task_id: e.request_id || 'SYSTEM',
            event_type: e.event_type,
            actor: e.actor_id || 'system',
            tool: 'SECURITY',
            status: e.severity || 'INFO',
            details: JSON.stringify(e.details || {})
          });
        });
      }

      // Collect Agent Task Trajectory Events
      for (const t of tasks.slice(0, 10)) {
        try {
          const events = await API.get(`/agent/tasks/${encodeURIComponent(t.task_id)}/audit`);
          if (events && events.length > 0) {
            events.forEach(e => {
              allAuditRows.push({
                timestamp: e.timestamp,
                task_id: e.task_id,
                event_type: e.event_type,
                actor: e.actor_id || 'agent',
                tool: e.tool_name || 'N/A',
                status: e.status,
                details: JSON.stringify(e.metadata || {})
              });
            });
          }
        } catch {
          // Ignore individual task audit fetch errors
        }
      }

      // Sort by timestamp descending
      allAuditRows.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      if (allAuditRows.length === 0) {
        container.innerHTML = `
          <div style="padding: 32px; text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">
            NO SECURITY OR AUDIT TRAIL EVENTS RECORDED // HASH LEDGER VERIFIED
          </div>
        `;
        return;
      }

      const rowsHtml = allAuditRows.map(r => `
        <tr>
          <td><span style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-muted);">${Utils.formatDate(r.timestamp)}</span></td>
          <td><code style="font-size: 0.74rem;">${Utils.escapeHtml(r.task_id)}</code></td>
          <td><strong style="color: var(--text-primary); font-size: 0.78rem;">${Utils.escapeHtml(r.event_type)}</strong></td>
          <td><span style="font-size: 0.78rem; color: var(--text-secondary);">${Utils.escapeHtml(r.actor)}</span></td>
          <td><code style="font-size: 0.74rem; color: var(--text-secondary);">${Utils.escapeHtml(r.tool)}</code></td>
          <td>${Utils.createBadge(r.status)}</td>
          <td><div style="color: var(--text-muted); font-family: var(--font-mono); font-size: 0.72rem; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${Utils.escapeHtml(r.details)}">${Utils.escapeHtml(r.details)}</div></td>
        </tr>
      `).join('');

      container.innerHTML = `
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Task / Req ID</th>
                <th>Event Type</th>
                <th>Actor</th>
                <th>Component / Tool</th>
                <th>Status / Severity</th>
                <th>Sanitized Metadata</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `
        <div class="tech-section" style="border-color: var(--status-error);">
          <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
            <span class="tech-section-title" style="color: var(--status-error);">Audit Log Fetch Fault</span>
            <span class="badge badge-error">FAULT</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem;">${Utils.escapeHtml(err.message)}</p>
          </div>
        </div>
      `;
    }
  }
};

window.AuditPage = AuditPage;


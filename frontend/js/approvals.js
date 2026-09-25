/**
 * Human Approval Center Module for MRPL Sovereign AI Workbench UI.
 */

const ApprovalsPage = {
  initialized: false,

  async load() {
    await this.fetchPendingApprovals();
  },

  async fetchPendingApprovals() {
    const container = document.getElementById('approvals-container');
    if (!container) return;

    try {
      container.innerHTML = `
        <div class="tech-section">
          <div class="tech-section-header">
            <span class="tech-section-title">Governance Audit Check</span>
            <span class="badge badge-info">POLLING</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Loading tasks requiring operator authorization...</p>
          </div>
        </div>
      `;

      const data = await API.get('/agent/tasks');
      const allTasks = data.tasks || data.items || [];
      const pending = allTasks.filter(t => t.status === 'WAITING_FOR_APPROVAL' || t.agent_status === 'WAITING_FOR_APPROVAL');
      State.pendingApprovals = pending;

      if (!pending || pending.length === 0) {
        container.innerHTML = `
          <div class="tech-section">
            <div class="tech-section-header">
              <span class="tech-section-title">Pending Governance Approvals</span>
              ${Utils.createBadge('healthy')}
            </div>
            <div class="tech-section-body" style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">
              NO AGENT TASKS CURRENTLY WAITING FOR OPERATOR AUTHORIZATION
            </div>
          </div>
        `;
        return;
      }

      const cardsHtml = pending.map(t => `
        <div class="tech-section" style="border-color: var(--status-warning); margin-bottom: 20px;">
          <div class="tech-section-header" style="background-color: rgba(245, 158, 11, 0.08);">
            <span class="tech-section-title">Authorization Required // Task: <code style="font-family: var(--font-mono); color: var(--text-primary);">${Utils.escapeHtml(t.task_id)}</code></span>
            ${Utils.createBadge('WAITING_FOR_APPROVAL')}
          </div>
          <div class="tech-section-body">
            <div style="margin-bottom: 14px;">
              <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 4px;">Requested Goal</div>
              <p style="font-size: 0.9rem; color: var(--text-primary); font-weight: 600;">
                ${Utils.escapeHtml(t.user_query)}
              </p>
            </div>

            <div class="data-matrix" style="margin-bottom: 14px;">
              <div class="matrix-row"><span class="matrix-label">Intent Tag</span><span class="matrix-value">${Utils.escapeHtml(t.intent || 'GENERAL_CHAT')}</span></div>
              <div class="matrix-row"><span class="matrix-label">Selected Model</span><span class="matrix-value">${Utils.escapeHtml(t.selected_model || 'qwen2.5:7b')}</span></div>
              <div class="matrix-row"><span class="matrix-label">Requested At</span><span class="matrix-value">${Utils.formatDate(t.created_at)}</span></div>
            </div>

            <div style="background-color: var(--surface-2); padding: 12px; border-radius: var(--radius-sm); border-left: 3px solid var(--status-warning); margin-bottom: 16px; font-size: 0.78rem; color: var(--text-secondary);">
              ⚠ <strong style="color: var(--text-primary);">Governance Advisory:</strong> Authorizing this request will execute tool calls sequentially under strict operator governance policy.
            </div>

            <div style="display: flex; gap: 12px;">
              <button class="btn btn-primary" onclick="ApprovalsPage.approveTask('${Utils.escapeHtml(t.task_id)}')">
                Approve & Execute Task
              </button>
              <button class="btn btn-danger" onclick="ApprovalsPage.rejectTask('${Utils.escapeHtml(t.task_id)}')">
                Reject Task
              </button>
            </div>
          </div>
        </div>
      `).join('');

      container.innerHTML = cardsHtml;
    } catch (err) {
      container.innerHTML = `
        <div class="tech-section" style="border-color: var(--status-error);">
          <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
            <span class="tech-section-title" style="color: var(--status-error);">Approval Retrieval Fault</span>
            <span class="badge badge-error">FAULT</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem;">${Utils.escapeHtml(err.message)}</p>
          </div>
        </div>
      `;
    }
  },

  async approveTask(taskId) {
    if (!confirm(`Are you sure you want to APPROVE task '${taskId}' for execution?`)) return;

    try {
      await API.post(`/agent/approve/${encodeURIComponent(taskId)}`);
      Utils.showToast(`Task '${taskId}' APPROVED for execution!`);
      await this.fetchPendingApprovals();
    } catch (err) {
      Utils.showToast(`Approval failed: ${err.message}`, true);
    }
  },

  async rejectTask(taskId) {
    if (!confirm(`Are you sure you want to REJECT task '${taskId}'?`)) return;

    try {
      await API.post(`/agent/reject/${encodeURIComponent(taskId)}`);
      Utils.showToast(`Task '${taskId}' REJECTED.`);
      await this.fetchPendingApprovals();
    } catch (err) {
      Utils.showToast(`Rejection failed: ${err.message}`, true);
    }
  }
};

window.ApprovalsPage = ApprovalsPage;


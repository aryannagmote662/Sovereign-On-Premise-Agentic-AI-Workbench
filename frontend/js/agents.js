/**
 * Agent Task Console Module for MRPL Sovereign AI Workbench UI.
 */

const AgentsPage = {
  initialized: false,

  async load() {
    if (!this.initialized) {
      this.bindEvents();
      this.initialized = true;
    }
    await this.fetchTaskList();
  },

  bindEvents() {
    const form = document.getElementById('agent-task-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.createTask();
      });
    }
  },

  async createTask() {
    const queryEl = document.getElementById('agent-query-input');
    const submitBtn = document.getElementById('agent-submit-btn');

    if (!queryEl || !queryEl.value.trim()) {
      Utils.showToast('Please enter an agent prompt', true);
      return;
    }

    const prompt = queryEl.value.trim();

    try {
      submitBtn.disabled = true;
      const res = await API.post('/agent/tasks', { query: prompt });
      Utils.showToast(`Agent task '${res.task_id}' created! Status: ${res.agent_status}`);

      queryEl.value = '';
      await this.fetchTaskList();
    } catch (err) {
      Utils.showToast(`Failed to create task: ${err.message}`, true);
    } finally {
      submitBtn.disabled = false;
    }
  },

  async fetchTaskList() {
    const container = document.getElementById('agent-tasks-container');
    if (!container) return;

    try {
      const data = await API.get('/agent/tasks');
      const tasks = data.tasks || data.items || [];
      State.agentTasks = tasks;

      if (!tasks || tasks.length === 0) {
        container.innerHTML = `
          <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">
            NO AGENT EXECUTION TASKS REGISTERED
          </div>
        `;
        return;
      }

      const rows = tasks.map(t => `
        <tr>
          <td><code style="font-size: 0.75rem;">${Utils.escapeHtml(t.task_id)}</code></td>
          <td><strong style="color: var(--text-primary); font-size: 0.82rem;">${Utils.escapeHtml(t.user_query)}</strong></td>
          <td style="font-family: var(--font-mono); font-size: 0.76rem;">${Utils.escapeHtml(t.intent || 'GENERAL_CHAT')}</td>
          <td style="font-family: var(--font-mono); font-size: 0.76rem;">${Utils.escapeHtml(t.selected_model || 'qwen2.5:7b')}</td>
          <td>${Utils.createBadge(t.agent_status || t.status)}</td>
          <td style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--text-muted);">${Utils.formatDate(t.created_at)}</td>
          <td>
            <div style="display: flex; gap: 4px;">
              <button class="btn btn-secondary btn-sm" onclick="AgentsPage.viewTaskDetails('${Utils.escapeHtml(t.task_id)}')">Inspect</button>
              ${t.status === 'RUNNING' || t.status === 'WAITING_FOR_APPROVAL' ? `<button class="btn btn-danger btn-sm" onclick="AgentsPage.cancelTask('${Utils.escapeHtml(t.task_id)}')">Abort</button>` : ''}
              ${t.status === 'INTERRUPTED' || t.status === 'FAILED' ? `<button class="btn btn-primary btn-sm" onclick="AgentsPage.resumeTask('${Utils.escapeHtml(t.task_id)}')">Resume</button>` : ''}
              <button class="btn btn-danger btn-sm" onclick="AgentsPage.deleteTask('${Utils.escapeHtml(t.task_id)}')">Delete</button>
            </div>
          </td>
        </tr>
      `).join('');

      container.innerHTML = `
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Query</th>
                <th>Intent</th>
                <th>Model</th>
                <th>Status</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rows}
            </tbody>
          </table>
        </div>
        <div id="agent-detail-view" style="margin-top: 24px;"></div>
      `;
    } catch (err) {
      container.innerHTML = `
        <div style="padding: 16px; color: var(--status-error); font-size: 0.8rem;">
          Could not load agent task registry (${Utils.escapeHtml(err.message)})
        </div>
      `;
    }
  },

  async viewTaskDetails(taskId) {
    const detailDiv = document.getElementById('agent-detail-view');
    if (!detailDiv) return;

    try {
      detailDiv.innerHTML = `
        <div class="tech-section">
          <div class="tech-section-header">
            <span class="tech-section-title">Retrieving Trajectory</span>
            <span class="badge badge-info">POLLING</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem; font-family: var(--font-mono);">Fetching task execution trajectory for '${Utils.escapeHtml(taskId)}'...</p>
          </div>
        </div>
      `;

      const task = await API.get(`/agent/tasks/${encodeURIComponent(taskId)}`);
      const timeline = await API.get(`/agent/tasks/${encodeURIComponent(taskId)}/timeline`).catch(() => []);

      let planStepsHtml = '';
      if (task.plan && task.plan.tasks) {
        planStepsHtml = task.plan.tasks.map((st, idx) => `
          <div style="background: var(--surface-2); border: 1px solid var(--border-base); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 12px;">
              <span style="font-family: var(--font-mono); font-weight: 700; font-size: 0.85rem; color: var(--text-muted);">#${idx + 1}</span>
              <div>
                <div style="font-size: 0.82rem; font-weight: 700; color: var(--text-primary);">
                  Tool: <code style="font-family: var(--font-mono); color: var(--text-secondary);">${Utils.escapeHtml(st.tool_name)}</code>
                </div>
                <div style="font-size: 0.76rem; color: var(--text-secondary); margin-top: 2px;">
                  ${Utils.escapeHtml(st.description || '')}
                </div>
              </div>
            </div>
            <div>${Utils.createBadge(st.risk_level || 'LOW')}</div>
          </div>
        `).join('');
      }

      detailDiv.innerHTML = `
        <div class="tech-section" style="border-color: var(--border-strong);">
          <div class="tech-section-header">
            <span class="tech-section-title">Task Trajectory Detail: ${Utils.escapeHtml(task.task_id)}</span>
            ${Utils.createBadge(task.status)}
          </div>
          <div class="tech-section-body">
            <div class="data-matrix" style="margin-bottom: 16px;">
              <div class="matrix-row"><span class="matrix-label">Goal / Query</span><span class="matrix-value">${Utils.escapeHtml(task.user_query)}</span></div>
              <div class="matrix-row"><span class="matrix-label">Governance Approval</span><span class="matrix-value">${Utils.escapeHtml(task.approval_status)}</span></div>
              <div class="matrix-row"><span class="matrix-label">Step Execution Progress</span><span class="matrix-value">${task.current_step} / ${task.total_steps}</span></div>
            </div>

            <div style="font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-secondary); margin-bottom: 10px;">
              Generated Task Plan Graph
            </div>
            <div class="plan-flow">
              ${planStepsHtml || '<div style="padding: 12px; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">NO STEP GRAPH AVAILABLE</div>'}
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      detailDiv.innerHTML = `
        <div class="tech-section" style="border-color: var(--status-error);">
          <div class="tech-section-header" style="background-color: rgba(239, 68, 68, 0.1);">
            <span class="tech-section-title" style="color: var(--status-error);">Trajectory Retrieval Fault</span>
            <span class="badge badge-error">FAULT</span>
          </div>
          <div class="tech-section-body">
            <p class="text-secondary" style="font-size: 0.8rem;">${Utils.escapeHtml(err.message)}</p>
          </div>
        </div>
      `;
    }
  },

  async resumeTask(taskId) {
    try {
      await API.post(`/agent/tasks/${encodeURIComponent(taskId)}/resume`);
      Utils.showToast(`Task '${taskId}' resumed successfully.`);
      await this.fetchTaskList();
    } catch (err) {
      Utils.showToast(`Resume failed: ${err.message}`, true);
    }
  },

  async cancelTask(taskId) {
    try {
      await API.post(`/agent/tasks/${encodeURIComponent(taskId)}/cancel`);
      Utils.showToast(`Task '${taskId}' cancelled.`);
      await this.fetchTaskList();
    } catch (err) {
      Utils.showToast(`Cancel failed: ${err.message}`, true);
    }
  },

  async deleteTask(taskId) {
    if (!confirm(`Are you sure you want to PERMANENTLY DELETE task '${taskId}' and purge its record?`)) {
      return;
    }

    try {
      await API.delete(`/agent/tasks/${encodeURIComponent(taskId)}`);
      Utils.showToast(`Agent task '${taskId}' deleted successfully.`);
      await this.fetchTaskList();
    } catch (err) {
      Utils.showToast(`Delete failed: ${err.message}`, true);
    }
  }
};

window.AgentsPage = AgentsPage;


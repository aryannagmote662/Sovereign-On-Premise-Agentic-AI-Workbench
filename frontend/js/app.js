/**
 * Application Entry Point Module for MRPL Sovereign AI Workbench UI.
 */

document.addEventListener('DOMContentLoaded', () => {
  console.log('Initializing MRPL Sovereign AI Workbench UI...');

  // Initialize Router, Auth & System Monitor
  Router.init();
  Auth.init();
  if (window.SystemMonitor) {
    SystemMonitor.init();
  }


  // Bind Sidebar Navigation
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const view = item.getAttribute('data-view');
      window.location.hash = `#${view}`;
    });
  });

  // Bind Theme Toggle
  const themeBtn = document.getElementById('theme-toggle-btn');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const currentTheme = document.body.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      document.body.setAttribute('data-theme', newTheme);
      themeBtn.textContent = newTheme === 'dark' ? '☀️ Light' : '🌙 Dark';
    });
  }

  // Bind Validate Offline Posture Button
  const validateBtn = document.getElementById('validate-offline-btn');
  if (validateBtn) {
    validateBtn.addEventListener('click', async () => {
      try {
        validateBtn.disabled = true;
        Utils.showToast('Executing offline posture validation...');
        const res = await API.post('/security/offline/validate');
        Utils.showToast(`Offline Posture Check: ${res.status.toUpperCase()}`);
        await updateGlobalHealth();
      } catch (err) {
        Utils.showToast(`Offline validation error: ${err.message}`, true);
      } finally {
        validateBtn.disabled = false;
      }
    });
  }

  // Initial Health Fetch
  updateGlobalHealth();

  // Periodic Health Polling (Every 20 Seconds)
  setInterval(updateGlobalHealth, 20000);
});

/**
 * Global telemetry update function refreshing topbar indicators.
 */
async function updateGlobalHealth() {
  try {
    const health = await API.get('/workbench/health');
    State.setSystemHealth(health);

    const badgeEl = document.getElementById('offline-status-badge');
    if (badgeEl) {
      const off = health.offline_status || {};
      const isHealthy = off.status === 'healthy' || off.status === 'degraded';

      if (isHealthy && off.offline_mode) {
        badgeEl.className = 'offline-badge';
        badgeEl.innerHTML = `<span class="status-dot"></span> AIR-GAPPED / OFFLINE`;
      } else {
        badgeEl.className = 'offline-badge warning';
        badgeEl.innerHTML = `<span class="status-dot warning"></span> SECURITY WARNING`;
      }
    }
  } catch (err) {
    const badgeEl = document.getElementById('offline-status-badge');
    if (badgeEl) {
      badgeEl.className = 'offline-badge warning';
      badgeEl.innerHTML = `<span class="status-dot warning"></span> OFFLINE CHECK FAILED`;
    }
  }
}

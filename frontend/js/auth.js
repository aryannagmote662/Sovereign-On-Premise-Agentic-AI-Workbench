/**
 * Authentication, RBAC/ABAC Session & User Management Module for MRPL AI Workbench UI.
 */

const Auth = {
  currentUser: null,
  initialized: false,

  init() {
    if (this.initialized) return;
    this.bindEvents();
    this.initialized = true;
    this.checkSession();
  },

  bindEvents() {
    // Login form submission
    const loginForm = document.getElementById('auth-login-form');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.login();
      });
    }

    // Register form submission
    const registerForm = document.getElementById('auth-register-form');
    if (registerForm) {
      registerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.register();
      });
    }

    // Toggle between login and register views
    const showRegisterLink = document.getElementById('show-register-btn');
    const showLoginLink = document.getElementById('show-login-btn');
    if (showRegisterLink) {
      showRegisterLink.addEventListener('click', (e) => {
        e.preventDefault();
        this.toggleAuthScreen('register');
      });
    }
    if (showLoginLink) {
      showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        this.toggleAuthScreen('login');
      });
    }

    // Logout button
    const logoutBtn = document.getElementById('auth-logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', (e) => {
        if (e) e.preventDefault();
        this.logout();
      });
    }

    // Quick seed login buttons for dev convenience
    const seedBtns = document.querySelectorAll('.seed-login-btn');
    seedBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const btnEl = e.currentTarget || e.target.closest('.seed-login-btn');
        const username = btnEl ? btnEl.getAttribute('data-email') : null;
        const password = btnEl ? btnEl.getAttribute('data-password') : null;
        if (username && password) {
          this.quickLogin(username, password);
        }
      });
    });
  },

  quickLogin(email, password) {
    const emailEl = document.getElementById('login-email');
    const passwordEl = document.getElementById('login-password');
    if (emailEl && passwordEl) {
      emailEl.value = email;
      passwordEl.value = password;
      this.login();
    }
  },

  toggleAuthScreen(screen) {
    const loginCard = document.getElementById('auth-login-card');
    const registerCard = document.getElementById('auth-register-card');
    if (screen === 'register') {
      if (loginCard) loginCard.style.display = 'none';
      if (registerCard) registerCard.style.display = 'block';
    } else {
      if (registerCard) registerCard.style.display = 'none';
      if (loginCard) loginCard.style.display = 'block';
    }
  },

  async checkSession() {
    const token = localStorage.getItem('mrpl_token');
    if (!token) {
      const badgeContainer = document.getElementById('user-profile-badge');
      if (badgeContainer) badgeContainer.innerHTML = '';
      this.showAuthModal(true);
      return;
    }

    try {
      const user = await API.get('/auth/me');
      this.currentUser = user;
      this.showAuthModal(false);
      this.updateUIForUser(user);
    } catch (err) {
      console.warn('Session check failed, requesting login:', err.message);
      localStorage.removeItem('mrpl_token');
      const badgeContainer = document.getElementById('user-profile-badge');
      if (badgeContainer) badgeContainer.innerHTML = '';
      this.currentUser = null;
      this.showAuthModal(true);
    }
  },

  async login() {
    const emailEl = document.getElementById('login-email');
    const passwordEl = document.getElementById('login-password');
    const statusEl = document.getElementById('login-status-msg');

    if (!emailEl || !passwordEl) return;
    const username = emailEl.value.trim();
    const password = passwordEl.value;

    if (!username || !password) {
      if (statusEl) statusEl.textContent = 'Please enter email and password.';
      return;
    }

    if (statusEl) statusEl.textContent = 'Authenticating...';

    try {
      const data = await API.post('/auth/login', { username, password });
      localStorage.setItem('mrpl_token', data.access_token);
      
      this.currentUser = {
        user_id: data.user_id,
        full_name: data.full_name,
        email: data.email,
        role: data.role,
        department: data.department,
        workspace_id: data.workspace_id,
        clearance_level: data.clearance_level,
        status: data.status,
        permissions: data.permissions
      };

      if (statusEl) statusEl.textContent = '';
      this.showAuthModal(false);
      this.updateUIForUser(this.currentUser);
      Utils.showToast(`Welcome back, ${data.full_name}!`);
    } catch (err) {
      if (statusEl) statusEl.textContent = err.message || 'Login failed.';
      Utils.showToast(err.message || 'Login failed.', true);
    }
  },

  async register() {
    const nameEl = document.getElementById('reg-name');
    const emailEl = document.getElementById('reg-email');
    const pwdEl = document.getElementById('reg-password');
    const pwdConfEl = document.getElementById('reg-password-confirm');
    const deptEl = document.getElementById('reg-department');
    const roleEl = document.getElementById('reg-role');
    const statusEl = document.getElementById('register-status-msg');

    if (!nameEl || !emailEl || !pwdEl || !pwdConfEl) return;

    const full_name = nameEl.value.trim();
    const email = emailEl.value.trim();
    const password = pwdEl.value;
    const pwdConf = pwdConfEl.value;
    const department = deptEl ? deptEl.value : 'Operations';
    const requested_role = roleEl ? roleEl.value : 'PLANT_OPERATOR';

    if (password !== pwdConf) {
      if (statusEl) statusEl.textContent = 'Passwords do not match.';
      return;
    }

    if (statusEl) statusEl.textContent = 'Submitting registration...';

    try {
      const res = await API.post('/auth/register', {
        full_name,
        email,
        password,
        department,
        requested_role
      });

      if (statusEl) {
        statusEl.style.color = 'var(--status-success)';
        statusEl.textContent = 'Registration submitted! Account pending administrator approval.';
      }
      Utils.showToast('Registration submitted successfully! Please ask an administrator to activate your account.');
      
      setTimeout(() => {
        this.toggleAuthScreen('login');
      }, 2500);
    } catch (err) {
      if (statusEl) {
        statusEl.style.color = 'var(--status-error)';
        statusEl.textContent = err.message || 'Registration failed.';
      }
      Utils.showToast(err.message || 'Registration failed.', true);
    }
  },

  async logout() {
    try {
      await API.post('/auth/logout');
    } catch (e) {
      console.warn('Logout endpoint notice:', e.message);
    } finally {
      localStorage.removeItem('mrpl_token');
      this.currentUser = null;
      const badgeContainer = document.getElementById('user-profile-badge');
      if (badgeContainer) badgeContainer.innerHTML = '';
      this.showAuthModal(true);
      Utils.showToast('Logged out successfully.');
    }
  },

  showAuthModal(show) {
    const modal = document.getElementById('auth-modal-overlay');
    const appContainer = document.getElementById('app-container');
    if (modal) {
      modal.style.display = show ? 'flex' : 'none';
    }
    if (appContainer) {
      appContainer.style.filter = show ? 'blur(4px)' : 'none';
      appContainer.style.pointerEvents = show ? 'none' : 'auto';
    }
  },

  updateUIForUser(user) {
    if (!user) {
      const badgeContainer = document.getElementById('user-profile-badge');
      if (badgeContainer) badgeContainer.innerHTML = '';
      return;
    }

    // Update Topbar User Badge
    const badgeContainer = document.getElementById('user-profile-badge');
    if (badgeContainer) {
      badgeContainer.innerHTML = `
        <div class="user-badge-item">
          <span class="user-icon">👤</span>
          <div>
            <div style="font-weight: 600; color: var(--text-primary); font-size: 0.85rem;">${Utils.escapeHtml(user.full_name || user.email)}</div>
            <div style="font-size: 0.72rem; color: var(--accent-teal);">
              Role: <strong>${Utils.escapeHtml(user.role)}</strong> | WS: <strong>${Utils.escapeHtml(user.workspace_id)}</strong> | Lvl <strong>${user.clearance_level}</strong>
            </div>
          </div>
        </div>
      `;
    }

    // Dynamic Navigation Visibility Based on Role Permissions
    const navUsers = document.getElementById('nav-users');
    const navApprovals = document.getElementById('nav-approvals');
    const navAudit = document.getElementById('nav-audit');
    const navAgents = document.getElementById('nav-agents');
    const navRag = document.getElementById('nav-rag');
    const navOcr = document.getElementById('nav-ocr');

    const role = user.role;
    const permissions = user.permissions || [];

    if (navUsers) {
      navUsers.style.display = (role === 'AI_IT_ADMIN' || permissions.includes('user.view')) ? 'flex' : 'none';
    }
    if (navApprovals) {
      navApprovals.style.display = (permissions.includes('approval.view') || permissions.includes('approval.approve')) ? 'flex' : 'none';
    }
    if (navAudit) {
      navAudit.style.display = permissions.includes('audit.view') ? 'flex' : 'none';
    }
    if (navAgents) {
      navAgents.style.display = permissions.includes('code.generate') || role === 'ENGINEER' || role === 'AI_IT_ADMIN' ? 'flex' : 'none';
    }

    // If User Management View is active and user is admin, load user catalog
    if (window.location.hash === '#users' && (role === 'AI_IT_ADMIN' || role === 'ADMIN')) {
      this.loadUserCatalog();
    }
  },

  async loadUserCatalog() {
    const container = document.getElementById('users-list-container');
    if (!container) return;

    container.innerHTML = '<p class="card-subtitle">Loading platform user catalog...</p>';

    try {
      const users = await API.get('/auth/users');
      if (!users || users.length === 0) {
        container.innerHTML = '<p class="card-subtitle">No user records found.</p>';
        return;
      }

      container.innerHTML = `
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Full Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Department</th>
                <th>Workspace</th>
                <th>Clearance</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${users.map(u => `
                <tr>
                  <td><code>${Utils.escapeHtml(u.user_id)}</code></td>
                  <td><strong>${Utils.escapeHtml(u.full_name)}</strong></td>
                  <td>${Utils.escapeHtml(u.email)}</td>
                  <td><span class="badge badge-info">${Utils.escapeHtml(u.role)}</span></td>
                  <td>${Utils.escapeHtml(u.department)}</td>
                  <td><code>${Utils.escapeHtml(u.workspace_id)}</code></td>
                  <td><span class="badge ${u.clearance_level >= 4 ? 'badge-warning' : 'badge-healthy'}">Level ${u.clearance_level}</span></td>
                  <td><span class="badge ${u.status === 'ACTIVE' ? 'badge-success' : (u.status === 'PENDING' ? 'badge-warning' : 'badge-error')}">${Utils.escapeHtml(u.status)}</span></td>
                  <td>
                    <button class="btn btn-secondary btn-sm" onclick="Auth.showEditUserModal('${u.user_id}', '${Utils.escapeHtml(u.role)}', '${Utils.escapeHtml(u.workspace_id)}', ${u.clearance_level}, '${u.status}')">
                      ✏ Edit / Approve
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color: var(--status-error);">Failed to load user catalog: ${Utils.escapeHtml(err.message)}</div>`;
    }
  },

  showEditUserModal(userId, currentRole, currentWs, currentClearance, currentStatus) {
    const targetUserIdEl = document.getElementById('edit-user-id');
    const roleSelect = document.getElementById('edit-user-role');
    const wsInput = document.getElementById('edit-user-workspace');
    const clearanceSelect = document.getElementById('edit-user-clearance');
    const statusSelect = document.getElementById('edit-user-status');
    const modal = document.getElementById('edit-user-modal');

    if (targetUserIdEl) targetUserIdEl.value = userId;
    if (roleSelect) roleSelect.value = currentRole;
    if (wsInput) wsInput.value = currentWs;
    if (clearanceSelect) clearanceSelect.value = currentClearance;
    if (statusSelect) statusSelect.value = currentStatus;

    if (modal) modal.style.display = 'flex';
  },

  closeEditUserModal() {
    const modal = document.getElementById('edit-user-modal');
    if (modal) modal.style.display = 'none';
  },

  async submitUserUpdate() {
    const userId = document.getElementById('edit-user-id').value;
    const role = document.getElementById('edit-user-role').value;
    const workspace_id = document.getElementById('edit-user-workspace').value.trim();
    const clearance_level = parseInt(document.getElementById('edit-user-clearance').value, 10);
    const status = document.getElementById('edit-user-status').value;

    try {
      await API.post('/auth/users/update', {
        user_id: userId,
        role,
        workspace_id,
        clearance_level,
        status
      });

      Utils.showToast('User account updated successfully!');
      this.closeEditUserModal();
      this.loadUserCatalog();
    } catch (err) {
      Utils.showToast(err.message || 'Failed to update user account', true);
    }
  }
};

window.Auth = Auth;

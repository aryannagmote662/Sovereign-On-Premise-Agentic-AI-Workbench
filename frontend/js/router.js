/**
 * SPA View Router for MRPL Sovereign AI Workbench UI.
 * Handles tab navigation and updates DOM active classes.
 */

const Router = {
  routes: {
    'dashboard': 'Dashboard',
    'chat': 'Unified Chat',
    'documents': 'Document Management',
    'rag': 'Knowledge Base / RAG',
    'ocr': 'OCR & Vision Inspection',
    'agents': 'Agent Task Console',
    'approvals': 'Human Approval Center',
    'audit': 'Audit Trajectory Log',
    'health': 'System Health & Security',
  },

  init() {
    window.addEventListener('hashchange', () => this.handleHashChange());
    this.handleHashChange();
  },

  handleHashChange() {
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    const route = this.routes[hash] ? hash : 'dashboard';
    this.navigateTo(route);
  },

  navigateTo(viewName) {
    if (!this.routes[viewName]) return;

    // Update state
    State.setView(viewName);

    // Update DOM panels
    document.querySelectorAll('.content-panel').forEach(panel => {
      panel.classList.remove('active');
    });

    const targetPanel = document.getElementById(`${viewName}-view`);
    if (targetPanel) {
      targetPanel.classList.add('active');
      if (window.Animations) {
        Animations.animateViewEntrance(targetPanel);
      }
    }

    // Update Sidebar items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
      if (item.getAttribute('data-view') === viewName) {
        item.classList.add('active');
      }
    });

    // Update Topbar Title
    const titleEl = document.getElementById('page-title');
    if (titleEl) {
      titleEl.textContent = this.routes[viewName];
    }

    // Trigger page-specific data load
    this.loadViewData(viewName);
  },

  loadViewData(viewName) {
    switch (viewName) {
      case 'dashboard':
        if (window.DashboardPage) window.DashboardPage.load();
        break;
      case 'chat':
        if (window.ChatPage) window.ChatPage.load();
        break;
      case 'documents':
        if (window.DocumentsPage) window.DocumentsPage.load();
        break;
      case 'rag':
        if (window.RAGPage) window.RAGPage.load();
        break;
      case 'ocr':
        if (window.OCRPage) window.OCRPage.load();
        break;
      case 'agents':
        if (window.AgentsPage) window.AgentsPage.load();
        break;
      case 'approvals':
        if (window.ApprovalsPage) window.ApprovalsPage.load();
        break;
      case 'audit':
        if (window.AuditPage) window.AuditPage.load();
        break;
      case 'health':
        if (window.HealthPage) window.HealthPage.load();
        break;
    }
  }
};

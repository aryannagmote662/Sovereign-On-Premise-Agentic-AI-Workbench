/**
 * Centralized API Client Module for MRPL Sovereign AI Workbench.
 * Uses relative same-origin HTTP requests exclusively.
 */

const API = {
  /**
   * Core fetch request wrapper with centralized error handling.
   */
  async request(endpoint, options = {}) {
    const defaultHeaders = {
      'Accept': 'application/json',
    };

    const token = localStorage.getItem('mrpl_token');
    if (token) {
      defaultHeaders['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      defaultHeaders['Content-Type'] = 'application/json';
    }


    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(endpoint, config);
      const data = await response.json().catch(() => null);

      if (response.status === 401) {
        localStorage.removeItem('mrpl_token');
        if (window.Auth) {
          window.Auth.currentUser = null;
          const badgeContainer = document.getElementById('user-profile-badge');
          if (badgeContainer) badgeContainer.innerHTML = '';
          window.Auth.showAuthModal(true);
        }
      }

      if (!response.ok) {
        let msg = `HTTP Error ${response.status}: ${response.statusText}`;
        if (data && data.detail) {
          msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        } else if (data && data.message) {
          msg = data.message;
        }
        throw new Error(msg);
      }

      // Check MRPL StandardResponse wrapper
      if (data && typeof data.success === 'boolean') {
        if (!data.success) {
          throw new Error(data.message || data.error || 'Request failed on backend');
        }
        return data.data !== undefined ? data.data : data;
      }

      return data;
    } catch (err) {
      console.error(`[API Error] ${endpoint}:`, err);
      throw err;
    }
  },

  get(endpoint, options = {}) {
    return this.request(endpoint, { method: 'GET', ...options });
  },

  post(endpoint, body = {}, options = {}) {
    const isFormData = body instanceof FormData;
    return this.request(endpoint, {
      method: 'POST',
      body: isFormData ? body : JSON.stringify(body),
      ...options,
    });
  },

  delete(endpoint, options = {}) {
    return this.request(endpoint, { method: 'DELETE', ...options });
  },

  upload(endpoint, formData, options = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: formData,
      ...options,
    });
  }
};

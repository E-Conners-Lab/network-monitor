import axios from 'axios';

const API_BASE = '/api';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Track if we're currently refreshing to avoid multiple refresh attempts
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Handle auth errors with automatic token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and we haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't try to refresh if this was the refresh request itself
      if (originalRequest.url === '/auth/refresh') {
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        }).catch(err => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        localStorage.removeItem('token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await api.post('/auth/refresh', { refresh_token: refreshToken });
        const { access_token, refresh_token: newRefreshToken } = response.data;

        localStorage.setItem('token', access_token);
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken);
        }

        api.defaults.headers.Authorization = `Bearer ${access_token}`;
        originalRequest.headers.Authorization = `Bearer ${access_token}`;

        processQueue(null, access_token);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// Auth
export const auth = {
  login: (username, password) =>
    api.post('/auth/token', new URLSearchParams({ username, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
};

// Devices
export const devices = {
  list: (params) => api.get('/devices', { params }),
  get: (id) => api.get(`/devices/${id}`),
  create: (data) => api.post('/devices', data),
  update: (id, data) => api.put(`/devices/${id}`, data),
  delete: (id) => api.delete(`/devices/${id}`),
  check: (id, data = {}) => api.post(`/devices/${id}/check`, data),
  checkAll: (data = {}) => api.post('/devices/check-all', data),
  netboxStatus: () => api.get('/devices/netbox/status'),
  netboxSync: (site) => api.post('/devices/netbox/sync', null, { params: { site } }),
  netboxDevices: (params) => api.get('/devices/netbox/devices', { params }),
};

// Alerts
export const alerts = {
  list: (params) => api.get('/alerts', { params }),
  listActive: () => api.get('/alerts/active'),
  get: (id) => api.get(`/alerts/${id}`),
  acknowledge: (id) => api.post(`/alerts/${id}/acknowledge`),
  resolve: (id, notes) => api.post(`/alerts/${id}/resolve`, null, { params: { resolution_notes: notes } }),
};

// Metrics
export const metrics = {
  list: (params) => api.get('/metrics', { params }),
  latest: (deviceId, metricType) =>
    api.get('/metrics/latest', { params: { device_id: deviceId, metric_type: metricType } }),
  history: (deviceId, metricType, hours = 24) =>
    api.get('/metrics/history', { params: { device_id: deviceId, metric_type: metricType, hours } }),
  historyBatch: (deviceId, metricTypes, hours = 24) =>
    api.get('/metrics/history/batch', { params: { device_id: deviceId, metric_types: metricTypes.join(','), hours } }),
  getRouting: (deviceId) => api.get(`/metrics/device/${deviceId}/routing`),
};

// Remediation
export const remediation = {
  playbooks: () => api.get('/remediation/playbooks'),
  logs: (params) => api.get('/remediation/logs', { params }),
  execute: (deviceId, playbook, alertId) =>
    api.post(`/remediation/devices/${deviceId}/execute`, { playbook_name: playbook, alert_id: alertId }),
  enableInterface: (deviceId, interfaceName) =>
    api.post(`/remediation/devices/${deviceId}/interface/enable`, { interface_name: interfaceName }),
  clearBgp: (deviceId, neighborIp) =>
    api.post(`/remediation/devices/${deviceId}/bgp/clear`, { neighbor_ip: neighborIp }),
  clearCaches: (deviceId) => api.post(`/remediation/devices/${deviceId}/caches/clear`),
  autoRemediate: (alertId) => api.post(`/remediation/alerts/${alertId}/auto-remediate`),
};

// Network Tests
export const tests = {
  runFull: () => api.post('/tests/run/full'),
  runQuick: () => api.post('/tests/run/quick'),
  runDevice: (deviceId, testType = 'full') =>
    api.post(`/tests/devices/${deviceId}/run`, { test_type: testType }),
  getStatus: (taskId) => api.get(`/tests/status/${taskId}`),
};

// Config Backups
export const configs = {
  list: (params) => api.get('/configs', { params }),
  listDevice: (deviceId, limit = 20) => api.get(`/configs/device/${deviceId}`, { params: { limit } }),
  getLatest: (deviceId) => api.get(`/configs/device/${deviceId}/latest`),
  get: (id) => api.get(`/configs/${id}`),
  diff: (id1, id2) => api.get(`/configs/diff/${id1}/${id2}`),
  backup: (deviceIds, triggeredBy = 'manual') =>
    api.post('/configs/backup', { device_ids: deviceIds, triggered_by: triggeredBy }),
  backupAll: (triggeredBy = 'manual') =>
    api.post('/configs/backup', { triggered_by: triggeredBy }),
  delete: (id) => api.delete(`/configs/${id}`),
};

// System
export const system = {
  version: () => api.get('/version'),
};

export default api;

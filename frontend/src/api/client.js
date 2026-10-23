import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

const TOKEN_KEY = 'auditai_session_token';
api.interceptors.request.use((request) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) request.headers.Authorization = `Bearer ${token}`;
  return request;
});
api.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
    sessionStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(new Event('auditai:unauthorized'));
  }
  return Promise.reject(error);
});

export const authApi = {
  tokenKey: TOKEN_KEY,
  login: (email, password) => api.post('/auth/login', { email, password }),
  devStatus: () => api.get('/auth/dev-otp/status'),
  devGenerate: (email) => api.post('/auth/dev-otp/generate', { email }),
  devVerify: (challenge_id, otp) => api.post('/auth/dev-otp/verify', { challenge_id, otp }),
  me: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
};

export const transfersApi = {
  cycles: (params) => api.get('/transfers/cycles', { params }),
  reconciliation: () => api.get('/transfers/reconciliation'),
  reviews: () => api.get('/transfer-reviews'),
  sendToReview: (body) => api.post('/transfer-reviews', body),
  decide: (id, stage, body) => api.post(`/transfer-reviews/${id}/${stage}`, body),
  upload: (formData) => api.post('/transfers/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};

export const policiesApi = {
  list: (params) => api.get('/policies', { params }),
  run: () => api.post('/policies/run'),
  reviewers: () => api.get('/policies/reviewers'),
  authority: (id, limit) => api.put(`/policies/authorities/${id}`, { limit }),
  inputs: (id, body) => api.put(`/policies/claims/${encodeURIComponent(id)}`, body),
};

export const reviewQueueApi = {
  sync: () => api.post('/review-queue/sync'),
  list: (params) => api.get('/review-queue', { params }),
  detail: (id) => api.get(`/review-queue/${id}`),
  decide: (id, stage, body) => api.post(`/review-queue/${id}/${stage}`, body),
  comment: (id, notes) => api.post(`/review-queue/${id}/comments`, { notes }),
  reconcile: (claimId) => api.post(`/review-queue/reconciliation/${encodeURIComponent(claimId)}`),
  expense: (claimId) => api.post(`/review-queue/expense/${encodeURIComponent(claimId)}`),
};

export const claimsApi = {
  list: (params) => api.get('/claims', { params }),
  getDetail: (claimId) => api.get(`/claims/${claimId}`),
  upload: (formData) => api.post('/claims/upload', formData, { 
    headers: { 'Content-Type': 'multipart/form-data' } 
  }),
  uploadReceipt: (claimId, formData) => api.post(`/receipts/upload?claim_id=${claimId}`, formData, { 
    headers: { 'Content-Type': 'multipart/form-data' } 
  }),
};

export const receiptsApi = {
  get: (receiptId) => api.get(`/receipts/${receiptId}`),
};

export const fraudApi = {
  summary: () => api.get('/fraud/summary'),
  score: () => api.post('/fraud/score'),
  train: () => api.post('/fraud/train'),
};

export const reportsApi = {
  generate: (claimId) => api.post(`/reports/generate/${claimId}`),
  generateAll: () => api.post('/reports/generate-all'),
};

export const casesApi = {
  list: (params) => api.get('/cases', { params }),
  makerRecommend: (claimId, action, notes) =>
    api.post(`/cases/${claimId}/maker-recommend`, null, { params: { action, notes } }),
  checkerSignoff: (claimId, action, notes) =>
    api.post(`/cases/${claimId}/checker-signoff`, null, { params: { action, notes } }),
  getTrail: (claimId) => api.get(`/cases/${claimId}/trail`),
};

export const analyticsApi = {
  benford: () => api.get('/analytics/benford', { timeout: 20000 }),
  relatedParties: () => api.get('/analytics/related-parties', { timeout: 20000 }),
  sodViolations: () => api.get('/analytics/sod-violations', { timeout: 20000 }),
  caseMetrics: () => api.get('/analytics/case-metrics'),
};

export default api;

export const recordsApi = { lookup: (records) => api.post('/review-records/lookup', { records }), detail: (kind, id) => api.get(`/review-records/${kind}/${encodeURIComponent(id)}`) };

export const masterDataApi = {
  status: () => api.get('/master-data/status'),
  upload: (dataset, file) => {const body=new FormData();body.append('file',file);return api.post(`/master-data/${dataset}/import`,body,{headers:{'Content-Type':'multipart/form-data'}});},
  run: (dataset) => api.post(`/master-checks/${dataset}/run`),
  findings: (dataset) => api.get(`/master-checks/${dataset}`),
  send: (id) => api.post(`/master-checks/findings/${id}/send-to-review`),
};

export const detectionApi={ overview:()=>api.get('/detection/overview'), recheck:()=>api.post('/detection/recheck') };

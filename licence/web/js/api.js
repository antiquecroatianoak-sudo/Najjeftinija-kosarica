// Thin client for the REST API. Resolves to parsed JSON or throws ApiError.
// The browser sends the Basic credentials it already used for the page.

export class ApiError extends Error {
  constructor(status, message, fields = {}, body = null) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.body = body;
  }
  get offline() { return this.status === 0; }
}

async function request(method, path, body) {
  const init = { method, headers: { Accept: 'application/json' }, credentials: 'same-origin' };
  if (method !== 'GET') init.headers['X-Requested-With'] = 'LicensePulse'; // CSRF guard on the server
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, 'Nema veze s poslužiteljem. Prikazani su spremljeni podaci.');
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error ?? {};
    const message = res.status === 401 ? 'Prijava je istekla. Osvježite stranicu.' : err.message || `Greška ${res.status}`;
    throw new ApiError(res.status, message, err.fields || {}, data);
  }
  return data;
}

const qs = (params) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString();
  return s ? `?${s}` : '';
};

/** File -> { filename, content_base64 } for upload endpoints. */
export function readFile(file) {
  return new Promise((resolve, reject) => {
    if (file.size > 10 * 1024 * 1024) { reject(new ApiError(413, 'Datoteka je veća od 10 MB.')); return; }
    const reader = new FileReader();
    reader.onload = () => resolve({ filename: file.name, content_base64: String(reader.result).split(',')[1] ?? '' });
    reader.onerror = () => reject(new ApiError(0, 'Datoteku nije moguće pročitati.'));
    reader.readAsDataURL(file);
  });
}

export const api = {
  me: () => request('GET', '/api/me'),
  dashboard: (days) => request('GET', `/api/dashboard${qs({ days })}`),
  analytics: () => request('GET', '/api/analytics'),
  list: (filters = {}) => request('GET', `/api/licenses${qs(filters)}`).then((d) => d.items),
  create: (data) => request('POST', '/api/licenses', data),
  update: (id, data) => request('PUT', `/api/licenses/${id}`, data),
  patch: (id, data) => request('PATCH', `/api/licenses/${id}`, data),
  remove: (id) => request('DELETE', `/api/licenses/${id}`),
  importPreview: (file) => request('POST', '/api/import/preview', file),
  importCommit: (payload) => request('POST', '/api/import/commit', payload),
  notifications: () => request('GET', '/api/notifications'),
  readNotifications: (ids) => request('POST', '/api/notifications/read', ids ? { ids } : {}),
  bankImport: (payload) => request('POST', '/api/bank/import', payload),
  bankTransactions: (status) => request('GET', `/api/bank/transactions${qs({ status })}`).then((d) => d.items),
  bankInsights: () => request('GET', '/api/bank/insights'),
  bankResolve: (id, action, license_id) => request('POST', `/api/bank/transactions/${id}`, { action, license_id }),
  updateOrg: (data) => request('PATCH', '/api/organization', data),
  changePassword: (current, password) => request('POST', '/api/me/password', { current, password }),
  users: () => request('GET', '/api/users').then((d) => d.items),
  createUser: (data) => request('POST', '/api/users', data),
  deleteUser: (id) => request('DELETE', `/api/users/${id}`),
  tokens: () => request('GET', '/api/tokens').then((d) => d.items),
  createToken: (name) => request('POST', '/api/tokens', { name }),
  deleteToken: (id) => request('DELETE', `/api/tokens/${id}`),
  webhooks: () => request('GET', '/api/webhooks'),
  createWebhook: (data) => request('POST', '/api/webhooks', data),
  deleteWebhook: (id) => request('DELETE', `/api/webhooks/${id}`),
  testWebhook: (id) => request('POST', `/api/webhooks/${id}/test`),
  deliveries: (id) => request('GET', `/api/webhooks/${id}/deliveries`).then((d) => d.items),
  rates: () => request('GET', '/api/rates'),
  refreshRates: () => request('POST', '/api/rates/refresh'),
  setRate: (cur, per_eur) => request('PUT', `/api/rates/${cur}`, { per_eur }),
  deleteRate: (cur) => request('DELETE', `/api/rates/${cur}`),
  system: () => request('GET', '/api/system'),
};

/** Fields the API accepts on create/update (drops derived ones). */
export function editable(l) {
  const { name, category, cost, currency, billing_cycle, start_date, status, usage_key, auto_status } = l;
  return { name, category, cost, currency, billing_cycle, start_date, status, usage_key, auto_status };
}

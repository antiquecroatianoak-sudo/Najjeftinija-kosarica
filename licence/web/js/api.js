// Thin client for the REST API. Every call resolves to parsed JSON or throws ApiError.

export class ApiError extends Error {
  constructor(status, message, fields = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

async function request(method, path, body) {
  const init = { method, headers: { Accept: 'application/json' } };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, 'Poslužitelj nije dostupan.');
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error ?? {};
    throw new ApiError(res.status, err.message || `Greška ${res.status}`, err.fields || {});
  }
  return data;
}

export const api = {
  dashboard: () => request('GET', '/api/dashboard'),
  meta: () => request('GET', '/api/meta'),
  list: (filters = {}) => {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    return request('GET', `/api/licenses${qs ? `?${qs}` : ''}`).then((d) => d.items);
  },
  get: (id) => request('GET', `/api/licenses/${id}`),
  create: (data) => request('POST', '/api/licenses', data),
  update: (id, data) => request('PUT', `/api/licenses/${id}`, data),
  patch: (id, data) => request('PATCH', `/api/licenses/${id}`, data),
  remove: (id) => request('DELETE', `/api/licenses/${id}`),
};

async function request(path, options = {}) {
  const apiBase = import.meta.env.PROD ? "http://127.0.0.1:18760" : "";
  const url = path.startsWith("http") ? path : `${apiBase}${path}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function buildQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  health: () => request("/api/health"),
  dashboard: () => request("/api/dashboard"),
  projects: () => request("/api/projects"),
  createProject: (payload) =>
    request("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  deleteProject: (id) => request(`/api/projects/${id}`, { method: "DELETE" }),
  project: (id) => request(`/api/projects/${id}`),
  projectHosts: (id) => request(`/api/projects/${id}/hosts`),
  status: () => request("/api/capture/status"),
  stats: () => request("/api/stats"),
  hosts: (params = {}) => request(`/api/hosts${buildQuery(params)}`),
  settings: () => request("/api/settings"),
  saveSettings: (payload) =>
    request("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  start: () => request("/api/capture/start", { method: "POST" }),
  pause: () => request("/api/capture/pause", { method: "POST" }),
  resume: () => request("/api/capture/resume", { method: "POST" }),
  stop: () => request("/api/capture/stop", { method: "POST" }),
  packets: (params) => request(`/api/packets${buildQuery(params)}`),
  endpoints: (params) => request(`/api/endpoints${buildQuery(params)}`),
  newEndpoints: (params) => request(`/api/endpoints/new${buildQuery(params)}`),
  describeEndpoint: (params) => request(`/api/endpoints/describe${buildQuery(params)}`),
  sitemap: (params) => request(`/api/sitemap${buildQuery(params)}`),
  recon: (params) => request(`/api/recon${buildQuery(params)}`),
};

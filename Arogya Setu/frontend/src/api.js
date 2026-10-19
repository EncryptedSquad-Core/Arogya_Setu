window.API_BASE = "http://127.0.0.1:8000/api/v1";

window.ArogyaAPI = {
  async getState() {
    const res = await fetch(`${window.API_BASE}/state`);
    if (!res.ok) throw new Error("Backend offline");
    return res.json();
  },
  async login(payload) {
    const res = await fetch(`${window.API_BASE}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return { ok: res.ok, data: await res.json() };
  },
  async register(payload) {
    const res = await fetch(`${window.API_BASE}/auth/register`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return { ok: res.ok, data: await res.json() };
  },
  async analyzeScan(payload) {
    const res = await fetch(`${window.API_BASE}/scans/analyze`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return res.json();
  },
  async createAppointment(payload) {
    return fetch(`${window.API_BASE}/appointments`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
  },
  async updateAppointment(id, payload) {
    return fetch(`${window.API_BASE}/appointments/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
  },
  async createReferral(payload) {
    return fetch(`${window.API_BASE}/referrals`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
  },
  async deleteReferral(id) {
    return fetch(`${window.API_BASE}/referrals/${id}`, { method: "DELETE" });
  },
  async updateUser(id, payload) {
    const res = await fetch(`${window.API_BASE}/users/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    return res.json();
  },
  async deleteUser(id) {
    return fetch(`${window.API_BASE}/users/${id}`, { method: "DELETE" });
  }
};
